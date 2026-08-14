from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .auth import (
    AuthenticatedUser,
    SupabaseAuthClient,
    assert_humanbulb_staff_email,
    authenticate_request,
    clear_session_cookies,
    ensure_membership,
    set_session_cookies,
)
from .config import get_settings
from .schemas import (
    AnalyticsResponse,
    CohortSizeRequest,
    ReportingPeriodRequest,
    DashboardResponse,
    GrantSummaryResponse,
    LoginRequest,
    ProjectStateResponse,
    ProjectSummary,
    SetupProgress,
    SignupRequest,
    UserSession,
)
from .services import (
    analyze_project,
    build_component_state,
    build_setup_progress,
    delete_upload,
    derive_project_status,
    ensure_analysis,
    generate_and_store_report,
    get_or_create_current_project,
    get_saved_analysis,
    list_uploads,
    save_upload,
    set_project_status,
    update_cohort_size,
    update_reporting_period,
)
from .storage import StorageClient


settings = get_settings()
ROOT_DIR = Path(__file__).resolve().parents[1]

app = FastAPI(title="HUMANBULB Impact Portal API")


@app.on_event("startup")
async def ensure_reporting_period_column() -> None:
    """Create the reporting-period column when the local app boots."""
    from .db import execute

    execute(
        """
        alter table projects
        add column if not exists reporting_period text not null default ''
        """
    )


@app.get("/health")
async def health() -> dict[str, str]:
    """Expose a lightweight health check for local and deployed environments."""
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """Send root traffic to the login entrypoint for the static frontend."""
    return RedirectResponse(url="/login.html")


async def protected_page(path: str, request: Request) -> FileResponse:
    """Serve a static page only after verifying the session cookie."""
    await authenticate_request(request)
    return FileResponse(ROOT_DIR / path)


def serialize_project_summary(project: dict) -> ProjectSummary:
    """Normalize database rows so UUID-backed ids always serialize as strings."""
    serialized = dict(project)
    for key in ("id", "organization_id"):
        if key in serialized and serialized[key] is not None:
            serialized[key] = str(serialized[key])
    return ProjectSummary(**serialized)


def build_project_state_payload(user: AuthenticatedUser, project: dict) -> dict:
    """Build the admin workspace payload consumed by the setup screen."""
    uploads = list_uploads(project["id"], user.organization_id)
    setup_components = build_component_state(uploads)
    has_analysis = get_saved_analysis(project["id"], user.organization_id) is not None
    setup_progress = build_setup_progress(project, uploads)
    status_value = derive_project_status(project["id"], user.organization_id, setup_progress["is_complete"], has_analysis)
    project["status"] = status_value
    setup_progress["analysis_status"] = status_value
    return {
        "user": UserSession(
            user_id=str(user.user_id),
            email=user.email,
            organization_id=str(user.organization_id),
            organization_name=user.organization_name,
        ),
        "project": serialize_project_summary(project),
        "setup_components": setup_components,
        "setup_progress": SetupProgress(**setup_progress),
    }


@app.post("/api/auth/login")
async def login(payload: LoginRequest, response: Response) -> dict[str, str]:
    """Authenticate an approved staff member and establish portal cookies."""
    assert_humanbulb_staff_email(payload.email)
    session = await SupabaseAuthClient(settings).sign_in(payload.email, payload.password)
    access_token = session.get("access_token")
    refresh_token = session.get("refresh_token")
    user_data = session.get("user") or {}
    if not access_token or not user_data.get("id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unable to create session.")
    ensure_membership(user_data["id"], payload.email)
    set_session_cookies(response, access_token, refresh_token)
    return {"status": "ok"}


