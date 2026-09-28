# Phase 24 — Cross-role submission ownership and live dashboards

## Implemented
- Added safe SQLite migrations for `submitted_by_user_id` on proposals and sponsorships, plus submitter indexes.
- Proposal and sponsorship creation now records the authenticated account ID.
- Added authenticated `GET /api/me/proposals` (university-only) and `GET /api/me/sponsorships` (industry-only). These return only submissions created by the current account.
- University workspace now submits its proposal form to the backend and displays the account's saved proposals with challenge, status, and requested budget.
- Industry workspace now displays the account's saved sponsorships and computes its pledge total/count from backend records. It no longer presents the old hardcoded budget and sponsorship count as live account data.
- Existing disbursement, certificate, tax-report, and milestone actions remain clearly demo/prototype-only where no real backend workflow exists.

## Verification
- Backend unit tests: 36 passed.
- Python compilation, frontend inline JavaScript syntax, local references, and ZIP integrity are checked as part of this phase packaging.

## Important limitations
- Existing proposal/sponsorship records created before this migration have an empty submitter ID and therefore will not appear in a user's personal list; no ownership was guessed or backfilled by organization name.
- A proposal can be submitted only when the university account has an organization and email configured, and the challenge ID must exist.
- Industry pledge records are submissions/pledges, not verified transfers. Escrow, disbursement, official CSR/80G documents, and milestone proof persistence are not implemented by this phase.
- Full browser-based end-to-end testing was not available in this environment. This is an incremental integration phase, not a production-readiness certification.
