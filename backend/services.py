from __future__ import annotations

import json
import mimetypes
import random
import zipfile
from datetime import datetime, timezone
from io import BytesIO
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
from .upload_schema import serialize_component_schema, validate_component_dataframe


COMPONENT_CONFIG = {
    "pre": {"name": "Week 1 Pre-Survey", "type": "Google Form", "extensions": {".csv", ".xlsx"}},
    "weekly": {"name": "Weekly Check-In Surveys", "type": "Google Form", "extensions": {".csv", ".xlsx"}},
    "post": {"name": "Week 8 Post-Survey", "type": "Google Form", "extensions": {".csv", ".xlsx"}},
    "deliverables": {"name": "Deliverables Tracker", "type": "Google Sheet", "extensions": {".csv", ".xlsx"}},
    "resume-linkedin": {"name": "Resume & LinkedIn Completion Tracker", "type": "Google Sheet", "extensions": {".csv", ".xlsx"}},
    "testimonials": {"name": "Testimonials", "type": "Google Form", "extensions": {".csv", ".xlsx"}},
    "photos": {"name": "Photos", "type": "Drive Folder", "extensions": {".zip", ".png", ".jpg", ".jpeg", ".webp"}},
}

ANALYSIS_VERSION = 4
PHOTO_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_FEATURED_PHOTOS = 4


def now_utc() -> datetime:
    """Provide a timezone-aware UTC timestamp for stored portal records."""
    return datetime.now(timezone.utc)


def guess_content_type(filename: str) -> str:
    """Infer a browser-friendly content type for uploaded or extracted photo assets."""
    content_type, _ = mimetypes.guess_type(filename)
    return content_type or "application/octet-stream"


def build_featured_photo_caption(filename: str) -> str:
    """Turn raw file names into cleaner labels for featured-photo cards."""
    stem = Path(filename).stem.replace("_", " ").replace("-", " ").strip()
    return stem.title() or "Program photo"


def collect_photo_asset_paths(parsed_summary: dict[str, Any] | None, primary_storage_path: str) -> list[str]:
    """List all storage objects tied to a photo upload so deletes clean up derived assets too."""
    summary = parsed_summary or {}
    asset_paths: list[str] = []
    for asset in summary.get("featured_images", []):
        asset_path = str(asset.get("storage_path") or "").strip()
        if asset_path and asset_path != primary_storage_path:
            asset_paths.append(asset_path)
    return list(dict.fromkeys(asset_paths))


