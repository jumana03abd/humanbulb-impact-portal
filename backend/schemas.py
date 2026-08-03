from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None
    organization_name: str | None = None


class UserSession(BaseModel):
    user_id: str
    email: EmailStr
    organization_id: str
    organization_name: str


class CohortSizeRequest(BaseModel):
    cohort_size: int = Field(ge=0, le=100000)


class ProjectSummary(BaseModel):
    id: str
    organization_id: str
    name: str
    cohort_year: int | None = None
    cohort_size: int = 0
    status: str
    created_at: datetime
    updated_at: datetime


class UploadRecord(BaseModel):
    id: str
    component: str
    filename: str
    content_type: str
    size_bytes: int
    row_count: int | None = None
    source_kind: str
    parsed_summary: dict[str, Any] | None = None
    created_at: datetime


class UploadFileState(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    row_count: int | None = None
    source_kind: str
    parsed_summary: dict[str, Any] | None = None
    created_at: datetime


class SetupComponentState(BaseModel):
    id: str
    name: str
    type: str
    uploads: int
    files: list[UploadFileState]


class SetupProgress(BaseModel):
    total_required: int
    completed_required: int
    total_uploads: int
    is_complete: bool
    missing_components: list[str]
    analysis_status: str


class ProjectStateResponse(BaseModel):
    user: UserSession
    project: ProjectSummary
    setup_components: list[SetupComponentState]
    setup_progress: SetupProgress


class MetricCard(BaseModel):
    label: str
    value: str
    note: str


class ObjectiveCard(BaseModel):
    title: str
    description: str
    target: str
    actual: str
    status: str
    statusTone: str


class DashboardResponse(BaseModel):
    project: ProjectSummary
    metrics: list[MetricCard]
    grantObjectives: list[ObjectiveCard]
    sources: list[dict[str, Any]]
    last_calculated_at: datetime | None = None


class BeforeAfterDatum(BaseModel):
    label: str
    before: float
    after: float


class DistributionDatum(BaseModel):
    label: str
    before: int
    after: int


class AnalyticsResponse(BaseModel):
    project: ProjectSummary
    beforeAfter: list[BeforeAfterDatum]
    distribution: list[DistributionDatum]
    deltas: list[dict[str, Any]]
    analyst_notes: list[str]
    matched_response_count: int


class GrantSummaryResponse(BaseModel):
    project: ProjectSummary
    metrics: list[dict[str, str]]
    objectives: list[ObjectiveCard]
    quote: str
    narrative: str
    executive_summary: str
    report_id: str | None = None
    pdf_download_url: str | None = None
    generated_at: datetime | None = None


class ReportRecord(BaseModel):
    id: str
    project_id: str
    storage_path: str
    created_at: datetime


class ApiError(BaseModel):
    detail: str
