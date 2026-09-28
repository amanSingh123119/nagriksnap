# NagrikSnap P3 — Collaboration Workspace

## Implemented
- Persistent collaboration membership per challenge, with `invited`, `accepted`, `declined`, and `removed` states.
- Invitations are scoped to a challenge and can only be accepted/declined by the invited account.
- Pending invitations do not grant case-room access; accepted invitations grant access only to that challenge.
- Persistent project tasks with title, description, assignee, priority, due date, status, creator and timestamps.
- Assignees must be accepted members of the same challenge.
- Task updates are limited to the creator, assignee, or government reviewer.
- API audit events for invitation actions and task creation/updates.
- Frontend collaboration section in `frontend/caseroom.html` for invitations, member list, task creation and status updates.
- SQLite schema is created/migrated by the existing database initialization routine.

## API contract
See the P3 section in `README.md` for endpoints and payloads.

## Validation performed
- Python backend modules compile.
- Security and collaboration regression tests pass: 13 total.
- Frontend inline JavaScript syntax check passes.
- ZIP archive integrity check passes.

## Known limitations before production
- Invitations target an existing account by internal user ID; a user directory/search UI and email/SMS notifications are not included.
- No file attachments are added to task records; continue using the separately controlled evidence-storage workflow.
- SQLite is suitable for the current prototype, not a multi-instance production deployment. Plan PostgreSQL migrations and a shared rate limiter before scale-out.
- Notifications are currently in-app/API workflow only; no delivery provider is configured here.
- Conduct deployment-specific authorization review and penetration testing before handling real citizen data.
