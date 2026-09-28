#!/usr/bin/env python3
"""Read-only SQLite inventory for planning a PostgreSQL migration.

This intentionally exports schema metadata and row counts only, never citizen rows.
Run: python scripts/audit_sqlite_migration.py [path-to-sqlite-db]
"""
from __future__ import annotations
import json
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / "backend" / "nagriksnap.db"

def main() -> int:
    db_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_DB.resolve()
    if not db_path.is_file():
        print(f"Database not found: {db_path}", file=sys.stderr)
        return 2
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        tables = []
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        for name in names:
            # Names originate from sqlite_master, but quote identifiers defensively.
            quoted = '"' + name.replace('"', '""') + '"'
            columns = [dict(r) for r in conn.execute(f"PRAGMA table_info({quoted})")]
            foreign_keys = [dict(r) for r in conn.execute(f"PRAGMA foreign_key_list({quoted})")]
            indexes = [dict(r) for r in conn.execute(f"PRAGMA index_list({quoted})")]
            count = conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
            tables.append({"name": name, "row_count": count, "columns": columns,
                           "foreign_keys": foreign_keys, "indexes": indexes})
        report = {"database_file": db_path.name, "integrity_check": integrity,
                  "table_count": len(tables), "total_rows": sum(t["row_count"] for t in tables),
                  "contains_row_data": False, "tables": tables,
                  "notes": ["Metadata-only report; no row values exported.",
                            "Not a PostgreSQL migration or compatibility certification."]}
        print(json.dumps(report, indent=2, default=str))
        return 0 if integrity == "ok" else 1
    finally:
        conn.close()

if __name__ == "__main__":
    raise SystemExit(main())
