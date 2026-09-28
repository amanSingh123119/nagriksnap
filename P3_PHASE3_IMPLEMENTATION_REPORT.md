# Phase 3 — Collaboration workflow report

## Implemented
- Added an authenticated, challenge-scoped directory search for eligible registered collaborators.
- Directory access is restricted to accepted project members with admin, government-admin, or university roles.
- Search requires at least two characters and returns at most 20 results.
- Results include only user ID, name, username, role, organisation, and department; phone, address, and credential fields are never returned.
- Existing project members and invitees are excluded from new search results to reduce duplicate invitations.
- Replaced manual user-ID entry in the case-room invite form with directory search and explicit selection.
- Task assignee field is a dropdown populated from accepted members.
- Task cards mark overdue tasks when their due date has passed and they are not done.
- Invitation success text explicitly states that no email or SMS was sent.

## Verification
- Python compilation and the focused backend regression suite should be run before release.
- Frontend syntax validation should be run before release.
- This is not a production security certification; perform browser-based tests with separate accounts and challenge memberships.

## Remaining human / later-phase work
- Connect an email/SMS provider and verified sender identity if external notifications are required.
- Decide notification preferences, delivery retries, unsubscribe/consent rules, and retention policy.
- Validate actual organisation affiliations before allowing privileged roles.
- Test with separate university and government accounts, including attempts to search or invite across unauthorised challenges.
- Add persistent notification centre and proposal/milestone approval workflow in a later phase.
- SQLite is still used; production multi-instance deployment requires a reviewed PostgreSQL migration and shared rate-limit store.
