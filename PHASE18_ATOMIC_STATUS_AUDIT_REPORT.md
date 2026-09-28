# Phase 18 — Atomic Status Updates and Audit Integrity

## Implemented
- Added `update_complaint_status_atomic` in the SQLite persistence layer.
- The method starts an immediate transaction, reads the current status, applies permitted complaint fields, and writes a status-history event only when the status changes.
- Complaint updates and status-history inserts commit together. Any exception rolls the transaction back, preventing a status change without its corresponding history event.
- Government/admin status endpoint now uses the atomic persistence method and returns 404 if the record does not exist.
- Added regression tests for a successful atomic transition, rollback when a database trigger forces history insertion to fail, and an unknown complaint ID.

## Verification
- `python -m unittest discover -s tests -v`: 29 tests passed.
- Python compilation and archive integrity are checked during packaging.

## Limitations / follow-up
- Audit-log insertion is still separate from the complaint/history transaction; this phase guarantees atomicity only for the complaint row and status-history event.
- SMS notification is an external side effect after the database transaction and can fail independently. A transactional outbox would be a stronger production pattern.
- Browser-based end-to-end testing and production deployment review have not been completed.
- SQLite remains the active database in this build; production migration, backups/recovery, monitoring, and privacy/security review remain required.
