# NagrikSnap P0 Security Hardening Report — v3

## Implemented in this pass

- Kept the existing Argon2 password hashing, database-backed revocable sessions, role dependencies, case-room membership checks, and admin audit trail.
- Made complaint upload retrieval authenticated and restricted it to administrators/government administrators and users authorized for the corresponding case room. Responses use `private, no-store`; path resolution is checked.
- Closed a data exposure in the case-room aggregate endpoint: non-admin members no longer receive proposal lead email/phone or sponsorship contact name/email.
- Removed proposal-supplied arbitrary URLs from case-room announcement attachment fields.
- Public registration always creates a citizen and ignores self-declared organization/department values, preventing role escalation and unverified organization claims through registration.
- Review creation now checks challenge existence, bounds rating/impact values, and derives reviewer identity/department from the authenticated account rather than trusting client-supplied identity fields.
- Added validation for public challenge description/title length, phone format, geographic coordinate bounds, and bounty range.
- Tightened in-process request throttling by endpoint and set lower limits for login/registration. This is a fallback only, not a substitute for a shared edge/API-gateway limiter.
- Added production startup checks requiring explicit exact HTTPS `ALLOWED_ORIGINS` and an out-of-band admin username/password hash when `APP_ENV=production`.
- Added focused security regression tests under `backend/tests/test_security.py`.

## Verification performed

- Python compilation passed for `backend/main.py`, `backend/database.py`, and the regression test file.
- Five regression tests passed: protected routes require authentication; citizen registration cannot escalate role or claim an organization; citizens cannot enter case rooms; public challenge details omit phone/admin assignment; security headers are present.
- ZIP archive integrity checked after packaging.

## Still required before public production deployment (not claimed complete)

1. **Organization verification:** university/company accounts and roles must be provisioned only after an out-of-band verification process. Public registration cannot establish institutional identity.
2. **Shared abuse controls:** configure reverse-proxy/API-gateway rate limits, request/body limits, and optionally CAPTCHA for public complaint creation. The in-process limiter resets on restart and is not shared across workers.
3. **Storage and operations:** evidence is now access-controlled by the application but remains on local disk. Use private object storage with least-privilege credentials, backups, retention policy, and authenticated downloads for multi-instance production.
4. **Deployment security:** terminate TLS at a trusted proxy/load balancer, configure trusted proxy handling, exact production origins, firewall rules, database backup/restore, monitoring, and secret management. Do not expose the development server directly to the internet.
5. **Dependency/secrets scans:** `pip-audit` was not installed in the execution environment, so a vulnerability scan was not performed. Run `python -m pip install pip-audit && pip-audit -r backend/requirements.txt`; run a repository secrets scanner and rotate any exposed credentials.
6. **Broader regression testing:** tests are focused, not exhaustive. Run end-to-end tests for every route and role, cross-user/cross-organization access, uploads, session revocation/expiry, concurrent writes, and the actual deployment environment.
7. **Database:** SQLite remains in use. Review migration/backups and transaction boundaries before multi-worker production use.
8. **Frontend evidence previews:** private evidence endpoints require an authenticated request. Review all image preview flows; do not make evidence public merely to restore unauthenticated image rendering.

## CSRF note

The current API authenticates with an explicit Bearer token header and does not use cookie-based authentication, so classic ambient-cookie CSRF is not the current authentication mechanism. If authentication is moved to cookies, add CSRF tokens and appropriate SameSite/Secure/HttpOnly cookie settings before deployment.

**Status:** Additional P0 fixes and focused tests completed in this pass. Not production-certified; the deployment and verification items above remain open.

# P1 Security & Trust Workflow — v4

## Implemented in this pass

- Added a persisted organization-verification request workflow for university and industry accounts. Public registration still creates citizen accounts only.
- Added authenticated request submission and a user's own request-history endpoint.
- Added administrator-only queue and review endpoints. Approval assigns the verified organization and role; rejection requires a reason. Pending requests cannot grant privileges.
- Added audit events for submission, approval, and rejection.
- Updated token verification to load the user's current role and organization from the database, so role changes apply to existing sessions instead of leaving stale role claims active.
- Replaced the in-memory endpoint throttle with an atomic SQLite-backed limiter shared by API workers using the same database file. It hashes the IP/path bucket before storage and fails closed if limiter storage is unavailable.
- Added regression tests for approval flow, admin-only review, and rate-limit windows.

## P1 API workflow

1. Citizen submits `POST /api/organization-verification` with `requested_role` (`university` or `industry`), organization name, contact email, justification, and optional department/HTTPS website.
2. Citizen checks `GET /api/organization-verification/mine`.
3. An administrator reviews `GET /api/admin/organization-verification?status=pending`.
4. Administrator approves or rejects with `POST /api/admin/organization-verification/{request_id}/review`. Approval changes the account's role and organization; rejection requires a note.

These endpoints provide an application workflow, not proof that the institution itself is genuine. Administrators must verify submitted details through an independent channel before approving.

## Verification

Run from `backend/`:

```bash
python -m py_compile main.py database.py tests/test_security.py
python -m unittest discover -s tests -v
```

SQLite-backed rate limiting is shared only among processes using the same database file. For multi-host deployment, use a shared store such as Redis and configure gateway-level body/request limits. This change does not certify the application for public production deployment.

# P2 University Matching — v5

## Implemented in this pass
- Added a persistent `university_profiles` table for verified university expertise, SDG focus, past project count, available project slots, district coverage, website, and update timestamp.
- Added `PUT /api/university/profile`. Only accounts already approved with the `university` role can create/update a profile. Inputs are bounded and organization name is taken from the approved account, not trusted from the request body.
- Added `GET /api/challenges/{challenge_id}/matches`, restricted to `admin` and `govt_admin` roles.
- Added transparent, deterministic advisory ranking: expertise/SDG keyword overlap (up to 60 points), reported capacity (20), prior projects (up to 15), and district match (5). The API returns matched terms and human-readable reasons, plus a notice that recommendations are not automatic assignments.
- Added regression tests for role restrictions, profile persistence, explainable match output, and matching endpoint access control.

## P2 verification
- `python -m unittest discover -s tests -v`: 11 tests passed.
- Python compilation and ZIP integrity are checked for the delivered archive.

## Limitations
- Matching is a transparent keyword baseline, not a trained semantic/embedding model. Scores should be evaluated against human-labelled matches before operational use.
- District matching is a simple text comparison, not geospatial distance calculation.
- Profile details are self-reported by an already role-approved organization and still require administrative verification of evidence.
- Matching API is currently an admin/government workflow; frontend integration is not included in this P2 pass.
