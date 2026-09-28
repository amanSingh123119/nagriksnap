# Phase 16 — Account-linked complaint ownership

## Implemented
- Added nullable `complaints.owner_user_id` with a safe SQLite column migration; legacy/anonymous reports remain unowned rather than being guessed or automatically assigned.
- Complaint submission accepts an optional bearer session. If supplied, the session must belong to a signed-in citizen account; the authenticated account ID is written by the server, never accepted from a form field. Anonymous public submissions remain supported and are not account-linked.
- Added `GET /api/me/complaints`, requiring an authenticated citizen account. It returns only records whose `owner_user_id` matches the current session's account ID and omits contact/assignment ownership fields from the response.
- Updated the Citizen “My Complaints” page to use this account-scoped API instead of downloading the public challenge feed and filtering IDs in browser storage.
- Added a regression test covering unauthenticated access, cross-account isolation, and omission of phone data.

## Verification
Backend unit tests, Python compilation, inline JavaScript syntax checks, local-link checks, and ZIP integrity were run for this phase. See the test output from the build run for exact results.

## Limitations / follow-up
- Anonymous reports and older records without an owner remain outside “My Complaints”; no phone-number-based auto-linking is performed because it would be unsafe to infer ownership.
- This repository still uses SQLite and has an explicit production launch gate. Do not use real sensitive citizen data until database migration, deployment controls, privacy review, backups/recovery, and end-to-end testing are completed.
- A tracking ID remains a public tracking reference; it is not a substitute for account authorization.
