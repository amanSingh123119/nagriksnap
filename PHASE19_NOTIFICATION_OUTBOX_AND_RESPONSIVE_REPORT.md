# Phase 19 — Notification Outbox & Site-Wide Responsive Hardening

## Implemented
- Added a SQLite `notification_outbox` table with a unique deduplication key, delivery state, attempt count, timestamps, retry scheduling and last-error field.
- Complaint status transitions enqueue SMS intent in the same transaction as the status update and history event. No SMS network request runs inside the request transaction.
- Added `backend/scripts/process_notification_outbox.py`, a one-shot worker suitable for an external scheduler. It sends due items and retries failures with exponential backoff, capped at six hours and eight attempts.
- Removed the direct synchronous SMS send from the status-change route.
- Added conservative responsive CSS across shared site styles: fluid containers, responsive grids/forms, mobile workspace navigation, overflow-safe tables/media, touch targets, and narrow-phone adjustments.

## Operational notes
- Run the worker periodically via a scheduler after configuring the SMS provider: `python scripts/process_notification_outbox.py` from `backend/`. Without `FAST2SMS_API_KEY`, the existing SMS adapter simulates delivery; this must not be mistaken for a real SMS.
- Delivery is retryable, but an external SMS provider can accept a message while the worker loses its response; therefore strict exactly-once delivery cannot be guaranteed. Provider-side idempotency is not implemented.
- The outbox is currently SQLite-backed. Multi-worker production deployment requires a verified database migration and appropriate worker-claim semantics.
- CSS cannot replace device/browser testing. Responsive checks here are static; real-device and browser end-to-end tests remain outstanding.
- This project is not production-ready for sensitive citizen data; see the existing release gate.
