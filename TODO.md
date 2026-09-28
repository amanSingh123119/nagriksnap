# SIH 2026 Problem Statement #26043 — Project Progress Tracker

## 🌟 Quadruple Helix Model (SIH 26043 Compliance)
1. [x] **Citizens Crowdsourcing**: Photo, GPS geo-tagging, Hindi/English speech-to-text, and AI duplicate detection & citizen upvoting banner.
2. [x] **AI Scoping & Triaging Engine**: Automatic categorization, UN SDG mapping, urgency index rating, and recommended engineering tech stacks.
3. [x] **University Innovation Hub (`challenges.html`)**: Proposal submission modal, GitHub demo link repository, and university innovation leaderboard ranking.
4. [x] **Jharkhand GIS Geo-Heatmap (`challenges.html`)**: Interactive Leaflet map with 24 district challenge pinpoints (Ranchi, Jamshedpur, Dhanbad, Bokaro, Palamu, etc.).
5. [x] **Industry & CSR Grant Escrow**: CSR grant pledge portal, milestone tranche tracking, and 80G / CSR-1 tax receipt downloads.
6. [x] **Multi-Party Case Room (`caseroom.html`)**: 3-column live collaborative workspace with real-time stakeholder messaging, milestone progress bars, and official problem dossier export.
7. [x] **Command Center & Governance (`admin.html`)**: 3-role views (Govt Admin, University Bids, CSR Escrow), lifecycle status transitions, sandbox authorizations, and PDF exports.
8. [x] **1-Click Hackathon Role Launcher (`login.html`)**: Instant demo access for Judges to test any stakeholder role (Govt, University, Industry, Citizen).

## 🚀 All Features Operational & Hackathon-Ready!


## P4 analytics follow-up (implementation update)
- [x] Add structured district field and safe SQLite column migration.
- [x] Add district field to citizen submission form/API.
- [x] Add date, district and department filters for complaint analytics.
- [x] Add CSV export and explicit all-time scope note for non-complaint metrics.
- [x] Show recorded sponsorship totals by status without claiming disbursement.
- [x] Document the resolution-rate definition and historical-data caveat.
- [ ] Human: validate/backfill historical district values from trusted sources.
- [ ] Human: approve the resolution-rate definition with pilot authority.
- [ ] Implement verified approval/disbursement amount fields and evidence before reporting actual disbursements.
- [ ] Add database-backed dropdown options for districts/departments and browser end-to-end tests.


## Phase 5 — Session security
- [x] Configurable session lifetime with production cap
- [x] Account-wide session revocation endpoint
- [x] Regression tests for session revocation isolation
- [ ] Add user-facing “sign out all devices” control
- [ ] Complete PostgreSQL migration and production infrastructure hardening

## Phase 7 — Frontend/backend integration audit
- [x] Replace hard-coded localhost API URLs in login, reviews, government analytics, university profile/matching, reviews helper, and chatbot with shared same-origin-aware API base.
- [x] Attach bearer tokens to same-origin requests through the authenticated fetch wrapper.
- [x] Document route-to-feature integration status and remaining blockers in `PHASE7_FRONTEND_BACKEND_INTEGRATION_AUDIT.md`.
- [ ] Run live browser smoke tests for each role against a deployed staging API.
- [ ] Implement PostgreSQL persistence and migration/rollback tests before production.
- [ ] Move evidence uploads to private object storage and test authorization, retention, malware scanning and deletion.
