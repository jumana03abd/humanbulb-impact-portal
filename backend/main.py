from __future__ import annotations

import json
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .auth import AuthenticatedUser, SupabaseAuthClient, authenticate_request, clear_session_cookies, ensure_membership, set_session_cookies
from .config import get_settings
from .schemas import (
    AnalyticsResponse,
    CohortSizeRequest,
    DashboardResponse,
    GrantSummaryResponse,
    LoginRequest,
    ProjectStateResponse,
    ProjectSummary,
    SignupRequest,
    UserSession,
)
from .services import (
    COMPONENT_CONFIG,
    analyze_project,
    build_component_state,
    ensure_analysis,
    generate_and_store_report,
    get_or_create_current_project,
    get_saved_analysis,
    list_uploads,
    save_upload,
    update_cohort_size,
)
from .storage import StorageClient


settings = get_settings()
ROOT_DIR = Path(__file__).resolve().parents[1]

app = FastAPI(title="HUMANBULB Impact Portal API")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/login.html")


async def protected_page(path: str, request: Request) -> FileResponse:
    await authenticate_request(request)
    return FileResponse(ROOT_DIR / path)


@app.post("/api/auth/login")
async def login(payload: LoginRequest, response: Response) -> dict[str, str]:
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
    session = await SupabaseAuthClient(settings).sign_up(
        payload.email,
        payload.password,
        {"full_name": payload.full_name or "", "organization_name": payload.organization_name or ""},
    )
    user_data = session.get("user") or {}
    if not user_data.get("id"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to create account.")
    access_token = session.get("session", {}).get("access_token")
    refresh_token = session.get("session", {}).get("refresh_token")
    ensure_membership(user_data["id"], payload.email, payload.organization_name)
    if access_token:
        set_session_cookies(response, access_token, refresh_token)
    return {"status": "ok"}


@app.post("/api/auth/logout")
async def logout(response: Response) -> dict[str, str]:
    clear_session_cookies(response)
    return {"status": "ok"}


@app.get("/api/auth/me", response_model=UserSession)
async def me(user: AuthenticatedUser = Depends(authenticate_request)) -> UserSession:
    return UserSession(
        user_id=user.user_id,
        email=user.email,
        organization_id=user.organization_id,
        organization_name=user.organization_name,
    )


@app.get("/api/projects/current", response_model=ProjectStateResponse)
async def current_project(user: AuthenticatedUser = Depends(authenticate_request)) -> ProjectStateResponse:
    project = get_or_create_current_project(user)
    uploads = list_uploads(project["id"], user.organization_id)
    return ProjectStateResponse(
        user=UserSession(
            user_id=user.user_id,
            email=user.email,
            organization_id=user.organization_id,
            organization_name=user.organization_name,
        ),
        project=ProjectSummary(**project),
        setup_components=build_component_state(uploads),
    )


@app.post("/api/projects/current/cohort-size")
async def save_cohort_size(payload: CohortSizeRequest, user: AuthenticatedUser = Depends(authenticate_request)) -> dict[str, int]:
    project = get_or_create_current_project(user)
    update_cohort_size(project["id"], user.organization_id, payload.cohort_size)
    return {"cohort_size": payload.cohort_size}


@app.post("/api/projects/current/uploads")
async def upload_project_file(
    component: str = Form(...),
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(authenticate_request),
) -> dict[str, object]:
    project = get_or_create_current_project(user)
    record = await save_upload(user, project, component, file)
    uploads = list_uploads(project["id"], user.organization_id)
    return {"upload": record, "setup_components": build_component_state(uploads)}


@app.post("/api/projects/current/analyze")
async def trigger_analysis(user: AuthenticatedUser = Depends(authenticate_request)) -> dict[str, str]:
    project = get_or_create_current_project(user)
    await analyze_project(user, project)
    return {"status": "ok"}


@app.get("/api/projects/current/dashboard", response_model=DashboardResponse)
async def dashboard(user: AuthenticatedUser = Depends(authenticate_request)) -> DashboardResponse:
    project = get_or_create_current_project(user)
    analysis = await ensure_analysis(user, project)
    return DashboardResponse(
        project=ProjectSummary(**project),
        metrics=analysis["metrics"],
        grantObjectives=analysis["objectives"],
        sources=analysis["sources"],
        last_calculated_at=analysis.get("calculated_at"),
    )


@app.get("/api/projects/current/analytics", response_model=AnalyticsResponse)
async def analytics(user: AuthenticatedUser = Depends(authenticate_request)) -> AnalyticsResponse:
    project = get_or_create_current_project(user)
    analysis = await ensure_analysis(user, project)
    return AnalyticsResponse(
        project=ProjectSummary(**project),
        beforeAfter=analysis["before_after"],
        distribution=analysis["distribution"],
        deltas=analysis["deltas"],
        analyst_notes=analysis["analyst_notes"],
        matched_response_count=analysis["summary"]["matched_response_count"],
    )


@app.get("/api/projects/current/grant-summary", response_model=GrantSummaryResponse)
async def grant_summary(user: AuthenticatedUser = Depends(authenticate_request)) -> GrantSummaryResponse:
    project = get_or_create_current_project(user)
    analysis = await ensure_analysis(user, project)
    latest_report = None
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
        project=ProjectSummary(**project),
        metrics=[{"value": item["value"], "label": item["label"].lower()} for item in analysis["metrics"][:4]],
        objectives=analysis["objectives"],
        quote=analysis["selected_quote"],
        narrative=analysis["grant_narrative"],
        executive_summary=analysis["executive_summary"],
        report_id=latest_report["id"] if latest_report else None,
        pdf_download_url=pdf_download_url,
        generated_at=latest_report["created_at"] if latest_report else analysis.get("calculated_at"),
    )


@app.post("/api/projects/current/grant-summary/pdf")
async def build_pdf(user: AuthenticatedUser = Depends(authenticate_request)) -> dict[str, str]:
    project = get_or_create_current_project(user)
    analysis = await ensure_analysis(user, project)
    record = await generate_and_store_report(user, project, analysis)
    return {"report_id": record["id"], "download_url": f"/api/reports/{record['id']}/download"}


@app.get("/api/reports/{report_id}/download")
async def download_report(report_id: str, user: AuthenticatedUser = Depends(authenticate_request)) -> StreamingResponse:
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
    return FileResponse(ROOT_DIR / "login.html")


@app.get("/index.html", include_in_schema=False)
async def index_page(request: Request) -> FileResponse:
    return await protected_page("index.html", request)


@app.get("/admin.html", include_in_schema=False)
async def admin_page(request: Request) -> FileResponse:
    return await protected_page("admin.html", request)


@app.get("/dashboard.html", include_in_schema=False)
async def dashboard_page(request: Request) -> FileResponse:
    return await protected_page("dashboard.html", request)


@app.get("/analytics.html", include_in_schema=False)
async def analytics_page(request: Request) -> FileResponse:
    return await protected_page("analytics.html", request)


@app.get("/grant-summary.html", include_in_schema=False)
async def grant_page(request: Request) -> FileResponse:
    return await protected_page("grant-summary.html", request)


app.mount("/", StaticFiles(directory=ROOT_DIR, html=True), name="static")
