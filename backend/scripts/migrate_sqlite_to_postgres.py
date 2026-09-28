#!/usr/bin/env python3
"""Staged SQLite -> PostgreSQL data migration utility.

Dry-run is the default. Execute only against a disposable/staging PostgreSQL DB
and a sanitized SQLite snapshot. This does not switch the running application to
PostgreSQL; database.py remains SQLite-backed until its query layer is ported.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path


def qident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def map_type(declared: str, pk: bool = False) -> str:
    t = (declared or '').upper()
    if pk and 'INT' in t:
        return 'BIGINT'
    if 'INT' in t or 'BOOL' in t:
        return 'BIGINT' if 'INT' in t else 'BOOLEAN'
    if any(x in t for x in ('REAL', 'FLOA', 'DOUB')):
        return 'DOUBLE PRECISION'
    if 'BLOB' in t or 'BINARY' in t:
        return 'BYTEA'
    if 'NUMERIC' in t or 'DECIMAL' in t:
        return 'NUMERIC'
    return 'TEXT'


def inspect_schema(sqlite_path: Path) -> dict:
    conn = sqlite3.connect(f'file:{sqlite_path.resolve()}?mode=ro', uri=True)
    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        result = {'tables': [], 'warnings': []}
        for table in tables:
            cols = conn.execute(f'PRAGMA table_info({qident(table)})').fetchall()
            fks = conn.execute(f'PRAGMA foreign_key_list({qident(table)})').fetchall()
            indexes = conn.execute(f'PRAGMA index_list({qident(table)})').fetchall()
            count = conn.execute(f'SELECT COUNT(*) FROM {qident(table)}').fetchone()[0]
            result['tables'].append({
                'name': table,
                'columns': [{'name': c[1], 'type': c[2] or 'TEXT', 'notnull': bool(c[3]), 'default': c[4], 'pk': int(c[5])} for c in cols],
                'foreign_keys': [{'from': f[3], 'table': f[2], 'to': f[4], 'on_update': f[5], 'on_delete': f[6]} for f in fks],
                'indexes': [{'name': i[1], 'unique': bool(i[2]), 'origin': i[3]} for i in indexes],
                'rows': count,
            })
        result['warnings'].append('SQLite CHECK constraints and trigger definitions are not recreated by this utility; review source DDL and add equivalent PostgreSQL constraints before cutover.')
        result['warnings'].append('SQLite INTEGER PRIMARY KEY values are copied as BIGINT; identity/sequence behavior for future inserts must be configured and tested before application cutover.')
        result['warnings'].append('The running FastAPI application remains SQLite-backed. This utility migrates data only; it is not a PostgreSQL application adapter.')
        return result
    finally:
        conn.close()


def create_schema(pg, inventory: dict) -> None:
    # Create tables without foreign keys first to avoid dependency ordering issues.
    for table in inventory['tables']:
        defs = []
        pk_cols = [c for c in table['columns'] if c['pk']]
        for c in table['columns']:
            col_type = map_type(c['type'], bool(c['pk']))
            part = f"{qident(c['name'])} {col_type}"
            if c['notnull'] and not c['pk']:
                part += ' NOT NULL'
            # Preserve only simple literal defaults. Skip SQLite-specific expressions.
            default = c['default']
            if default is not None and isinstance(default, str) and re.fullmatch(r"(?:'[^']*'|-?\d+(?:\.\d+)?|NULL|CURRENT_TIMESTAMP)", default.strip(), re.I):
                part += ' DEFAULT ' + default
            defs.append(part)
        if pk_cols:
            defs.append('PRIMARY KEY (' + ', '.join(qident(c['name']) for c in sorted(pk_cols, key=lambda x: x['pk'])) + ')')
        pg.execute(f"CREATE TABLE IF NOT EXISTS {qident(table['name'])} ({', '.join(defs)})")
    # Add foreign keys after all tables exist. Use stable names and skip if present.
    for table in inventory['tables']:
        for n, fk in enumerate(table['foreign_keys'], 1):
            name = f"fk_{table['name']}_{fk['from']}_{n}"[:60]
            pg.execute(f"ALTER TABLE {qident(table['name'])} ADD CONSTRAINT {qident(name)} FOREIGN KEY ({qident(fk['from'])}) REFERENCES {qident(fk['table'])} ({qident(fk['to'])}) ON UPDATE {fk['on_update']} ON DELETE {fk['on_delete']}")
    # Recreate explicit unique indexes only; non-unique indexes can be optimized after load.
    for table in inventory['tables']:
        # Index column lists are read from the source database in the caller's inventory when available.
        for idx in table.get('unique_indexes', []):
            cols = ', '.join(qident(c) for c in idx['columns'])
            pg.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {qident(idx['name'][:60])} ON {qident(table['name'])} ({cols})")


def enrich_indexes(sqlite_path: Path, inventory: dict) -> None:
    conn = sqlite3.connect(f'file:{sqlite_path.resolve()}?mode=ro', uri=True)
    try:
        for table in inventory['tables']:
            for idx in conn.execute(f'PRAGMA index_list({qident(table["name"])})').fetchall():
                # SQLite autoindexes implement PK/UNIQUE constraints; those are represented elsewhere.
                if not idx[2] or idx[3] == 'pk':
                    continue
                info = conn.execute(f'PRAGMA index_info({qident(idx[1])})').fetchall()
                columns = [r[2] for r in info if r[2] is not None]
                if columns:
                    table.setdefault('unique_indexes', []).append({'name': idx[1], 'columns': columns})
    finally:
        conn.close()


def copy_rows(sqlite_path: Path, pg, inventory: dict) -> dict:
    copied = {}
    # Parent tables before child tables so enabled foreign keys are respected.
    by_name = {t['name']: t for t in inventory['tables']}
    pending = set(by_name)
    ordered = []
    while pending:
        ready = sorted(name for name in pending if all(fk['table'] not in pending or fk['table'] == name for fk in by_name[name]['foreign_keys']))
        if not ready:
            raise RuntimeError('Foreign-key cycle detected; manual migration ordering is required: ' + ', '.join(sorted(pending)))
        ordered.extend(ready)
        pending.difference_update(ready)
    with sqlite3.connect(f'file:{sqlite_path.resolve()}?mode=ro', uri=True) as src:
        src.row_factory = sqlite3.Row
        for table_name in ordered:
            table = by_name[table_name]
            columns = [c['name'] for c in table['columns']]
            cols_sql = ', '.join(qident(c) for c in columns)
            placeholders = ', '.join(['%s'] * len(columns))
            sql = f"INSERT INTO {qident(table['name'])} ({cols_sql}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
            count = 0
            for row in src.execute(f"SELECT {cols_sql} FROM {qident(table['name'])}"):
                pg.execute(sql, tuple(row[c] for c in columns))
                count += 1
            copied[table['name']] = count
    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1] / 'nagriksnap.db')
    parser.add_argument('--dry-run', action='store_true', help='Inspect schema and print migration plan (default behaviour).')
    parser.add_argument('--execute', action='store_true', help='Create schema and copy rows into DATABASE_URL; use staging only.')
    args = parser.parse_args()
    if args.execute and args.dry_run:
        parser.error('Choose either --execute or --dry-run, not both')
    if not args.source.is_file():
        print(f'Source SQLite database not found: {args.source}', file=sys.stderr); return 1
    inventory = inspect_schema(args.source)
    enrich_indexes(args.source, inventory)
    if not args.execute:
        print(json.dumps(inventory, indent=2))
        print(f"\nDRY RUN ONLY: {len(inventory['tables'])} tables; {sum(t['rows'] for t in inventory['tables'])} source rows.")
        return 0
    url = os.getenv('DATABASE_URL', '').strip()
    if not url:
        print('DATABASE_URL is required for --execute', file=sys.stderr); return 1
    try:
        import psycopg
    except ImportError:
        print('Install backend requirements to obtain psycopg before running --execute', file=sys.stderr); return 1
    try:
        with psycopg.connect(url) as pg:
            existing = pg.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=current_schema() AND table_type='BASE TABLE'").fetchone()[0]
            if existing:
                print('Target schema is not empty. Use a fresh staging database for this migration.', file=sys.stderr); return 1
            with pg.transaction():
                create_schema(pg, inventory)
                copied = copy_rows(args.source, pg, inventory)
            print(json.dumps({'copied_rows': copied, 'source_rows': {t['name']: t['rows'] for t in inventory['tables']}, 'warnings': inventory['warnings']}, indent=2))
            print('Migration copy finished. Reconcile counts, constraints, sequences, and business totals before any cutover.')
    except Exception as exc:
        print(f'Migration failed: {type(exc).__name__}: {exc}', file=sys.stderr); return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
