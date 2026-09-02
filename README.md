# HUMANBULB Impact Portal

This project preserves the original multi-page frontend prototype and adds a Python FastAPI backend for authentication, uploads, data processing, narrative generation, and PDF export.

## Current Architecture

- Frontend: static HTML/CSS/JavaScript pages already designed for `admin`, `dashboard`, `analytics`, and `grant-summary`
- Backend: FastAPI app in `backend/`
- Database: Supabase PostgreSQL
- Auth: Supabase Auth, mediated through backend session cookies, with HUMANBULB staff-only access controls
- File storage: Supabase private storage buckets
- Spreadsheet processing: `pandas` + `openpyxl`
- PDF generation: ReportLab
- Qualitative narrative generation: OpenAI API from the server only

## Screens That Previously Used Mock Data

These screens were previously driven by `portalData` in `app.js` and should now use backend API data:

- `admin.html`
  - Mock upload counts
  - Mock cohort-size state
- `dashboard.html`
  - Mock metric cards
  - Mock objective cards
- `analytics.html`
  - Mock before/after chart values
  - Mock distribution chart values
  - Mock delta list
- `grant-summary.html`
  - Mock narrative
  - Mock quote
  - Mock metric summary
  - Browser `print()` export instead of real PDF generation

## Local Development

1. Create a Python virtual environment.
2. Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Copy the environment template:

```bash
cp .env.example .env
```

4. Fill in:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `DATABASE_URL`
- `OPENAI_API_KEY`
- `ALLOWED_STAFF_EMAILS` for the exact HUMANBULB staff accounts that can access the portal
- optionally `ALLOWED_STAFF_EMAIL_DOMAINS` only if you want domain-wide fallback access

5. Apply the schema in Supabase SQL editor:

```sql
-- paste supabase_schema.sql
```

6. Create private Supabase storage buckets:

- `portal-uploads`
- `portal-reports`

7. Run the app:

```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

8. Open:

```text
http://127.0.0.1:8000/login.html
```

9. Run the local regression suite:

```bash
python -m unittest discover -s tests
```

GitHub Actions runs the same regression suite and JavaScript syntax check on every push and pull request.

## Locked Upload Schemas

The portal now validates spreadsheet uploads against explicit schema rules before analysis begins.

- `Week 1 Pre-Survey`
  - Required: participant identifier, clean tech knowledge, interview confidence, workplace readiness
  - Optional: resume readiness, career clarity, LinkedIn completion, program completion, testimonial text
- `Weekly Check-In Surveys`
  - Required: participant identifier, week/check-in marker, reflection or response text
- `Week 8 Post-Survey`
  - Required: participant identifier, clean tech knowledge, interview confidence, workplace readiness
  - Optional: resume readiness, career clarity, LinkedIn completion, program completion, testimonial text
- `Deliverables Tracker`
  - Required: intern/participant name, project or initiative, completion/status
- `Resume & LinkedIn Completion Tracker`
  - Required: intern/participant name, resume status, LinkedIn status
- `Testimonials`
  - Required: participant identifier, testimonial or quote text
- `Photos`
  - Direct image and PDF uploads are allowed
  - Optional spreadsheet metadata uploads may also be used, but must include a photo filename, URL, or file reference column

The backend accepts common naming variations for each required field, but every spreadsheet must include one match for each required schema item.

## Production Deployment

The repository includes a `Dockerfile` for any container host. It listens on the host-provided `PORT` and falls back to `8000` locally. The root `.python-version` pins native Python hosts such as Render to Python `3.12.10`, matching the tested local and CI runtime.

1. Build and test the image locally:

```bash
docker build -t humanbulb-impact-portal .
docker run --rm --env-file .env -p 8000:8000 humanbulb-impact-portal
```

2. Deploy the container image and configure a health check at `/health`; a `200` response confirms that required application settings loaded and Supabase PostgreSQL is reachable.
3. Set production environment variables, including `SESSION_COOKIE_SECURE=true` and `APP_BASE_URL` to the public HTTPS URL.
4. Ensure the Supabase database schema and private storage buckets exist.
5. Restrict service-role credentials to the backend only.
6. Set `PORTAL_ORGANIZATION_NAME`, `PORTAL_ORGANIZATION_SLUG`, and the HUMANBULB staff email allowlist variables in production.

## Staging Smoke Test

Run the real end-to-end workflow only against a dedicated, empty staging portal. The runner signs in as an approved staging staff account, uploads synthetic data, generates dashboard analytics and a PDF, then removes the test uploads and report. It intentionally refuses to run unless all safeguards are set:

```bash
export SMOKE_TEST_ENV=staging
export SMOKE_TEST_CONFIRM=run-staging-smoke
export SMOKE_TEST_BASE_URL=https://your-staging-portal.example.org
export SMOKE_TEST_EMAIL=staging-smoke-test@humanbulb.org
export SMOKE_TEST_PASSWORD='your-staging-password'
python3 scripts/staging_smoke_test.py
```

Run this only against a dedicated staging portal and staging staff account. Staff can download or delete the latest saved PDF from the Grant Summary screen.

## Notes

- Spreadsheet uploads support `.csv` and `.xlsx`.
- File validation happens both client-side and server-side.
- Quantitative metrics are computed in Python, not by AI.
- The OpenAI API is used only for qualitative narrative generation.
- Approved users are automatically attached to the single configured HUMANBULB organization, and every project/upload/report query remains scoped to that organization.
- If `ALLOWED_STAFF_EMAILS` is populated, only those exact email addresses can sign in. Domain matching is used only when the exact-email allowlist is empty.
