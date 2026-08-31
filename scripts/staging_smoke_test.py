"""Exercise the authenticated staging workflow against a clean portal project."""

from __future__ import annotations

import csv
import io
import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx


CONFIRMATION_VALUE = "run-staging-smoke"
REQUIRED_ENVIRONMENT = "staging"


@dataclass(frozen=True)
class UploadFixture:
    component: str
    filename: str
    rows: list[dict[str, str]]


UPLOAD_FIXTURES = [
    UploadFixture(
        component="pre",
        filename="smoke-pre-survey.csv",
        rows=[
            {
                "Email": "smoke-test@humanbulb.org",
                "Clean Tech Knowledge": "2",
                "Interview Confidence": "2",
                "Workplace Readiness": "2",
                "Resume Readiness": "2",
                "Career Clarity": "2",
            }
        ],
    ),
    UploadFixture(
        component="weekly",
        filename="smoke-weekly-check-in.csv",
        rows=[
            {
                "Email": "smoke-test@humanbulb.org",
                "Week": "1",
                "Reflection": "I learned practical interview preparation techniques and feel more confident applying them.",
            }
        ],
    ),
    UploadFixture(
        component="post",
        filename="smoke-post-survey.csv",
        rows=[
            {
                "Email": "smoke-test@humanbulb.org",
                "Clean Tech Knowledge": "5",
                "Interview Confidence": "5",
                "Workplace Readiness": "5",
                "Resume Readiness": "5",
                "Career Clarity": "5",
                "LinkedIn Status": "Complete",
                "Program Completion": "Complete",
            }
        ],
    ),
    UploadFixture(
        component="deliverables",
        filename="smoke-deliverables.csv",
        rows=[
            {
                "Intern Name": "Smoke Test",
                "Project Name": "Staging validation",
                "Completion Status": "Complete",
            }
        ],
    ),
    UploadFixture(
        component="resume-linkedin",
        filename="smoke-resume-linkedin.csv",
        rows=[
            {
                "Intern Name": "Smoke Test",
                "Resume Status": "Complete",
                "LinkedIn Status": "Complete",
            }
        ],
    ),
    UploadFixture(
        component="testimonials",
        filename="smoke-testimonials.csv",
        rows=[
            {
                "Participant Name": "Smoke Test",
                "Testimonial": "This program gave me a clearer path into clean energy work and stronger interview confidence.",
            }
        ],
    ),
    UploadFixture(
        component="photos",
        filename="smoke-photo-metadata.csv",
        rows=[{"Photo Filename": "staging-smoke-test.jpg"}],
    ),
]


def required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set.")
    return value


def csv_payload(rows: list[dict[str, str]]) -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def response_detail(response: httpx.Response) -> str:
    try:
        payload: Any = response.json()
    except ValueError:
        return response.text or response.reason_phrase
    if isinstance(payload, dict):
        return str(payload.get("detail") or payload)
    return str(payload)


def require_success(response: httpx.Response, action: str) -> dict[str, Any]:
    if response.is_success:
        payload = response.json()
        if isinstance(payload, dict):
            return payload
        raise RuntimeError(f"{action} returned an unexpected response.")
    raise RuntimeError(f"{action} failed ({response.status_code}): {response_detail(response)}")


def find_upload_id(project_state: dict[str, Any], filename: str) -> str:
    for component in project_state["setup_components"]:
        for uploaded_file in component["files"]:
            if uploaded_file["filename"] == filename:
                return str(uploaded_file["id"])
    raise RuntimeError(f"Could not identify the upload id for {filename}.")


def assert_empty_project(project_state: dict[str, Any]) -> None:
    existing_uploads = [
        uploaded_file["filename"]
        for component in project_state["setup_components"]
        for uploaded_file in component["files"]
    ]
    if existing_uploads or project_state["project"]["cohort_size"]:
        raise RuntimeError(
            "The staging project is not empty. Use a dedicated clean staging portal before running this smoke test."
        )


