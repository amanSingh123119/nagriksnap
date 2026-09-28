# P0 deployment gate

Do not deploy publicly until each applicable item is checked:

- [ ] `APP_ENV=production` and explicit HTTPS-only `ALLOWED_ORIGINS` configured.
- [ ] Admin provisioned out-of-band with a strong Argon2 password hash; no secrets committed.
- [ ] TLS termination, trusted proxy configuration, firewall, and request/body limits verified.
- [ ] Shared gateway rate limits configured for login, registration, AI, uploads, and public complaint creation.
- [ ] University/company identities verified before assigning privileged roles and organization names.
- [ ] Private object storage, backups, retention, and authorized evidence download tested for production topology.
- [ ] `python -m pip install pip-audit && pip-audit -r backend/requirements.txt` completed and findings triaged.
- [ ] Repository secrets scan completed; exposed keys rotated.
- [ ] Full role-by-route authorization matrix and cross-organization tests passed.
- [ ] Session expiry/revocation, database restore, concurrent writes, and monitoring/alerting tested.
- [ ] Configure `SESSION_TTL_SECONDS` for the deployment; production sessions are capped at 24 hours.
- [ ] Test single-session logout and account-wide logout with separate user accounts.
- [ ] Frontend image previews verified with private authenticated evidence access.
- [ ] Run `cd backend && python -m unittest discover -s tests -v` in the release environment.

The included tests are focused regression tests and are not a substitute for a full penetration test or production certification.

## Phase 6 — Database and evidence-storage release gates
- [ ] PostgreSQL adapter and schema migrations implemented for all persistence operations.
- [ ] PostgreSQL integration, migration, rollback, concurrency, and restore tests pass.
- [ ] Evidence files moved to private object storage; authorization, encryption, scanning, retention, and deletion controls verified.
- [ ] Encrypted backups, key management, scheduled backups, restore drills, and recovery objectives verified.
- [ ] Privacy/data-retention review and incident-response runbook approved.
- [ ] Independent security review and penetration test completed; all P0 findings resolved.
- [ ] Production startup gate removed only after the above evidence is reviewed and signed off.

## Phase 8 — Database and evidence storage follow-up
- [ ] Replace SQLite persistence with a supported PostgreSQL adapter and versioned migrations.
- [ ] Test migration from a copy of existing data; reconcile row counts and critical records.
- [ ] Test transaction isolation, concurrent writes, migration rollback, and restore.
- [ ] Configure a private S3-compatible bucket, least-privilege IAM, provider encryption, TLS, lifecycle and retention rules.
- [ ] Run live upload/download authorization tests against the provisioned object store.
- [ ] Configure secret management, storage monitoring, backup/restore, and incident response.
- [ ] Keep the production startup release gate enabled until all blockers are verified.
