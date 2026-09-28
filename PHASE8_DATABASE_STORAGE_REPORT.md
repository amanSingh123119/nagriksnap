# Phase 8 — Database and Evidence Storage Hardening

## Implemented
- Added `backend/storage.py`, a storage adapter with development-local storage and private S3-compatible object storage modes.
- Complaint evidence upload now writes through the adapter and stores an opaque storage key in the existing `photo` field.
- Evidence retrieval continues to authorize case-room membership before reading from storage; the API streams bytes and does not generate public object URLs.
- S3 writes request server-side AES-256 encryption. Bucket privacy, IAM policy, lifecycle rules, TLS and provider-side encryption settings must also be configured by the operator.
- Added storage adapter tests for local round-trip, path traversal rejection, invalid mode, and missing S3 bucket configuration.
- Added environment configuration examples for S3-compatible storage.

## Not completed — PostgreSQL
The application persistence layer in `backend/database.py` remains SQLite-specific (sqlite3, PRAGMA, SQLite schema initialization and `?` placeholders). A PostgreSQL migration has **not** been implemented. Do not point this application at PostgreSQL or claim PostgreSQL support. A proper migration requires a supported adapter/ORM, versioned schema migrations, data migration and reconciliation, transaction/concurrency tests, and a tested rollback plan.

## Production status
**Not production-ready for real citizen data.** The production startup safeguard remains enabled. Local evidence storage is development-only. S3 mode is an implementation foundation, but production operation still requires a private bucket, least-privilege IAM, key/secret management, network controls, retention/deletion policy, malware/content scanning policy, monitoring, backup/restore validation and independent security review. PostgreSQL persistence remains a release blocker.

## Verification
Run from `backend/`:

```bash
python -m unittest discover -s tests -v
python -m py_compile main.py database.py storage.py
```

The S3 path requires a separately provisioned test bucket for live integration testing; unit tests do not prove the cloud configuration is secure.
