from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from .analysis import UploadDataset, build_analysis, dataframe_summary, read_spreadsheet
from .auth import AuthenticatedUser
from .config import get_settings
from .db import execute, execute_returning, fetch_all, fetch_one
from .openai_service import generate_narrative
from .pdf_report import generate_grant_pdf
from .storage import StorageClient


COMPONENT_CONFIG = {
    "pre": {"name": "Week 1 Pre-Survey", "type": "Google Form", "extensions": {".csv", ".xlsx"}},
    "weekly": {"name": "Weekly Check-In Surveys", "type": "Google Form", "extensions": {".csv", ".xlsx"}},
    "post": {"name": "Week 8 Post-Survey", "type": "Google Form", "extensions": {".csv", ".xlsx"}},
    "deliverables": {"name": "Deliverables Tracker", "type": "Google Sheet", "extensions": {".csv", ".xlsx"}},
    "resume-linkedin": {"name": "Resume & LinkedIn Completion Tracker", "type": "Google Sheet", "extensions": {".csv", ".xlsx"}},
    "testimonials": {"name": "Testimonials", "type": "Google Form", "extensions": {".csv", ".xlsx"}},
    "photos": {"name": "Photos", "type": "Drive Folder", "extensions": {".png", ".jpg", ".jpeg", ".webp", ".pdf"}},
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_or_create_current_project(user: AuthenticatedUser) -> dict[str, Any]:
    project = fetch_one(
        """
        select id, organization_id, name, cohort_year, cohort_size, status, created_at, updated_at
        from projects
        where organization_id = %s
        order by updated_at desc
        limit 1
        """,
        (user.organization_id,),
    )
    if project:
        return project

    return execute_returning(
        """
        insert into projects (id, organization_id, owner_user_id, name, cohort_year, cohort_size, status)
        values (%s, %s, %s, %s, %s, %s, %s)
        returning id, organization_id, name, cohort_year, cohort_size, status, created_at, updated_at
        """,
        (str(uuid4()), user.organization_id, user.user_id, "Green Careers Launchpad", now_utc().year, 0, "draft"),
    )


def update_cohort_size(project_id: str, organization_id: str, cohort_size: int) -> None:
    execute(
        """
        update projects
        set cohort_size = %s, updated_at = now()
        where id = %s and organization_id = %s
        """,
        (cohort_size, project_id, organization_id),
    )


def list_uploads(project_id: str, organization_id: str) -> list[dict[str, Any]]:
    return fetch_all(
        """
        select id, component, filename, content_type, size_bytes, row_count, source_kind, parsed_summary, created_at, storage_path
        from project_uploads
        where project_id = %s and organization_id = %s
        order by created_at asc
        """,
        (project_id, organization_id),
    )


def build_component_state(upload_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in upload_rows:
        grouped.setdefault(row["component"], []).append(row)
    state = []
    for component_id, config in COMPONENT_CONFIG.items():
        rows = grouped.get(component_id, [])
        state.append(
            {
                "id": component_id,
                "name": config["name"],
                "type": config["type"],
                "uploads": len(rows),
                "files": [row["filename"] for row in rows],
            }
        )
    return state


async def save_upload(user: AuthenticatedUser, project: dict[str, Any], component: str, file: UploadFile) -> dict[str, Any]:
    if component not in COMPONENT_CONFIG:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown upload category.")

    config = COMPONENT_CONFIG[component]
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in config["extensions"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported file type for {config['name']}.")

    settings = get_settings()
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"File exceeds {settings.max_upload_size_mb} MB limit.")

    row_count = None
    parsed_summary: dict[str, Any] | None = None
    source_kind = "binary"
    if suffix in {".csv", ".xlsx"}:
        source_kind = "spreadsheet"
        try:
            dataframe = read_spreadsheet(file.filename or "upload", content)
            row_count = int(dataframe.shape[0])
            parsed_summary = dataframe_summary(dataframe)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unable to parse spreadsheet: {exc}") from exc

    upload_id = str(uuid4())
    storage_path = f"{user.organization_id}/{project['id']}/{component}/{upload_id}-{Path(file.filename or 'upload').name}"
    await StorageClient().upload_bytes(settings.supabase_bucket_uploads, storage_path, content, file.content_type or "application/octet-stream")

    record = execute_returning(
        """
        insert into project_uploads (
          id, project_id, organization_id, component, filename, storage_path, content_type,
          size_bytes, file_ext, source_kind, row_count, parsed_summary, uploaded_by
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        returning id, component, filename, content_type, size_bytes, row_count, source_kind, parsed_summary, created_at, storage_path
        """,
        (
            upload_id,
            project["id"],
            user.organization_id,
            component,
            file.filename,
            storage_path,
            file.content_type or "application/octet-stream",
            len(content),
            suffix,
            source_kind,
            row_count,
            json.dumps(parsed_summary or {}),
            user.user_id,
        ),
    )
    execute("update projects set updated_at = now() where id = %s", (project["id"],))
    return record


async def load_analysis_input(upload_rows: list[dict[str, Any]]) -> list[UploadDataset]:
    settings = get_settings()
    storage = StorageClient(settings)
    datasets: list[UploadDataset] = []
    for row in upload_rows:
        dataframe = None
        if row["source_kind"] == "spreadsheet":
            payload = await storage.download_bytes(settings.supabase_bucket_uploads, row["storage_path"])
            dataframe = read_spreadsheet(row["filename"], payload)
        datasets.append(
            UploadDataset(
                component=row["component"],
                filename=row["filename"],
                dataframe=dataframe,
                content_type=row["content_type"],
                row_count=row["row_count"],
                summary=row.get("parsed_summary") or {},
            )
        )
    return datasets


async def analyze_project(user: AuthenticatedUser, project: dict[str, Any]) -> dict[str, Any]:
    uploads = list_uploads(project["id"], user.organization_id)
    datasets = await load_analysis_input(uploads)
    analysis = build_analysis(project, datasets)
    narrative = generate_narrative(analysis)
    payload = {
        "metrics": analysis["metrics"],
        "objectives": analysis["objectives"],
        "before_after": analysis["before_after"],
        "distribution": analysis["distribution"],
        "deltas": analysis["deltas"],
        "quotes": analysis["quotes"],
        "selected_quote": narrative["participant_quote"],
        "summary": analysis["summary"],
        "sources": analysis["sources"],
        "analyst_notes": analysis["analyst_notes"],
        "executive_summary": narrative["executive_summary"],
        "grant_narrative": narrative["grant_narrative"],
    }
    execute(
        """
        insert into project_analyses (id, project_id, organization_id, calculated_at, payload)
        values (%s, %s, %s, now(), %s::jsonb)
        on conflict (project_id)
        do update set payload = excluded.payload, calculated_at = now()
        """,
        (str(uuid4()), project["id"], user.organization_id, json.dumps(payload)),
    )
    return payload


def get_saved_analysis(project_id: str, organization_id: str) -> dict[str, Any] | None:
    row = fetch_one(
        """
        select payload, calculated_at
        from project_analyses
        where project_id = %s and organization_id = %s
        """,
        (project_id, organization_id),
    )
    if not row:
        return None
    payload = row["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    payload["calculated_at"] = row["calculated_at"]
    return payload


async def ensure_analysis(user: AuthenticatedUser, project: dict[str, Any]) -> dict[str, Any]:
    analysis = get_saved_analysis(project["id"], user.organization_id)
    if analysis:
        return analysis
    return await analyze_project(user, project)


async def generate_and_store_report(user: AuthenticatedUser, project: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    pdf_bytes = generate_grant_pdf(
        project,
        {
            "metrics": analysis["metrics"],
            "objectives": analysis["objectives"],
        },
        {
            "executive_summary": analysis["executive_summary"],
            "grant_narrative": analysis["grant_narrative"],
            "participant_quote": analysis["selected_quote"],
        },
    )
    report_id = str(uuid4())
    storage_path = f"{user.organization_id}/{project['id']}/reports/{report_id}.pdf"
    settings = get_settings()
    await StorageClient(settings).upload_bytes(settings.supabase_bucket_reports, storage_path, pdf_bytes, "application/pdf")
    record = execute_returning(
        """
        insert into reports (id, project_id, organization_id, type, narrative_payload, storage_path, created_by)
        values (%s, %s, %s, %s, %s::jsonb, %s, %s)
        returning id, project_id, storage_path, created_at
        """,
        (
            report_id,
            project["id"],
            user.organization_id,
            "grant_summary_pdf",
            json.dumps(
                {
                    "executive_summary": analysis["executive_summary"],
                    "grant_narrative": analysis["grant_narrative"],
                    "participant_quote": analysis["selected_quote"],
                }
            ),
            storage_path,
            user.user_id,
        ),
    )
    return record
