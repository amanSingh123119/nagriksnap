# Phase 22 — Account security, email and integration audit

## Implemented in this phase
- Added a normalized email field to citizen accounts and a uniqueness index for non-empty email addresses. Existing accounts need their email populated before email recovery can work.
- Citizen registration now requires an email address.
- Added configurable SMTP delivery for new-login notices. Delivery is best-effort and does not block login if SMTP is unavailable.
- Added server-side email OTP password reset: 6-digit code, 10-minute expiry, attempt counter, single-use token, Argon2 password hashing, and revocation of existing sessions after reset.
- Updated the login page to request OTP by registered email and submit the reset confirmation.
- Added SMTP variables to `backend/.env.example`.

## Cross-role data flow audit
The project has a shared backend/database for complaints, status history, proposals, sponsorships, case-room and collaboration records. The current phase does not certify every module as fully connected end-to-end; role permissions, entity ownership and UI workflows still require a systematic endpoint-by-endpoint audit and browser testing.

## Configuration required for real email
Set SMTP_HOST, SMTP_PORT, SMTP_STARTTLS, SMTP_USERNAME, SMTP_PASSWORD and SMTP_FROM using a real email provider. Keep secrets out of source control. Confirm SPF/DKIM/DMARC and provider sending limits before production. Login notices are best-effort.

## Important limitations / release blockers
- Existing users without a stored email cannot use email reset until a secure email verification/update workflow is completed.
- Registration email is not yet verified via a separate confirmation link/OTP; do not treat an entered email as verified.
- Admin environment account currently has no registered email lookup for password reset or login notification.
- SMTP delivery was not tested against a real provider because credentials are not supplied.
- Project remains SQLite-based; prior production release gate explicitly blocks production mode until PostgreSQL persistence and private evidence storage are verified.
- Full browser end-to-end tests across citizen, government, university, industry and admin roles remain outstanding.
