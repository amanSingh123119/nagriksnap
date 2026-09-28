# NagrikSnap — SIH 2026 Problem Statement #26043

> **"A digital platform to crowdsource societal challenges and facilitate collaborative problem solving through universities and industry partnerships."**  
> **Sponsoring Agency:** Government of Jharkhand  
> **Theme:** Crowdsourced Societal Innovation & Quadruple Helix Collaboration (Citizens ↔ Universities ↔ Industry ↔ Government)

---

## 🌟 Quadruple Helix Workflow
1. **Citizens & NGOs**: Crowdsource real-world societal & disaster challenges via photo, voice (Hindi/English), and GPS location.
2. **Groq AI Engine**: Classifies domain (*Disaster Management, Water & Sanitation, Clean Energy, Infrastructure*), computes urgency rating, and generates actionable problem briefs.
3. **University & Student Solvers**: Browse open challenges on `challenges.html`, submit solution proposals, tech stacks, and demo prototypes.
4. **Industry & CSR Partners**: Pledge CSR grant funding, provide hardware kits, and offer technical mentorship.
5. **Government Authorities**: Endorse solutions, coordinate pilot rollouts in Jharkhand, and verify ground-level community impact.

---

## 🚀 Quick Setup Guide

### 1. Backend (FastAPI)
Open a terminal in `backend/`:
```bash
cd backend
python -m venv venv
venv\Scripts\activate      # Windows (or source venv/bin/activate on Mac/Linux)
pip install -r requirements.txt
```

Set up `.env` locally by copying `.env.example`. Never commit `.env`.
- `GROQ_API_KEY` — optional AI provider key
- `FAST2SMS_API_KEY` — optional SMS provider key
- `ALLOWED_ORIGINS` — exact frontend origins, comma-separated
- `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` — optional, securely provisioned admin account; there is no default admin password

Passwords require at least 10 characters and are hashed with Argon2. Public self-registration creates citizen accounts only. University, industry and government accounts must be provisioned/verified through an administrative process. Privileged API operations require a backend-issued bearer token and role authorization.

To generate an Argon2 password hash locally for the optional environment-provisioned admin, run from `backend/`:
```bash
python -c "from argon2 import PasswordHasher; print(PasswordHasher().hash(input('Admin password: ')))"
```
Set the output as `ADMIN_PASSWORD_HASH` and set a non-default `ADMIN_USERNAME` in your local `.env`. Do not commit either value.

For local testing, create separate privileged workspace accounts from `backend/` with the operator-only CLI. It prompts for account details and a hidden password; sign in using that account's email or phone:
```bash
python provision_user.py --role admin
python provision_user.py --role govt_admin
python provision_user.py --role university
python provision_user.py --role industry
```
Run only against a trusted local/development database. Public signup remains citizen-only; do not add privileged roles to the public registration form.

**Security note:** this is a hardened SIH prototype, not yet a production-certified service. Before public launch, move sessions to a persistent revocable session store, add persistent audit logs and complete a security review. Configure HTTPS, backups, monitoring, and a proper password-recovery provider.

Run the server:
```bash
uvicorn main:app --reload --port 8000
```

### 2. Frontend
Open `frontend/index.html` in Live Server or any static web server. For VS Code Live Server's default port, the backend allows `http://localhost:5500` and `http://127.0.0.1:5500`. If you use another port, add that exact frontend origin to `ALLOWED_ORIGINS` in `backend/.env` and restart FastAPI. Alternatively, open the site through FastAPI at `http://127.0.0.1:8000` so the frontend and API share an origin:
- **Home**: `index.html`
- **Crowdsource Challenge**: `report.html`
- **Explore & Solve (University/CSR Hub)**: `challenges.html`
- **Track Status**: `track.html`
- **Admin Dashboard**: `admin.html`

---

## 📡 Key REST APIs (`http://localhost:8000`)
- `GET /api/challenges` — List societal challenges with domain/priority filters
- `POST /api/challenges` — Crowdsource a new challenge with AI categorization
- `POST /api/challenges/{id}/proposals` — Submit university student proposal
- `POST /api/challenges/{id}/sponsor` — Pledge industry CSR grant
- `GET /api/challenges/{id}/case-room` — Multi-stakeholder collaboration workspace
- `PUT /api/challenges/{id}/status` — Lifecycle update (Crowdsourced ➔ In Co-Development ➔ Pilot Solved)

## P1: Organization verification

Public signup remains citizen-only. University and industry users must request verification and wait for an administrator to approve the organization role. See `SECURITY_HARDENING_REPORT.md` for the API workflow and deployment limitations. Do not approve an organization without independent verification.

### Organization verification API

- `POST /api/organization-verification` — authenticated citizen submits a request.
- `GET /api/organization-verification/mine` — authenticated user views their requests.
- `GET /api/admin/organization-verification?status=pending` — admin queue (`pending`, `approved`, `rejected`, or `all`).
- `POST /api/admin/organization-verification/{request_id}/review` — admin approves/rejects; rejection requires a reason.

