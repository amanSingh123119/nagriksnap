# NagrikSnap — Brutal Website Review (Phase 11)

## Scope and caveat
This is a source-code and project-documentation review of the ZIP provided for Phase 10. It is not a live-hosted website test, user study, penetration test, or verification of claims about the SIH problem statement. Ratings below are practical engineering judgments, not measured benchmarks.

## Short verdict
**Prototype/demo readiness: 6/10. Production readiness for real citizen data: 2/10 (not approved for launch).** The product concept and breadth are promising, but the integration, data governance, operations, and end-to-end evidence are not yet at the level required for a public civic platform.

## Scorecard
| Area | Rating | Evidence-based assessment |
|---|---:|---|
| Problem/product concept | 8/10 | Clear citizen-to-university/industry/government collaboration loop. |
| UI and feature breadth | 7/10 | Multiple role-oriented pages and workflows exist; visual polish is not proof of workflow correctness. |
| Frontend/backend integration | 5/10 | Shared API wiring and many API routes exist, but not every page and role journey has automated browser-level proof. |
| Core workflow completeness | 5/10 | Complaint, proposal, sponsorship, case-room and collaboration paths exist; notification and approval lifecycle gaps remain. |
| Data architecture | 3/10 | SQLite persistence remains; migration utility is not a PostgreSQL application adapter. |
| Evidence/file handling | 4/10 | Storage abstraction exists, but production cloud configuration, access policies, lifecycle and recovery are unverified. |
| Security and privacy | 3/10 | Some auth, session, role checks and rate limiting exist; independent review and complete production controls are outstanding. |
| Analytics and trustworthiness | 4/10 | Filters/export and dashboards exist, but metrics need validation; pledges must not be represented as paid funds. |
| Testing/release confidence | 4/10 | Backend regression tests and syntax checks are useful; no complete deployed end-to-end suite or independent pen test. |
| Production operations | 2/10 | Backups/restore, monitoring, alerting, incident response, secrets management and live staging cutover are not proven. |

## What is genuinely good
- The product has a coherent multi-stakeholder premise rather than being only a complaint form.
- The project has a broad set of screens and backend routes for complaints, proposals, sponsorships, collaboration and administration.
- The codebase has a growing regression suite, reports, and explicit release-gate documentation.
- The production startup safeguard is the right default while critical controls are incomplete.

## The blunt problems
1. **A migration script is not a PostgreSQL migration.** `backend/database.py` still imports `sqlite3`, uses SQLite PRAGMA/`executescript`, `?` placeholders and SQLite-specific seed SQL. The running application has not been ported to PostgreSQL.
2. **“Feature exists” is not “feature works end-to-end.”** Each workflow needs browser tests across role, API, database and failure cases.
3. **Storage abstraction is not a secured production storage deployment.** Bucket policies, encryption, signed URL expiry, malware/content checks, retention/deletion, backup and recovery must be configured and tested.
4. **Civic data is sensitive.** Precise location, phone numbers, complaint narratives and uploaded images require data minimization, retention rules, access logging, consent/notice, deletion and incident procedures.
5. **AI/matching needs clear limits.** Keyword matching is advisory, not semantic or independently validated. Users need correction paths and humans must make assignment decisions.
6. **Dashboard figures need definitions.** Distinguish funding pledged from disbursed, define time windows, document source-of-truth and reconcile figures against underlying records.
7. **Demo content can damage credibility.** Clearly label synthetic sample organizations, messages, pilots, permits, impact results and certificates; do not imply real government or institutional endorsement without evidence.
8. **Operational readiness is missing evidence.** There is no verified production restore drill, monitoring/alerting exercise, incident response runbook, or independent security sign-off in the supplied project.

## Release blockers (must close before real citizen data)
- [ ] Implement PostgreSQL as the actual application database adapter, not only a migration script.
- [ ] Create versioned migrations and test a sanitized staging migration, row reconciliation, constraints, indexes, identity behavior and rollback.
- [ ] Run role-by-route authorization tests and end-to-end browser tests for citizen, government, university, industry and admin journeys.
- [ ] Deploy private object storage with encryption, least-privilege access, expiring downloads, upload validation, retention and deletion.
- [ ] Configure encrypted database/object backups and demonstrate restoration to a clean environment.
- [ ] Add shared rate limiting for multi-instance deployments, secret management, TLS/proxy hardening, monitoring, alerts and audit-log retention.
- [ ] Complete privacy/legal review, threat model, dependency and secret scans, and independent penetration testing.
- [ ] Verify every public-facing claim and every dashboard metric against evidence.
- [ ] Obtain explicit operational owner sign-off and keep the production gate enabled until all blockers pass.

## Recommended next order
1. PostgreSQL adapter + versioned schema migrations.
2. Automated API integration tests against a real disposable PostgreSQL instance.
3. Browser end-to-end tests for the critical journeys.
4. Production object storage, backup/restore and deletion tests.
5. Security/privacy review and staging release rehearsal.

## Current launch decision
**NO-GO for real citizen data.** Continue with synthetic/demo data only. This is not a claim that the project is unusable; it means the evidence required for a public production civic service has not yet been established.
