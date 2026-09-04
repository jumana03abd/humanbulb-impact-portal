from __future__ import annotations

import asyncio
import csv
import os
import unittest
from io import BytesIO, StringIO
from unittest.mock import AsyncMock, patch

import pandas as pd

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:password@localhost:5432/postgres")

from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

import backend.main as main
import backend.services as services
from backend.analysis import POST_PROGRAM_RATING_DEFINITIONS, UploadDataset, build_analysis, read_spreadsheet
from backend.auth import AuthenticatedUser
from backend.upload_schema import validate_component_dataframe


def post_program_survey_csv() -> bytes:
    """Build a representative export using the exact HUMANBULB survey question headers."""
    headers = ["Name (First Last)"]
    values = ["Sample Intern"]
    for survey_label in POST_PROGRAM_RATING_DEFINITIONS.values():
        headers.append(f"How would you rate yourself BEFORE the internship in the following areas? [{survey_label}]")
        values.append("2 = Low")
        headers.append(f"How would you rate yourself AFTER the internship in the following areas? [{survey_label}]")
        values.append("4 = High")
    buffer = StringIO()
    csv.writer(buffer).writerows([headers, values])
    return buffer.getvalue().encode("utf-8")


class CoreApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(main.app)
        main.app.dependency_overrides[main.authenticate_request] = self.authenticated_user

    def tearDown(self) -> None:
        main.app.dependency_overrides.clear()

    @staticmethod
    def authenticated_user() -> AuthenticatedUser:
        return AuthenticatedUser(
            user_id="user-1",
            email="staff@humanbulb.org",
            organization_id="org-1",
            organization_name="HUMANBULB",
        )

    def test_health_endpoint_confirms_database_connectivity(self) -> None:
        with patch("backend.db.fetch_one", return_value={"connected": 1}) as fetch_one:
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})
        fetch_one.assert_called_once_with("select 1 as connected")

    def test_health_endpoint_returns_service_unavailable_when_database_fails(self) -> None:
        with patch("backend.db.fetch_one", side_effect=RuntimeError("connection failed")):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Database unavailable.")

    def test_report_deletion_removes_scoped_storage_and_record(self) -> None:
        deleted_objects: list[tuple[str, str]] = []

        async def delete_object(storage_client, bucket: str, path: str) -> None:
            deleted_objects.append((bucket, path))

        with patch("backend.main.get_or_create_current_project", return_value={"id": "project-1"}), patch(
            "backend.db.fetch_one", return_value={"storage_path": "org-1/project-1/reports/report-1.pdf"}
        ), patch(
            "backend.db.execute"
        ) as execute, patch.object(main.StorageClient, "delete_object", delete_object):
            response = self.client.delete("/api/reports/report-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(
            deleted_objects,
            [(main.settings.supabase_bucket_reports, "org-1/project-1/reports/report-1.pdf")],
        )
        execute.assert_called_once_with(
            "delete from reports where id = %s and project_id = %s and organization_id = %s",
            ("report-1", "project-1", "org-1"),
        )

    def test_report_deletion_rejects_reports_outside_the_organization(self) -> None:
        with patch("backend.main.get_or_create_current_project", return_value={"id": "project-1"}), patch(
            "backend.db.fetch_one", return_value=None
        ), patch.object(
            main.StorageClient, "delete_object", AsyncMock()
        ) as delete_object:
            response = self.client.delete("/api/reports/another-organization-report")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Report not found.")
        delete_object.assert_not_awaited()

    def test_logout_clears_only_the_signed_in_users_workspace(self) -> None:
        with patch("backend.main.reset_current_workspace", AsyncMock()) as reset_workspace:
            response = self.client.post("/api/auth/logout")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        reset_workspace.assert_awaited_once_with(self.authenticated_user())

    def test_workspace_reset_removes_user_storage_and_project(self) -> None:
        user = self.authenticated_user()
        uploads = [
            {
                "storage_path": "org-1/project-1/photos/archive.zip",
                "parsed_summary": {
                    "featured_images": [
                        {"storage_path": "org-1/project-1/photos/featured-1.jpg"},
                    ]
                },
            }
        ]
        reports = [{"storage_path": "org-1/project-1/reports/report-1.pdf"}]

        with patch("backend.services.find_current_workspace", return_value={"id": "project-1"}), patch(
            "backend.services.fetch_all", side_effect=[uploads, reports]
        ), patch.object(services.StorageClient, "delete_object", AsyncMock()) as delete_object, patch(
            "backend.services.execute"
        ) as execute:
            asyncio.run(services.reset_current_workspace(user))

        self.assertEqual(
            delete_object.await_args_list,
            [
                unittest.mock.call(main.settings.supabase_bucket_uploads, "org-1/project-1/photos/archive.zip"),
                unittest.mock.call(main.settings.supabase_bucket_uploads, "org-1/project-1/photos/featured-1.jpg"),
                unittest.mock.call(main.settings.supabase_bucket_reports, "org-1/project-1/reports/report-1.pdf"),
            ],
        )
        execute.assert_called_once_with(
            """
        delete from projects
        where id = %s and organization_id = %s and workspace_owner_user_id = %s
        """,
            ("project-1", "org-1", "user-1"),
        )

    def test_invalid_upload_is_rejected_before_storage(self) -> None:
        uploaded_file = UploadFile(
            filename="invalid-pre-survey.csv",
            file=BytesIO(b"Email\nsmoke-test@humanbulb.org\n"),
        )

        with patch.object(main.StorageClient, "upload_bytes", AsyncMock()) as upload_bytes:
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(
                    services.save_upload(
                        self.authenticated_user(),
                        {"id": "project-1"},
                        "post-program",
                        uploaded_file,
                    )
                )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("missing required fields", raised.exception.detail)
        upload_bytes.assert_not_awaited()

    def test_valid_upload_is_stored_after_schema_validation(self) -> None:
        uploaded_file = UploadFile(
            filename="post-program-survey.csv",
            file=BytesIO(post_program_survey_csv()),
        )
        stored_record = {"id": "upload-1", "filename": "valid-pre-survey.csv"}

        with patch.object(main.StorageClient, "upload_bytes", AsyncMock()) as upload_bytes, patch(
            "backend.services.execute_returning", return_value=stored_record
        ), patch("backend.services.execute"):
            result = asyncio.run(
                services.save_upload(
                    self.authenticated_user(),
                    {"id": "project-1"},
                    "post-program",
                    uploaded_file,
                )
            )

        self.assertEqual(result, stored_record)
        upload_bytes.assert_awaited_once()

    def test_post_program_survey_produces_paired_before_after_results(self) -> None:
        dataframe = read_spreadsheet("post-program-survey.csv", post_program_survey_csv())
        analysis = build_analysis(
            {"cohort_size": 0},
            [
                UploadDataset(
                    component="post-program",
                    filename="post-program-survey.csv",
                    dataframe=dataframe,
                    content_type="text/csv",
                    row_count=1,
                    summary={},
                )
            ],
        )

        self.assertEqual(analysis["summary"]["matched_response_count"], 1)
        self.assertEqual(len(analysis["before_after"]), len(POST_PROGRAM_RATING_DEFINITIONS))
        self.assertEqual(analysis["metrics"][1]["value"], "100%")
        self.assertEqual(analysis["metrics"][4]["value"], "100%")

    def test_weekly_checkin_accepts_question_style_google_form_headers(self) -> None:
        dataframe = pd.DataFrame(
            {
                "Timestamp": ["2026-09-03 10:00:00"],
                "Name ": ["Sample Intern"],
                "What project(s) did you work on?": ["Community research"],
                "What is one new thing you learned this week?": ["How to prepare survey findings"],
                " What skill improved the most?": ["Project management"],
                "What challenge did you face, and how did you overcome it?": ["Scheduling, solved with a plan"],
            }
        )

        validation = validate_component_dataframe("weekly", "Weekly Check-In Surveys", dataframe)

        self.assertTrue(validation["valid"])

    def test_resume_tracker_accepts_title_rows_and_url_columns(self) -> None:
        raw_rows = [
            ["Green Careers Launchpad Resume + LinkedIn Tracker", "", "", "", "", "", ""],
            ["", "", "", "", "", "", ""],
            ["", "", "", "", "", "", ""],
            ["Intern Name", "LinkedIn URL", "Cover Letter URL", "Resume URL", "Staff Verified (Resume)", "Verified By", "Verification Date"],
            ["Sample Intern", "https://linkedin.com/in/sample", "", "https://example.org/resume", True, "Staff", "2026-09-03"],
        ]
        workbook = BytesIO()
        pd.DataFrame(raw_rows).to_excel(workbook, index=False, header=False)

        dataframe = read_spreadsheet("resume-linkedin.xlsx", workbook.getvalue())
        validation = validate_component_dataframe("resume-linkedin", "Resume & LinkedIn Completion Tracker", dataframe)

        self.assertEqual(list(dataframe.columns)[:4], ["Intern Name", "LinkedIn URL", "Cover Letter URL", "Resume URL"])
        self.assertTrue(validation["valid"])


if __name__ == "__main__":
    unittest.main()
