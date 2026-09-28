# Phase 17 — Complaint Status History and Citizen Tracking

## Implemented
- Added `complaint_status_history` table and index to the SQLite schema.
- Backfilled one baseline status event for existing complaints that did not have history.
- New complaints receive an initial `Complaint submitted` event.
- Authorized government/admin status changes append a history event with old/new status, timestamp and internal actor metadata.
- Added `GET /api/challenges/{challenge_id}/status-history`, returning status events without actor identity fields or contact details.
- Updated `track.html` to fetch the current complaint and status history from the backend using a tracking ID. Removed its dependency on browser-local complaint records for lookup and replaced the illustrative lifecycle with recorded events.
- Updated tracking-page copy to clarify that lookup uses a tracking ID, not a phone number.
- Added a regression test for event ordering, actor-field privacy and missing IDs.

## Verification
- Backend unit tests run with `python -m unittest discover -s tests -v` from `backend/`.
- Python compilation, inline JavaScript syntax checks, local HTML-link checks and ZIP integrity checks were run for this phase.

## Limitations
- Public tracking IDs act as lookup keys; avoid exposing tracking IDs publicly. For sensitive or high-risk reports, require account authentication before showing details/history.
- Status history records platform status changes; it does not independently verify real-world resolution.
- Status row update and history insertion are separate database operations, not a single transaction. A future hardening phase should make them atomic.
- Browser-based end-to-end testing and production security review have not been completed.
