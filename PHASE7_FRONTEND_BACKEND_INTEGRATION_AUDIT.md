# Phase 7 — Frontend/Backend Integration Audit

## Scope
This phase fixes a deployment integration issue: several frontend pages used hard-coded `http://localhost:8000` URLs. Those URLs point to the visitor's own computer after deployment, not the deployed API.

## Changes made
- Added `window.NAGRIKSNAP_API_BASE` in `frontend/js/main.js`: local development uses `http://127.0.0.1:8000`; deployed pages use same-origin relative API paths.
- Updated login/register, reviews, government impact analytics, university profile, university matching, the reviews helper, and chatbot API base URLs to use the shared base or a safe same-origin fallback.
- Updated the authenticated fetch wrapper to attach the bearer token to same-origin API requests as well as local development API requests.

## Integration map (static code audit)
| Area | Backend route(s) | Integration status |
|---|---|---|
| Login / registration | `POST /auth/login`, `POST /auth/register` | Frontend requests wired; requires live deployment smoke test |
| Challenge list/detail/report/status | `/api/challenges`, `/api/challenges/{id}`, `/api/challenges/{id}/status` | API routes exist; page-specific workflows need live browser testing |
| Proposals | `/api/challenges/{id}/proposals`, `/api/proposals` | API routes exist; test roles and acceptance flow end-to-end |
| Sponsorships | `/api/challenges/{id}/sponsor`, `/api/sponsorships` | API routes exist; verify actual payment/pledge semantics before claiming money is transferred |
| Case room / milestones | `/api/challenges/{id}/case-room`, `/api/challenges/{id}/milestones` | API routes exist; end-to-end workflow testing remains |
| Collaboration | `/api/challenges/{id}/collaboration/*`, `/api/collaboration/*` | API routes exist; notification delivery and full approval workflow remain incomplete |
| Reviews | `/api/reviews`, `/reviews` | Backend routes exist; localStorage fallback means browser-local and server data may diverge if the API fails |
| University profile/matching | `/api/university/profile`, `/api/ai-match`, `/api/challenges/{id}/matches` | Routes exist; matching is heuristic, not a validated semantic AI model |
| Analytics | `/api/analytics`, `/api/admin/impact-analytics` | Routes exist; validate definitions, source data and totals with stakeholders |
| Audit logs | `/api/admin/audit-logs` | Backend route exists; confirm the admin UI and permission boundaries in live tests |
| Evidence uploads | `/uploads/{filename}` | Local disk-backed; NOT suitable for real citizen evidence in production yet |
| Sign out all devices | `POST /auth/logout-all` | Backend endpoint exists; dedicated frontend control is not yet implemented |

## What “connected” means here
A frontend request referencing a backend route is only a static wiring check. It does not prove the deployed API is reachable, the database is persistent, all roles are authorized correctly, external providers work, or the user journey succeeds end-to-end.

## Remaining release blockers
- SQLite-only persistence; PostgreSQL adapter and tested migrations are not complete.
- Evidence files still use local disk; private encrypted object storage, malware scanning, retention/deletion and signed access are not complete.
- Some frontend features have localStorage fallback/demo behavior and may not be server-synchronized.
- External SMS/email, payment/transfer, official organization verification, live GIS, and real AI must not be described as operational unless separately configured and tested.
- Need live browser smoke tests for citizen, government, university, industry and admin roles; integration tests against the deployed API; authorization review; backup/restore drill; security and privacy review; independent penetration test.

## Verdict
**Some core frontend/backend flows are wired, but not every feature is fully connected or verified end-to-end. The site is not ready to accept real citizen data in production.** Keep the Phase 6 production startup safeguard enabled until release blockers are closed and signed off.

## Verification performed in this workspace
- Backend regression suite: 18 tests passed.
- Python compilation: `main.py`, `database.py`, and `scripts/backup_sqlite.py` passed.
- JavaScript syntax: 11 inline script blocks and 5 external JavaScript files passed Node syntax checks.
- Static scan: no hard-coded `http://localhost:8000` references remain in frontend HTML/JS.
- These checks do not replace browser-based end-to-end tests against a deployed staging environment.
