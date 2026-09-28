#!/usr/bin/env python3
"""Create and verify a consistent SQLite backup for development/staging only.

This does not encrypt the backup and is not a production backup solution.
Protect the destination with restrictive filesystem permissions and do not put
real citizen data into this SQLite deployment.
"""
import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


def backup_and_verify(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"SQLite source database not found: {source}")
    if source.resolve() == destination.resolve():
        raise ValueError("Backup destination must differ from source database")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing backup: {destination}")
    try:
        with sqlite3.connect(f"file:{source.resolve()}?mode=ro", uri=True) as src:
            with sqlite3.connect(destination) as dst:
                src.backup(dst)
        with sqlite3.connect(f"file:{destination.resolve()}?mode=ro", uri=True) as check:
            result = check.execute("PRAGMA integrity_check").fetchone()[0]
            if result != "ok":
                raise RuntimeError(f"Backup integrity check failed: {result}")
            table_count = check.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchone()[0]
        os.chmod(destination, 0o600)
        print(f"Backup verified: {destination}")
        print(f"Integrity: {result}; application tables: {table_count}")
        print("Note: backup is not encrypted; store it only in an approved protected location.")
    except Exception:
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1] / "nagriksnap.db")
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        backup_and_verify(args.source, args.destination)
    except Exception as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
