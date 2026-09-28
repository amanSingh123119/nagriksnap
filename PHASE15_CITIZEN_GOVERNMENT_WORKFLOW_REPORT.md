# Phase 15 — Citizen/Government complaint workflow integration

## Implemented
1. **Report submission reliability:** A tracking ID is displayed only after the backend returns a real ID. On API/network failure, the form remains available and shows an error instead of generating a fake ID.
2. **Citizen tracking list:** Successful IDs are stored in the current browser's `nagriksnap_submitted_ids`. The dashboard requests the backend challenge list and matches it to those IDs. Legacy local-only records are still shown when available.
3. **Government status workflow:** The government portal now displays live challenge records and lets an authorized reviewer submit status changes to `PUT /api/challenges/{id}/status` with a bearer token. The API enforces the allowed roles and writes an audit action.

## Important limitations
- Complaint creation is still not bound to an authenticated citizen identity in the backend. The citizen dashboard therefore uses a browser-local list of tracking IDs; it does not provide account-linked ownership or cross-device recovery. This should be addressed with a schema migration and authenticated ownership endpoint before real citizen data is used.
- The government list uses the existing public challenge-list endpoint, which omits phone numbers and assignment fields. Status updates are protected server-side.
- The project is still not production-ready. The existing production release gate blocks launch until PostgreSQL application persistence and production private-storage verification are complete.
- No browser-driven end-to-end test was run in this phase.

## Validation
- Backend unit tests: 24 passed.
- Python compilation: passed.
- Inline JavaScript syntax: checked with Node.js where available.
- Static local links and ZIP integrity: checked.