The API throttling middleware now uses SQLite-backed rate-limit events. In a multi-host deployment, configure a shared limiter (for example Redis) and edge rate limits.

## P2: University expertise matching

P2 adds a verified-university profile and explainable matching API:

- `PUT /api/university/profile` (Bearer token; approved `university` role): save `expertise`, optional `sdg_focus`, `past_projects`, `available_slots`, `districts`, and `website`.
- `GET /api/challenges/{challenge_id}/matches` (Bearer token; `admin` or `govt_admin`): returns ranked university recommendations, scores, matched terms, and reasons.

The baseline score is transparent: expertise/SDG keyword overlap (60 points maximum), available capacity (20), prior projects (15 maximum), and district text match (5). This is advisory ranking only; a human must review the profile and proposal before assigning a challenge. It is not a substitute for semantic retrieval or independent institution verification.

Run backend tests from `backend/` with `python -m unittest discover -s tests -v`.

## P3: Collaboration workspace

P3 adds authenticated team invitations and a project task board to the existing case-room workflow.

### Collaboration APIs

- `GET /api/challenges/{challenge_id}/collaboration/members` — list members for a case room the caller can access.
- `POST /api/challenges/{challenge_id}/collaboration/invitations` — an authorized government reviewer or university collaborator invites an existing account by `user_id` and a project role (`student`, `faculty`, `mentor`, `member`). The invitee must accept before receiving case-room access.
- `GET /api/collaboration/invitations/mine` — list invitations for the signed-in account.
- `POST /api/challenges/{challenge_id}/collaboration/invitations/decision` — accept or decline the current user's pending invitation with `{"decision":"accept"}` or `{"decision":"decline"}`.
- `GET /api/challenges/{challenge_id}/collaboration/tasks` — list tasks for an authorized case-room member.
- `POST /api/challenges/{challenge_id}/collaboration/tasks` — create a task with `title`, optional `description`, optional accepted-member `assigned_to`, `priority` (`low`, `medium`, `high`) and optional ISO date `due_date`.
- `PATCH /api/collaboration/tasks/{task_id}` — update task details/status (`todo`, `in_progress`, `blocked`, `done`). Only the task creator, assignee, or government reviewer can update a task.

The case-room page now includes the P3 member, invitation and task-board UI. Sign in first; the API remains the authority for permissions. For local development, open the page using the same frontend serving setup already described above and ensure the backend API is running. The invitation form expects the target account's user ID.

### P3 validation

Run `cd backend` then `python -m unittest discover -s tests -v`. The suite covers pending-invite access denial, invitation acceptance, task creation, assignment validation and status validation. The current suite has 13 tests. This is application-level regression coverage, not an independent penetration test or production certification.

## Phase 9 migration readiness
A read-only SQLite schema/count inventory is available at `scripts/audit_sqlite_migration.py`. Run it with `python scripts/audit_sqlite_migration.py` (or pass a database path). It does not export row data and is not a PostgreSQL migration. See `PHASE9_MIGRATION_READINESS_REPORT.md`. Production remains blocked until the PostgreSQL adapter, private storage deployment, backup/restore, and security release gates are completed and independently reviewed.

### PostgreSQL migration utility (staging only)
The SQLite-to-PostgreSQL migration utility defaults to a read-only schema/count inventory:

```bash
python backend/scripts/migrate_sqlite_to_postgres.py --source backend/nagriksnap.db
```

Execution requires `psycopg` and `DATABASE_URL` and must only be run against a fresh, isolated staging database using a sanitized source snapshot:

```bash
DATABASE_URL='postgresql://…' python backend/scripts/migrate_sqlite_to_postgres.py --execute --source backend/nagriksnap.db
```

This utility does **not** switch the running app to PostgreSQL. See `PHASE10_POSTGRES_MIGRATION_IMPLEMENTATION_REPORT.md` for constraints and release gates. Keep the production startup safeguard enabled.

## Phase 11: honest release review

See `BRUTAL_WEBSITE_REVIEW_PHASE11.md` for a source-code-based scorecard and the release blockers. **Current decision: no-go for real citizen data.** The application database layer is still SQLite-backed; the PostgreSQL migration utility does not switch runtime persistence. Keep the production startup safeguard enabled until PostgreSQL cutover, private storage, backup/restore, end-to-end tests and independent security/privacy review are complete. This review is not a live-site or penetration test.

## Phase 12 — Role-specific login foundation
The login page now provides distinct Citizen, Government, University, Industry, and Admin workspace choices. The selected workspace is checked against the role returned by the backend; it does not grant privileges. See `PHASE12_ROLE_LOGIN_FOUNDATION_REPORT.md` for scope and limitations.

