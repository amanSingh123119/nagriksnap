# Phase 12 — Role-specific login foundation

## Implemented
- Expanded the login page to offer five distinct workspace choices: Citizen, Government, University, Industry, and Admin.
- Added role-specific descriptions and deep links using `login.html?role=...`.
- Login now checks that the authenticated backend role matches the selected workspace. Selecting a role does not grant that role.
- Successful login routes users to the matching workspace: citizen complaints, government portal, university portal, industry/CSR portal, or admin console.
- Citizen self-registration remains available only for citizens. Privileged accounts must be provisioned/approved through administrative processes.
- Added client-side route guards to the five private dashboard entry pages to improve navigation and reduce accidental cross-role access.
- Government accounts (`govt_admin`) now use the normal user-session storage key and are routed to the government portal, rather than the admin console.

## Security boundary
Client-side guards are a user-experience layer, not a security boundary. Backend authentication and per-endpoint authorization remain mandatory. The current app still has outstanding production requirements documented in the release checklist; this phase does not certify production readiness.

## Not included in this phase
- Full redesign of the public homepage.
- Standardized left-sidebar layout across all five dashboards.
- Live end-to-end browser testing against a deployed environment.
- PostgreSQL runtime migration and production deployment hardening.
