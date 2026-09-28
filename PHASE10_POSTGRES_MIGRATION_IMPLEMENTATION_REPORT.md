# Phase 10 — PostgreSQL Migration Utility (Staging Only)

## Delivered
- Added `backend/scripts/migrate_sqlite_to_postgres.py`.
- Default invocation is read-only dry-run: inventories tables, columns, types, indexes, foreign keys and row counts without exporting row values.
- `--execute` requires `DATABASE_URL` and `psycopg`; it creates a PostgreSQL schema and copies source rows in a transaction. A non-empty target is rejected unless explicitly overridden.
- Added `psycopg[binary]` to backend requirements for this utility.

## Critical scope boundary
This is a **migration utility**, not a PostgreSQL adapter for the running application. `backend/database.py` still uses SQLite (`sqlite3`, `PRAGMA`, `?` placeholders, `executescript`, and SQLite transaction behaviour). The FastAPI app therefore remains SQLite-backed. Do not remove the production startup safeguard or point the live application at PostgreSQL until the query/persistence layer is ported and tested.

## Known migration caveats
- SQLite CHECK constraints and triggers are not automatically recreated; review source DDL and implement equivalent PostgreSQL constraints/triggers.
- Integer primary keys are copied as BIGINT, not identity columns. Configure/advance sequences or identity columns before any future inserts through PostgreSQL.
- Some SQLite defaults/affinities need manual review. Reconcile all table counts, primary/unique keys, foreign keys, and domain-specific totals.
- Unique-index names and source constraints should be reviewed for PostgreSQL naming/compatibility.
- The utility is intended for a sanitized staging copy and a fresh PostgreSQL database. It is not a zero-downtime migration, does not freeze source writes, and does not implement dual-write/CDC.
- No live PostgreSQL service was available in this environment; connection, migration, rollback, concurrency and restore tests have not been run here.

## Staging procedure
1. Take a protected, verified backup of the SQLite source and work from a sanitized copy.
2. Provision an isolated PostgreSQL staging database with TLS, private networking and least-privilege credentials; keep `DATABASE_URL` in a secret manager.
3. Run the dry-run first: `python backend/scripts/migrate_sqlite_to_postgres.py --source backend/nagriksnap.db`.
4. After reviewing the inventory, run against a **fresh staging target only**: `DATABASE_URL='...' python backend/scripts/migrate_sqlite_to_postgres.py --execute --source backend/nagriksnap.db`.
5. Review warnings, implement missing constraints/identity sequences, compare source/target counts and business totals, test representative CRUD flows and rollback/restore.
6. Only after the application adapter is migrated and independent security/privacy reviews pass should a controlled canary/cutover be considered.

## Release decision
**NO-GO for real citizen data.** This phase provides a data-copy utility only. It does not complete application PostgreSQL support, private object storage deployment, encrypted recovery, end-to-end acceptance tests, or independent security review.

## Local verification performed for this phase
- Migration utility dry-run completed against the included development SQLite database: 14 tables and 16 rows inventoried, with no row values in the inventory output.
- Two new unit tests cover type mapping and confirm that the inventory includes schema/count metadata but not inserted row values.
- Backend regression suite: 24 tests passed in the local environment.
- Python compilation passed for the application modules, migration utility and migration-tool tests.
- These checks do not substitute for running the migration against a real PostgreSQL staging service.
