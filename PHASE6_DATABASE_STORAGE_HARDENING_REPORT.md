# Phase 6 — Database and Storage Hardening Foundation

## Implemented in this phase
- Added `NAGRIKSNAP_SQLITE_PATH` so tests and non-production deployments can point SQLite at an explicit path instead of silently sharing the default file.
- Added `backend/scripts/backup_sqlite.py`, which uses SQLite's online backup API, refuses to overwrite an existing destination, checks `PRAGMA integrity_check`, and applies owner-only file permissions where supported.
- Added a fail-closed production startup gate. The current backend still uses SQLite and local-disk evidence uploads; `APP_ENV=production` now refuses to start rather than inviting operators to put real citizen data on an architecture that has not completed production storage controls.

## Important scope boundary
**This phase does not make NagrikSnap production-ready for real citizen data.** It deliberately prevents production-mode startup. The app still has a SQLite-specific persistence layer and local `backend/uploads` storage. The backup utility is for development/staging only, is not encrypted, and is not a substitute for managed encrypted backups.

## Required before real citizen data
1. Implement and test a PostgreSQL adapter/migrations for every query and transaction; run migration and rollback tests against a real PostgreSQL service.
2. Move evidence uploads to private object storage with encryption at rest, short-lived authorized download URLs, malware/content scanning, retention/deletion controls, and access logs.
3. Define data minimization, retention, deletion, consent, incident response, breach handling, and access-review procedures appropriate to the deployment and applicable Indian law/policy.
4. Configure managed secrets, HTTPS/TLS, trusted proxy settings, rate limiting, monitoring/alerting, tested encrypted backups, restore drills, and disaster recovery objectives.
5. Complete dependency/security scans, authorization review, privacy review, load tests, and an independent penetration test; record sign-off and close every P0 checklist item.
6. Only remove the production startup gate after the PostgreSQL and private-storage implementation is complete and its release tests pass.

## Verification
- Run backend regression tests: `cd backend && python -m unittest discover -s tests -v`.
- Verify backup tooling: `python backend/scripts/backup_sqlite.py --source backend/nagriksnap.db --destination /secure/nonproduction/path/backup.db`.
- Test the fail-closed guard in a subprocess with `APP_ENV=production`; expected result is a clear startup error until release gates are closed.

Do not run backups containing real citizen data into an unencrypted or unapproved destination.
