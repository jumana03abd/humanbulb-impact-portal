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
- `ALLOWED_STAFF_EMAIL_DOMAINS`
- optionally `ALLOWED_STAFF_EMAILS` for individual allowlisting

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

## Production Deployment

1. Deploy the FastAPI app to your Python host.
2. Set production environment variables.
3. Set `SESSION_COOKIE_SECURE=true`.
4. Point your domain to the FastAPI app.
5. Ensure the Supabase database schema and storage buckets exist.
6. Restrict service-role credentials to the backend only.
7. Set `PORTAL_ORGANIZATION_NAME`, `PORTAL_ORGANIZATION_SLUG`, and the HUMANBULB staff email allowlist variables in production.

## Notes

- Spreadsheet uploads support `.csv` and `.xlsx`.
- File validation happens both client-side and server-side.
- Quantitative metrics are computed in Python, not by AI.
- The OpenAI API is used only for qualitative narrative generation.
- Approved users are automatically attached to the single configured HUMANBULB organization, and every project/upload/report query remains scoped to that organization.
