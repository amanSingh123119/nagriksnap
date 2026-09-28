# P4 — Impact Dashboard & Government Analytics

## Delivered
- Added `GET /api/admin/impact-analytics`, restricted to `admin` and `govt_admin` sessions.
- Returns aggregate-only metrics: total/active/resolved challenges, resolution rate, proposals and acceptance rate, recorded sponsorship totals and status breakdown, review rating/impact, university profile count, status, priority, department, monthly, structured-district, task and milestone breakdowns.
- Added an Impact Analytics tab with aggregate KPI cards, charts, date/district/department filters, CSV export, refresh, loading/error states and last-updated timestamp. Filters apply to complaint metrics only; proposal, sponsorship, review, university and collaboration totals are explicitly all-time.
- The analytics response intentionally excludes citizen names, phone numbers, evidence URLs and complaint-level records.
- Added regression tests for authentication/authorization and aggregate-only output.

## Data interpretation notes
- Added a structured `district` field and migration for existing SQLite databases. New complaint submissions can provide district explicitly. Existing historical rows remain blank until a human validates and backfills them; do not infer official district values from free-text addresses.
- Monthly trend groups by the first seven characters of `created_at`; historical records without a valid timestamp are omitted.
- Resolution rate treats `Resolved`, `Pilot Deployed` and `Closed` as resolved states. Confirm this definition with the pilot authority before operational use.
- Funding metrics reflect recorded pledge amounts grouped by recorded status. Status labels are not proof of approval or disbursement; disbursed funding must not be claimed until a separately verified disbursement field and evidence workflow exist.
- Existing demo/sandbox sections and certificate actions elsewhere in the government portal are still prototype content and must not be represented as actual government authorizations.

## Run tests
From `nagriksnap_p0/backend`:

```bash
python -m unittest discover -s tests -v
```

The dashboard API requires a logged-in `admin` or `govt_admin` account. Frontend fetch uses the existing authenticated-fetch wrapper, which attaches the backend-issued bearer token for the local API URL.


## Phase 4 implementation addendum
- Added query parameters `date_from`, `date_to`, `district`, and `department` to the protected analytics endpoint, with ISO date validation and reversed-range rejection.
- Resolution-rate definition is returned with the response: Resolved, Pilot Deployed, and Closed divided by all filtered challenges; Rejected is not counted as resolved. This is a proposed product definition and still requires pilot-authority approval.
- CSV export includes active filters, complaint breakdowns, all-time totals, and recorded sponsorship-status amounts.
- Added explicit district entry to the citizen submission form. Historical districts require human validation/backfill.
- Reworded sample GIS download and official citation actions so they do not claim that a dataset or official certificate was generated.
