# Phase 9 — PostgreSQL Migration Readiness and Release Gates

## Delivered
- Added `scripts/audit_sqlite_migration.py`, a read-only inventory tool for the current SQLite database.
- The tool reports schema columns, indexes, foreign keys, table row counts, and SQLite integrity without exporting citizen/user row values.
- Added a migration runbook covering staged migration, reconciliation, rollback, and release evidence.

## Not delivered (do not claim otherwise)
- The application still uses `sqlite3` and SQLite-specific SQL. No PostgreSQL adapter or production migration has been completed.
- No live PostgreSQL service was available here, so connection, schema, migration, concurrency, failover, and restore tests were not run.
- No live S3/MinIO bucket, IAM policy, key management, malware scanning, lifecycle policy, or restore drill was available for verification.
- No independent privacy review or penetration test was performed.

## Required migration runbook
1. Provision a non-production PostgreSQL instance with TLS, private networking, least-privilege application role, and managed secrets.
2. Implement a supported database adapter and versioned migrations for every table and query; remove SQLite-only constructs (`PRAGMA`, `executescript`, `INSERT OR REPLACE`, `?` placeholders, SQLite transaction assumptions).
3. Freeze writes or use a documented dual-write/CDC plan for cutover. Take an encrypted, verified source backup first.
4. Run migrations against a sanitized copy. Compare table counts, key constraints, orphan checks, and critical business totals; validate password/session handling without exposing secrets in logs.
5. Test concurrent writes, transaction rollback, uniqueness/foreign-key behavior, session revocation, rate limits, and failure/retry behavior.
6. Rehearse rollback and restore with measured RPO/RTO. Do not treat a successful schema migration as a backup/restore test.
7. Deploy behind a canary, monitor errors/latency, then cut over only after product and security sign-off.
8. Keep the production startup gate in place until all release gates are evidenced and approved.

## Current production decision
**NO-GO for real citizen data.** This phase improves migration planning only. It does not make the platform production-ready and does not remove the startup safeguard.