## Phase 13 — Public Homepage Redesign

The public homepage (`frontend/index.html`) now includes About, Features, How It Works, role-specific workspaces, Impact and Accountability, Feedback/Reviews, FAQ, Contact and footer sections. It uses role-specific login links and avoids presenting illustrative metrics or fabricated testimonials as verified facts. See `PHASE13_PUBLIC_HOMEPAGE_REPORT.md`.


## Phase 14 — Role-specific dashboard navigation
See `PHASE14_ROLE_DASHBOARD_LAYOUT_REPORT.md`. Adds responsive role-specific sidebar navigation to the Citizen, Government, University, Industry, and Admin workspaces. This is a UI/navigation improvement, not a substitute for server-side authorization.

## Phase 15 — Citizen/Government complaint workflow integration
- Citizen report submission now records the real backend-issued tracking ID in a browser-local list and no longer invents a successful-looking tracking ID when the backend submission fails.
- Citizen dashboard loads backend challenge data and shows records whose tracking IDs were submitted in the current browser, while retaining legacy local-only records with a clear limitation note. This is not yet account-linked ownership across devices.
- Government workspace includes a live complaint table and status update controls. Updates send the bearer token to the protected backend status endpoint; the server remains authoritative for role checks and audit logging.
- Validation: backend unit tests, Python compilation, JavaScript syntax checks, static links, and ZIP integrity. Browser-based end-to-end testing was not run.


## Phase 16 — Account-linked complaint ownership
- Added optional citizen-session ownership at report submission and a protected `GET /api/me/complaints` endpoint.
- Citizen My Complaints now uses the authenticated account-scoped endpoint. Legacy anonymous reports are not automatically assigned to accounts.
- See `PHASE16_ACCOUNT_LINKED_COMPLAINTS_REPORT.md` for scope and limitations.


## Phase 17 — Status history and tracking
- Added persisted complaint status history and a status-history API.
- Tracking page now displays backend-recorded status events.
- See `PHASE17_STATUS_HISTORY_REPORT.md` for verification and limitations.

### Phase 18 — Atomic status transitions
- Complaint status updates and status-history events are now committed in one SQLite transaction.
- If history insertion fails, the status update rolls back. Regression tests cover successful transitions, forced history-write failure, and missing complaints.
- See `PHASE18_ATOMIC_STATUS_AUDIT_REPORT.md` for scope and remaining production limitations.


### Phase 19 — Notification outbox and responsive hardening
See `PHASE19_NOTIFICATION_OUTBOX_AND_RESPONSIVE_REPORT.md`. Status transitions enqueue SMS notifications transactionally; run the one-shot outbox worker through an external scheduler. Shared styles now include responsive layouts for mobile, tablet and desktop. Real-device/browser testing and production database/storage release work remain required.

### Phase 20 — Responsive audit and hardening
See `PHASE20_RESPONSIVE_AUDIT_REPORT.md` for the latest responsive CSS, keyboard focus, overflow handling, mobile modal, and reduced-motion improvements. This is code-level hardening; real-device/browser visual QA is still required.

## Phase 21 — Responsive QA and layout verification

See `PHASE21_BROWSER_AUDIT_REPORT.md` for the page/reference checks, JavaScript syntax checks, backend regression results, and the explicit limitation that Chromium navigation was blocked by the execution environment. Visual browser QA remains outstanding.


## Phase 22 — Email authentication and integration audit
- Added citizen email capture, best-effort login notifications, and email OTP password reset endpoints.
- Configure SMTP using `backend/.env.example`; without SMTP credentials real emails are not sent.
- See `PHASE22_AUTH_EMAIL_INTEGRATION_AUDIT_REPORT.md` for limitations and release blockers.


## Phase 23 — Cross-role workflow integration audit
See `PHASE23_CROSS_ROLE_INTEGRATION_REPORT.md` for the authentication fixes, backend-connected workflow corrections, regression tests, and remaining gaps.


## Phase 25 — Live milestone workflow
- Replaced illustrative case-room milestone cards with authenticated records loaded from the backend.
- Added a milestone submission form for authorised participating stakeholders, including progress, status, summary, and optional evidence URL.
- Added server-side validation for non-empty milestone titles, progress range, and HTTP(S)-only evidence URLs.
- Replaced illustrative escrow amount/partner claims with an explicit statement that payments and escrow are not processed.
- Added security regression tests for citizen write denial and evidence URL validation.
- Verification: 38 backend tests passed; browser-based end-to-end rendering remains unverified.


## Phase 26 — Government evidence review
See `PHASE26_GOVERNMENT_EVIDENCE_REVIEW_REPORT.md`. Government/admin reviewers can approve, reject, or request revisions on milestone evidence. When milestones exist, Pilot requires an approved milestone and Resolved requires an approved 100% milestone. This remains a staging workflow; evidence URLs are not independently verified.