@app.post("/api/auth/signup")
async def signup(payload: SignupRequest, response: Response) -> dict[str, str]:
    """Create a first-time portal account for an allowlisted HUMANBULB staff email."""
    assert_humanbulb_staff_email(payload.email)
    session = await SupabaseAuthClient(settings).sign_up(
        payload.email,
        payload.password,
        {"full_name": payload.full_name or "", "organization_name": settings.portal_organization_name},
    )
    user_data = session.get("user") or {}
    if not user_data.get("id"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to create account.")
    access_token = session.get("session", {}).get("access_token")
    refresh_token = session.get("session", {}).get("refresh_token")
    ensure_membership(user_data["id"], payload.email)
    if access_token:
        set_session_cookies(response, access_token, refresh_token)
    return {"status": "ok"}


@app.post("/api/auth/logout")
async def logout(response: Response) -> dict[str, str]:
    """Clear the session cookies so the current staff user is signed out."""
    clear_session_cookies(response)
    return {"status": "ok"}


@app.get("/api/auth/me", response_model=UserSession)
async def me(user: AuthenticatedUser = Depends(authenticate_request)) -> UserSession:
    """Return the currently authenticated staff session for frontend bootstrapping."""
    return UserSession(
        user_id=str(user.user_id),
        email=user.email,
        organization_id=str(user.organization_id),
        organization_name=user.organization_name,
    )


@app.get("/api/projects/current", response_model=ProjectStateResponse)
async def current_project(user: AuthenticatedUser = Depends(authenticate_request)) -> ProjectStateResponse:
    """Return the current organization project and admin setup progress."""
    project = get_or_create_current_project(user)
    return ProjectStateResponse(**build_project_state_payload(user, project))


@app.post("/api/projects/current/cohort-size")
async def save_cohort_size(payload: CohortSizeRequest, user: AuthenticatedUser = Depends(authenticate_request)) -> dict[str, object]:
    """Persist the cohort size entered on the setup workspace page."""
    project = get_or_create_current_project(user)
    update_cohort_size(project["id"], user.organization_id, payload.cohort_size)
    project["cohort_size"] = payload.cohort_size
    return build_project_state_payload(user, project)


@app.post("/api/projects/current/reporting-period")
async def save_reporting_period(payload: ReportingPeriodRequest, user: AuthenticatedUser = Depends(authenticate_request)) -> dict[str, object]:
    """Persist the reporting period entered on the setup workspace page."""
    project = get_or_create_current_project(user)
    reporting_period = payload.reporting_period.strip()
    update_reporting_period(project["id"], user.organization_id, reporting_period)
    project["reporting_period"] = reporting_period
    return build_project_state_payload(user, project)


@app.post("/api/projects/current/uploads")
async def upload_project_file(
    component: str = Form(...),
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(authenticate_request),
) -> dict[str, object]:
    """Accept an uploaded program source file and return refreshed setup state."""
    project = get_or_create_current_project(user)
    await save_upload(user, project, component, file)
    return build_project_state_payload(user, project)


@app.delete("/api/projects/current/uploads/{upload_id}")
async def remove_project_upload(upload_id: str, user: AuthenticatedUser = Depends(authenticate_request)) -> dict[str, object]:
    """Delete an uploaded source file and refresh the admin workspace state."""
    project = get_or_create_current_project(user)
    await delete_upload(user, project, upload_id)
    return build_project_state_payload(user, project)


@app.post("/api/projects/current/analyze")
async def trigger_analysis(user: AuthenticatedUser = Depends(authenticate_request)) -> dict[str, str]:
    """Run spreadsheet-based analysis once the required setup inputs are present."""
    project = get_or_create_current_project(user)
    uploads = list_uploads(project["id"], user.organization_id)
    setup_progress = build_setup_progress(project, uploads)
    if not setup_progress["is_complete"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Complete the cohort size entry and all required uploads before generating the dashboard.",
        )
    set_project_status(project["id"], user.organization_id, "analyzing")
    await analyze_project(user, project)
    return {"status": "ok"}


@app.get("/api/projects/current/dashboard", response_model=DashboardResponse)
async def dashboard(user: AuthenticatedUser = Depends(authenticate_request)) -> DashboardResponse:
    """Return the high-level impact dashboard metrics and target summaries."""
    project = get_or_create_current_project(user)
    analysis = await ensure_analysis(user, project)
    return DashboardResponse(
        project=serialize_project_summary(project),
        metrics=analysis["metrics"],
        grantObjectives=analysis["objectives"],
        sources=analysis["sources"],
        featuredPhotos=analysis.get("featured_photos", []),
        last_calculated_at=analysis.get("calculated_at"),
    )


@app.get("/api/projects/current/analytics", response_model=AnalyticsResponse)
async def analytics(user: AuthenticatedUser = Depends(authenticate_request)) -> AnalyticsResponse:
    """Return the detailed before/after analytics used by the comparison page."""
    project = get_or_create_current_project(user)
    analysis = await ensure_analysis(user, project)
    return AnalyticsResponse(
        project=serialize_project_summary(project),
        beforeAfter=analysis["before_after"],
        distribution=analysis["distribution"],
        deltas=analysis["deltas"],
        analyst_notes=analysis["analyst_notes"],
        matched_response_count=analysis["summary"]["matched_response_count"],
    )


@app.get("/api/projects/current/grant-summary", response_model=GrantSummaryResponse)
async def grant_summary(user: AuthenticatedUser = Depends(authenticate_request)) -> GrantSummaryResponse:
    """Return the narrative, metrics, and quote used in the grant summary view."""
    project = get_or_create_current_project(user)
    analysis = await ensure_analysis(user, project)
    from .db import fetch_one

    latest_report = fetch_one(
        """
        select id, created_at
        from reports
        where project_id = %s and organization_id = %s and type = 'grant_summary_pdf'
        order by created_at desc
        limit 1
        """,
        (project["id"], user.organization_id),
    )
    pdf_download_url = f"/api/reports/{latest_report['id']}/download" if latest_report else None
    return GrantSummaryResponse(
        project=serialize_project_summary(project),
        metrics=[{"value": item["value"], "label": item["label"].lower()} for item in analysis["metrics"][:4]],
        objectives=analysis["objectives"],
        quote=analysis["selected_quote"],
        quotes=analysis.get("quotes", [])[:3],
        narrative=analysis["grant_narrative"],
        executive_summary=analysis["executive_summary"],
        featuredPhotos=analysis.get("featured_photos", []),
        report_id=latest_report["id"] if latest_report else None,
        pdf_download_url=pdf_download_url,
        generated_at=latest_report["created_at"] if latest_report else analysis.get("calculated_at"),
    )


@app.get("/api/projects/current/uploads/{upload_id}/asset/{asset_index}")
async def project_upload_asset(upload_id: str, asset_index: int, user: AuthenticatedUser = Depends(authenticate_request)) -> StreamingResponse:
    """Stream one protected featured-photo asset from the active project uploads."""
    from .db import fetch_one

    project = get_or_create_current_project(user)
    row = fetch_one(
        """
        select storage_path, content_type, parsed_summary
        from project_uploads
        where id = %s and project_id = %s and organization_id = %s
        limit 1
        """,
        (upload_id, project["id"], user.organization_id),
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload asset not found.")

    summary = row.get("parsed_summary") or {}
    featured_images = summary.get("featured_images") or []
    if asset_index < 0 or asset_index >= len(featured_images):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload asset not found.")

    asset = featured_images[asset_index]
    payload = await StorageClient(settings).download_bytes(settings.supabase_bucket_uploads, asset["storage_path"])
    media_type = asset.get("content_type") or row.get("content_type") or "application/octet-stream"
    return StreamingResponse(iter([payload]), media_type=media_type)


@app.post("/api/projects/current/grant-summary/pdf")
async def build_pdf(user: AuthenticatedUser = Depends(authenticate_request)) -> dict[str, str]:
    """Generate and persist the latest grant-summary PDF for download."""
    project = get_or_create_current_project(user)
    analysis = await ensure_analysis(user, project)
    record = await generate_and_store_report(user, project, analysis)
    return {"report_id": record["id"], "download_url": f"/api/reports/{record['id']}/download"}


@app.get("/api/reports/{report_id}/download")
async def download_report(report_id: str, user: AuthenticatedUser = Depends(authenticate_request)) -> StreamingResponse:
    """Stream a previously generated PDF report back to the signed-in staff user."""
    from .db import fetch_one

    report = fetch_one(
        """
        select storage_path
        from reports
        where id = %s and organization_id = %s
        """,
        (report_id, user.organization_id),
    )
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    payload = await StorageClient(settings).download_bytes(settings.supabase_bucket_reports, report["storage_path"])
    return StreamingResponse(iter([payload]), media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="humanbulb-grant-summary.pdf"'})


@app.get("/login.html", include_in_schema=False)
async def login_page() -> FileResponse:
    """Serve the public login shell for staff authentication."""
    return FileResponse(ROOT_DIR / "login.html")


@app.get("/index.html", include_in_schema=False)
async def index_page(request: Request) -> FileResponse:
    """Serve the protected landing page after authentication."""
    return await protected_page("index.html", request)


@app.get("/admin.html", include_in_schema=False)
async def admin_page(request: Request) -> FileResponse:
    """Serve the protected admin setup workspace."""
    return await protected_page("admin.html", request)


@app.get("/dashboard.html", include_in_schema=False)
async def dashboard_page(request: Request) -> FileResponse:
    """Serve the protected impact dashboard page shell."""
    return await protected_page("dashboard.html", request)


@app.get("/analytics.html", include_in_schema=False)
async def analytics_page(request: Request) -> FileResponse:
    """Serve the protected before-and-after analytics page shell."""
    return await protected_page("analytics.html", request)


@app.get("/grant-summary.html", include_in_schema=False)
async def grant_page(request: Request) -> FileResponse:
    """Serve the protected grant summary and PDF export page shell."""
    return await protected_page("grant-summary.html", request)


app.mount("/", StaticFiles(directory=ROOT_DIR, html=True), name="static")
