# Phase 25 — Live Milestone Workflow Report

## Delivered
- Case-room milestone list now reads persisted milestone records from `GET /api/challenges/{challenge_id}/milestones`.
- Participating authenticated roles can submit milestone title, update summary, progress percentage, status, and an optional evidence URL through the existing protected API.
- Frontend reports API failures rather than showing fake success, and refreshes the list only after a successful save.
- Milestone cards use DOM text nodes for user-provided content and clamp displayed progress to 0–100.
- Backend rejects blank titles, out-of-range progress (existing validation), and evidence URLs not beginning with HTTP(S).
- Removed the illustrative escrow amount/partner claim and clarified that pledges are not payments and escrow/tranche release is not implemented.
- Added regression tests ensuring citizen accounts cannot create milestones and `javascript:` evidence URLs are rejected.

## Verification
- `python -m unittest discover -s tests -v`: 38 tests passed.
- Python compilation, inline JavaScript syntax checks, local asset/link checks, and ZIP integrity checked before packaging.

## Known limitations
- Milestone records are append-only progress updates; editing/deleting existing milestones and formal government evidence approval are not implemented.
- Evidence is a URL reference, not an uploaded or scanned evidence artifact.
- No escrow, payment transfer, CSR tranche release, or official pilot certification is implemented.
- Browser-driven end-to-end tests were not run in this environment.
