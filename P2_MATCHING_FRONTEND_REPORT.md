# Phase 2 — University Matching Frontend Integration

## Implemented
- Added a government-reviewer **University Matching** tab.
- The tab loads challenge records from `GET /api/challenges`, lets a reviewer select a challenge, and requests ranked profiles from `GET /api/challenges/{challenge_id}/matches`.
- Displays score out of 100, expertise, available slots, update time, matched reasons, loading/error/empty states, refresh, and a minimum-score filter.
- Clearly explains that the ranking is a deterministic keyword-based heuristic, not an AI probability, official ranking, assignment, or guarantee.
- Added a university profile editor for expertise, SDG focus, prior project count, available slots, districts and HTTPS website.
- Added `GET /api/university/profile`, restricted to the signed-in university role and returning only that account's profile.
- Extended regression coverage for reading the current university's profile and denying citizens access.

## Verification performed
- Backend regression suite: 15 tests passed.
- Python backend compilation: passed.
- Inline JavaScript syntax checks for government and university portals: passed.
- ZIP integrity check: run after packaging.

## Known limits / human and later work
- Matching remains explainable keyword overlap, capacity, past project count and district text. It is not semantic AI and the score must not be presented as a probability.
- Only approved university accounts can save profiles; a human administrator must verify the organisation and its claims.
- Challenge list is paginated; this screen loads the first 100 records. Add server-side search/filtering if the pilot has more.
- District matching currently compares text against the challenge address. Structured district IDs and validated geography should be implemented in a later data-quality phase.
- Frontend API base URL follows the project's existing `http://localhost:8000` convention. Configure environment-specific API URLs before deployment.
- No university is automatically assigned; an authorised human must review profiles and proposals.