def build_featured_photos(upload_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Expose a small, stable set of featured photos for dashboard and grant-summary rendering."""
    featured: list[dict[str, str]] = []
    for row in upload_rows:
        if row.get("component") != "photos":
            continue
        summary = row.get("parsed_summary") or {}
        for index, asset in enumerate(summary.get("featured_images", [])):
            filename = str(asset.get("filename") or row.get("filename") or "Program photo")
            featured.append(
                {
                    "url": f"/api/projects/current/uploads/{row['id']}/asset/{index}",
                    "filename": filename,
                    "caption": build_featured_photo_caption(filename),
                }
            )
    return featured[:MAX_FEATURED_PHOTOS]


async def extract_zip_featured_images(
    storage: StorageClient,
    bucket_name: str,
    storage_prefix: str,
    archive_bytes: bytes,
    seed: str,
) -> dict[str, Any]:
    """Pick a few random images from an uploaded ZIP so staff can upload a photo folder directly."""
    try:
        archive = zipfile.ZipFile(BytesIO(archive_bytes))
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Photos ZIP could not be opened.") from exc

    with archive:
        image_members = [
            member
            for member in archive.infolist()
            if not member.is_dir() and Path(member.filename).suffix.lower() in PHOTO_IMAGE_EXTENSIONS
        ]
        if not image_members:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Photos ZIP must contain at least one .png, .jpg, .jpeg, or .webp image.",
            )

        picker = random.Random(seed)
        if len(image_members) <= MAX_FEATURED_PHOTOS:
            featured_members = list(image_members)
        else:
            featured_members = picker.sample(image_members, MAX_FEATURED_PHOTOS)
        featured_members.sort(key=lambda member: member.filename.lower())

        featured_images: list[dict[str, str]] = []
        skipped_files: list[str] = []
        for index, member in enumerate(featured_members, start=1):
            asset_name = Path(member.filename).name
            if not asset_name:
                continue
            try:
                asset_bytes = archive.read(member)
                asset_path = f"{storage_prefix}/featured-{index}-{asset_name}"
                await storage.upload_bytes(bucket_name, asset_path, asset_bytes, guess_content_type(asset_name))
                featured_images.append(
                    {
                        "filename": asset_name,
                        "storage_path": asset_path,
                        "content_type": guess_content_type(asset_name),
                    }
                )
            except Exception:
                skipped_files.append(asset_name)

    summary: dict[str, Any] = {
        "archive_type": "zip",
        "image_count": len(image_members),
        "featured_images": featured_images,
    }
    if skipped_files:
        summary["skipped_files"] = skipped_files
    if not featured_images:
        summary["preview_warning"] = "Photo ZIP uploaded, but preview images could not be generated from the archive."
    return summary


def get_or_create_current_project(user: AuthenticatedUser) -> dict[str, Any]:
    """Return the latest project for an organization or create a fresh cohort shell."""
    project = fetch_one(
        """
        select id, organization_id, name, cohort_year, cohort_size, reporting_period, status, created_at, updated_at
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
        insert into projects (id, organization_id, owner_user_id, name, cohort_year, cohort_size, reporting_period, status)
        values (%s, %s, %s, %s, %s, %s, %s, %s)
        returning id, organization_id, name, cohort_year, cohort_size, reporting_period, status, created_at, updated_at
        """,
        (str(uuid4()), user.organization_id, user.user_id, "Green Careers Launchpad", now_utc().year, 0, "", "draft"),
    )


def set_project_status(project_id: str, organization_id: str, status_value: str) -> None:
    """Update the project status shown across the admin and reporting views."""
    execute(
        """
        update projects
        set status = %s, updated_at = now()
        where id = %s and organization_id = %s
        """,
        (status_value, project_id, organization_id),
    )


def update_cohort_size(project_id: str, organization_id: str, cohort_size: int) -> None:
    """Save cohort size changes and invalidate stale derived analysis outputs."""
    execute(
        """
        update projects
        set cohort_size = %s, updated_at = now()
        where id = %s and organization_id = %s
        """,
        (cohort_size, project_id, organization_id),
    )
    invalidate_saved_analysis(project_id, organization_id)


def update_reporting_period(project_id: str, organization_id: str, reporting_period: str) -> None:
    """Save the staff-entered reporting period used in summaries and exports."""
    execute(
        """
        update projects
        set reporting_period = %s, updated_at = now()
        where id = %s and organization_id = %s
        """,
        (reporting_period, project_id, organization_id),
    )


def list_uploads(project_id: str, organization_id: str) -> list[dict[str, Any]]:
    """Fetch all uploaded source files for the active organization project."""
    return fetch_all(
        """
        select id, component, filename, content_type, size_bytes, row_count, source_kind, parsed_summary, created_at, storage_path
        from project_uploads
        where project_id = %s and organization_id = %s
        order by created_at asc
        """,
        (project_id, organization_id),
    )


def _serialize_upload_file(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw upload row into the frontend-friendly file metadata shape."""
    return {
        "id": str(row["id"]),
        "filename": row["filename"],
        "content_type": row["content_type"],
        "size_bytes": int(row["size_bytes"]),
        "row_count": row["row_count"],
        "source_kind": row["source_kind"],
        "parsed_summary": row.get("parsed_summary") or {},
        "created_at": row["created_at"],
    }


def build_component_state(upload_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group raw uploads into the setup cards rendered in the admin workspace."""
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
                "files": [_serialize_upload_file(row) for row in rows],
                "schema": serialize_component_schema(component_id),
            }
        )
    return state


def build_setup_progress(project: dict[str, Any], upload_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize how close the current project is to a complete upload setup."""
    completed_required = 0
    total_required = len(COMPONENT_CONFIG) + 1
    missing_components: list[str] = []

    cohort_size = int(project.get("cohort_size") or 0)
    if cohort_size > 0:
        completed_required += 1
    else:
        missing_components.append("Cohort size")

    upload_counts = {component_id: 0 for component_id in COMPONENT_CONFIG}
    for row in upload_rows:
        upload_counts[row["component"]] = upload_counts.get(row["component"], 0) + 1

    for component_id, config in COMPONENT_CONFIG.items():
        if upload_counts.get(component_id, 0) > 0:
            completed_required += 1
        else:
            missing_components.append(config["name"])

    return {
        "total_required": total_required,
        "completed_required": completed_required,
        "total_uploads": len(upload_rows),
        "is_complete": completed_required == total_required,
        "missing_components": missing_components,
        "analysis_status": project.get("status") or "draft",
    }


def invalidate_saved_analysis(project_id: str, organization_id: str) -> None:
    """Drop cached analysis whenever source uploads or cohort size change."""
    execute(
        "delete from project_analyses where project_id = %s and organization_id = %s",
        (project_id, organization_id),
    )


def derive_project_status(project_id: str, organization_id: str, is_complete: bool, has_analysis: bool) -> str:
    """Derive the user-facing project status from setup and analysis readiness."""
    status_value = "analyzed" if has_analysis else ("ready" if is_complete else "draft")
    set_project_status(project_id, organization_id, status_value)
    return status_value


async def save_upload(user: AuthenticatedUser, project: dict[str, Any], component: str, file: UploadFile) -> dict[str, Any]:
    """Validate, store, and catalog a newly uploaded program source file."""
    if component not in COMPONENT_CONFIG:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown upload category.")

    config = COMPONENT_CONFIG[component]
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in config["extensions"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported file type for {config['name']}.")

    settings = get_settings()
    storage = StorageClient(settings)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"File exceeds {settings.max_upload_size_mb} MB limit.")

    upload_id = str(uuid4())
    file_name = Path(file.filename or 'upload').name
    storage_path = f"{user.organization_id}/{project['id']}/{component}/{upload_id}-{file_name}"
    stored_content = content
    stored_content_type = file.content_type or guess_content_type(file_name)

    row_count = None
    parsed_summary: dict[str, Any] | None = None
    source_kind = "binary"
    if suffix in {".csv", ".xlsx"}:
        source_kind = "spreadsheet"
        try:
            dataframe = read_spreadsheet(file.filename or "upload", content)
            row_count = int(dataframe.shape[0])
            parsed_summary = dataframe_summary(dataframe)
            schema_validation = validate_component_dataframe(component, config["name"], dataframe)
            parsed_summary["schema_validation"] = schema_validation
            if not schema_validation["valid"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=schema_validation["message"],
                )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unable to parse spreadsheet: {exc}") from exc
    elif component == "photos":
        if suffix == ".zip":
            source_kind = "archive"
        else:
            source_kind = "image"

    if component == "photos":
        if suffix == ".zip":
            try:
                parsed_summary = await extract_zip_featured_images(
                    storage,
                    settings.supabase_bucket_uploads,
                    f"{user.organization_id}/{project['id']}/{component}/{upload_id}-assets",
                    content,
                    upload_id,
                )
            except HTTPException:
                raise
            except Exception:
                parsed_summary = {
                    "archive_type": "zip",
                    "image_count": 0,
                    "featured_images": [],
                    "preview_warning": "Photo ZIP uploaded, but preview images could not be generated from the archive.",
                }
            manifest_payload = {
                "archive_type": "zip",
                "original_filename": file_name,
                "image_count": parsed_summary.get("image_count", 0),
                "featured_images": parsed_summary.get("featured_images", []),
                "preview_warning": parsed_summary.get("preview_warning"),
                "skipped_files": parsed_summary.get("skipped_files", []),
            }
            storage_path = f"{user.organization_id}/{project['id']}/{component}/{upload_id}-photo-manifest.json"
            stored_content = json.dumps(manifest_payload).encode("utf-8")
            stored_content_type = "application/json"
        else:
            parsed_summary = {
                "image_count": 1,
                "featured_images": [
                    {
                        "filename": file_name,
                        "storage_path": storage_path,
                        "content_type": file.content_type or guess_content_type(file_name),
                    }
                ],
            }

    await storage.upload_bytes(
        settings.supabase_bucket_uploads,
        storage_path,
        stored_content,
        stored_content_type,
    )

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
    invalidate_saved_analysis(project["id"], user.organization_id)
    return record


async def delete_upload(user: AuthenticatedUser, project: dict[str, Any], upload_id: str) -> None:
    """Remove an uploaded file from storage and the project catalog."""
    row = fetch_one(
        """
        select id, storage_path, parsed_summary
        from project_uploads
        where id = %s and project_id = %s and organization_id = %s
        limit 1
        """,
        (upload_id, project["id"], user.organization_id),
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found.")

    settings = get_settings()
    storage = StorageClient(settings)
    await storage.delete_object(settings.supabase_bucket_uploads, row["storage_path"])
    for asset_path in collect_photo_asset_paths(row.get("parsed_summary"), row["storage_path"]):
        await storage.delete_object(settings.supabase_bucket_uploads, asset_path)
    execute(
        "delete from project_uploads where id = %s and project_id = %s and organization_id = %s",
        (upload_id, project["id"], user.organization_id),
    )
    invalidate_saved_analysis(project["id"], user.organization_id)
    execute(
        "update projects set updated_at = now() where id = %s and organization_id = %s",
        (project["id"], user.organization_id),
    )


async def load_analysis_input(upload_rows: list[dict[str, Any]]) -> list[UploadDataset]:
    """Read every uploaded file into normalized datasets for downstream analysis."""
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
    """Read the uploaded data sources, calculate metrics, and persist the result."""
    uploads = list_uploads(project["id"], user.organization_id)
    datasets = await load_analysis_input(uploads)
    analysis = build_analysis(project, datasets)
    analysis["featured_photos"] = build_featured_photos(uploads)
    narrative = generate_narrative(analysis)
    payload = {
        "analysis_version": ANALYSIS_VERSION,
        "metrics": analysis["metrics"],
        "objectives": analysis["objectives"],
        "before_after": analysis["before_after"],
        "distribution": analysis["distribution"],
        "deltas": analysis["deltas"],
        "quotes": analysis["quotes"],
        "selected_quote": narrative["participant_quote"],
        "summary": analysis["summary"],
        "sources": analysis["sources"],
        "featured_photos": analysis.get("featured_photos", []),
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
    set_project_status(project["id"], user.organization_id, "analyzed")
    return payload


def get_saved_analysis(project_id: str, organization_id: str) -> dict[str, Any] | None:
    """Return the latest persisted analysis payload for the active project, if any."""
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
    """Return cached analysis when possible, otherwise generate it on demand."""
    analysis = get_saved_analysis(project["id"], user.organization_id)
    if analysis and analysis.get("analysis_version") == ANALYSIS_VERSION:
        return analysis
    return await analyze_project(user, project)


async def generate_and_store_report(user: AuthenticatedUser, project: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    """Render the current grant summary into a PDF and store it in Supabase."""
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
            "participant_quotes": analysis.get("quotes", []),
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
                    "participant_quotes": analysis.get("quotes", []),
                }
            ),
            storage_path,
            user.user_id,
        ),
    )
    return record