def validate_configuration() -> tuple[str, str, str]:
    if os.environ.get("SMOKE_TEST_ENV", "").strip().lower() != REQUIRED_ENVIRONMENT:
        raise RuntimeError("SMOKE_TEST_ENV must be set to staging.")
    if os.environ.get("SMOKE_TEST_CONFIRM", "").strip() != CONFIRMATION_VALUE:
        raise RuntimeError(f"SMOKE_TEST_CONFIRM must be set to {CONFIRMATION_VALUE}.")

    base_url = required_environment("SMOKE_TEST_BASE_URL").rstrip("/")
    parsed_url = urlparse(base_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise RuntimeError("SMOKE_TEST_BASE_URL must be an HTTPS staging URL.")
    return base_url, required_environment("SMOKE_TEST_EMAIL"), required_environment("SMOKE_TEST_PASSWORD")


def main() -> int:
    try:
        base_url, email, password = validate_configuration()
        uploaded_ids: list[str] = []
        report_id: str | None = None
        with httpx.Client(base_url=base_url, timeout=60, follow_redirects=False) as client:
            health = require_success(client.get("/health"), "Health check")
            if health != {"status": "ok", "database": "ok"}:
                raise RuntimeError(f"Health check returned an unexpected payload: {health}")

            require_success(client.post("/api/auth/login", json={"email": email, "password": password}), "Staff login")
            current_user = require_success(client.get("/api/auth/me"), "Session check")
            if current_user["email"].lower() != email.lower():
                raise RuntimeError("The authenticated staff account does not match SMOKE_TEST_EMAIL.")

            project_state = require_success(client.get("/api/projects/current"), "Load project")
            assert_empty_project(project_state)
            require_success(
                client.post("/api/projects/current/cohort-size", json={"cohort_size": 1}),
                "Set cohort size",
            )

            try:
                for fixture in UPLOAD_FIXTURES:
                    project_state = require_success(
                        client.post(
                            "/api/projects/current/uploads",
                            data={"component": fixture.component},
                            files={"file": (fixture.filename, csv_payload(fixture.rows), "text/csv")},
                        ),
                        f"Upload {fixture.component}",
                    )
                    uploaded_ids.append(find_upload_id(project_state, fixture.filename))

                require_success(client.post("/api/projects/current/analyze"), "Run analysis")
                dashboard = require_success(client.get("/api/projects/current/dashboard"), "Load dashboard")
                if not dashboard["metrics"]:
                    raise RuntimeError("Dashboard returned no metrics.")
                analytics = require_success(client.get("/api/projects/current/analytics"), "Load analytics")
                if analytics["matched_response_count"] != 1:
                    raise RuntimeError("Analytics did not match the expected pre- and post-survey response.")
                grant_summary = require_success(client.get("/api/projects/current/grant-summary"), "Load grant summary")
                if not grant_summary["narrative"]:
                    raise RuntimeError("Grant summary returned no narrative.")
                report = require_success(
                    client.post("/api/projects/current/grant-summary/pdf"),
                    "Generate grant PDF",
                )
                report_id = str(report["report_id"])
                pdf_response = client.get(report["download_url"])
                if pdf_response.status_code != 200 or not pdf_response.content.startswith(b"%PDF"):
                    raise RuntimeError(f"PDF download failed: {response_detail(pdf_response)}")
            finally:
                if report_id:
                    deletion = client.delete(f"/api/reports/{report_id}")
                    if not deletion.is_success:
                        print(
                            f"Warning: unable to delete smoke-test report {report_id}: {response_detail(deletion)}",
                            file=sys.stderr,
                        )
                for upload_id in reversed(uploaded_ids):
                    deletion = client.delete(f"/api/projects/current/uploads/{upload_id}")
                    if not deletion.is_success:
                        print(
                            f"Warning: unable to delete smoke-test upload {upload_id}: {response_detail(deletion)}",
                            file=sys.stderr,
                        )

        print("Staging smoke test passed.")
        return 0
    except (httpx.HTTPError, RuntimeError) as error:
        print(f"Staging smoke test failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
