# NagrikSnap — Website Copy and Claims Audit (Phase 1)

## Purpose
NagrikSnap is an SIH prototype for problem statement 26043. Unless supported by a live integration and verifiable records, the website must not imply that it is an official government service, that partners have signed up, that money has moved, or that a field pilot has been authorised or completed.

## Changes made in Phase 1
- Added clear prototype notices to the homepage, challenges directory, government dashboard, CSR portal, admin portal, and case room.
- Relabelled homepage counters as illustrative demo values.
- Changed “Live Societal Challenges Hub” and “verified community challenges” wording to neutral prototype-directory wording.
- Replaced named CSR partner leaderboard entries and selected portal references with example partners and explicitly unverified sample amounts.
- Replaced the government authorization template’s official heading/signatory language with a sample-template disclaimer.
- Changed permit, endorsement, funding, certificate, annual report, and milestone actions so they no longer claim that an official decision, payment, certificate, or notification occurred.
- Changed the password-reset OTP message to state that no SMS/OTP is sent by the prototype.
- Clarified that complaint classification is rule-based prototype logic, not a trained AI model.
- Updated English SMS copy to explain that a provider integration is required.

## Remaining website text/data changes — next copy pass
1. **Homepage:** Replace hard-coded counter values with live aggregate API results; show “No verified data yet” when empty. Do not publish numeric claims until reconciled against database records.
2. **Challenges directory:** Audit every challenge card, district map marker, proposal count, pilot count, leaderboard score and funding amount. Seed records must carry a visible “Sample” badge and must never be mixed with verified records without a filter/label.
3. **CSR portal:** Remove remaining real company/person/registration references from sample rows, mentor profiles, sponsor cards, and any hard-coded escrow/grant figures unless permission and evidence are available. Separate pledged, approved, and disbursed amounts. No real transfer is made by current demo actions.
4. **University portal:** Label all sample university profiles, projects, grant requests, repository links, and field milestones. Do not imply a university has accepted a challenge unless an authenticated acceptance record exists.
5. **Government portal and admin:** Remove official-looking government branding, real officer names, official order references, seals/signature implications, and “certified/authorized” claims unless formally approved by the relevant authority. Use “review requested”, “decision pending”, “approved by [authorised role]” only when backed by an audit record.
6. **Case room:** Ensure sample messages are visibly labelled at the message level and never appear as actual partner communication. Load real messages only through authenticated API calls.
7. **Tracking and reviews:** Do not say “resolved”, “verified impact”, or “pilot solved” until an authorised reviewer records the outcome and supporting evidence. Explain who can change status and when a citizen can review a case.
8. **AI wording:** Use “rule-based preliminary category/priority suggestion” for current keyword logic. Do not claim semantic embeddings, model confidence, duplicate detection, voice AI, or AI accuracy unless implemented and evaluated. Show that humans review uncertain/high-impact cases.
9. **Notifications:** Search all translations and pages for SMS/email/instant/real-time claims. These should say “planned” or “requires provider integration” until delivery receipts are implemented and tested.
10. **Privacy and security:** Avoid absolute claims such as “fully secure”, “100% private”, or “government verified”. Publish a clear privacy notice only after the team has decided and implemented collection purpose, consent, retention, deletion, access, and contact details.
11. **Problem statement alignment:** Describe the product as a platform to crowdsource societal challenges and facilitate collaboration between citizens, universities, industry/CSR and government stakeholders. Do not claim official adoption, government partnership, statewide coverage, or deployment without evidence.
12. **Demo and presentation:** Keep a consistent “Prototype / sample data” label on every page with seeded records. In the live demo, explain which parts are connected to the backend and which are illustrative.

## Human verification required
- Confirm the official SIH problem statement wording and allowed use of department/state names and logos.
- Obtain written consent/permission before using any real person, university, company, government department or logo as a partner.
- Verify every real funding amount, CSR registration, certificate, field approval, pilot outcome, and impact metric with source documentation.
- Confirm notification, privacy, retention and complaint escalation policies with pilot stakeholders.

## Important note
These changes reduce misleading prototype claims; they do not make the system production-ready or certify legal/regulatory compliance. Security, data, integration, accessibility and deployment work remains tracked separately in the project reports and deployment checklist.
