"""Define upload schemas and validate spreadsheet columns before analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.analysis import (
    OUTCOME_DEFINITIONS,
    POST_PROGRAM_RATING_DEFINITIONS,
    find_metric_column,
    find_participant_key,
    find_post_program_survey_outcomes,
    normalize_name,
)


@dataclass(frozen=True)
class UploadField:
    """Describe one logical field and the spreadsheet aliases that can satisfy it."""

    key: str
    label: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class UploadSchema:
    """Describe the required and optional fields for one upload component."""

    component: str
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...] = ()


FIELD_DEFINITIONS: dict[str, UploadField] = {
    "participant_identifier": UploadField(
        key="participant_identifier",
        label="Participant identifier",
        aliases=(
            "participant identifier",
            "participant id",
            "participant",
            "student name",
            "intern name",
            "name",
            "full name",
        ),
    ),
    "week": UploadField(
        key="week",
        label="Week",
        aliases=(
            "week",
            "check-in week",
            "week number",
            "program week",
        ),
    ),
    "post_program_survey_ratings": UploadField(
        key="post_program_survey_ratings",
        label="Before/after ratings for all 13 post-program survey skills",
        aliases=(),
    ),
    "reflection_text": UploadField(
        key="reflection_text",
        label="Reflection or response text",
        aliases=(
            "reflection",
            "response",
            "responses",
            "check-in response",
            "weekly reflection",
            "how are you feeling",
            "what did you learn",
            "what is one new thing you learned this week",
            "what challenge did you face, and how did you overcome it",
            "what project(s) did you work on",
            "what support do you need",
            "share your thoughts",
        ),
    ),
    "clean_tech_knowledge": UploadField(
        key="clean_tech_knowledge",
        label="Clean tech knowledge",
        aliases=(
            "clean tech knowledge",
            "clean-tech knowledge",
            "knowledge of clean tech",
            "how familiar are you with clean tech careers",
            "clean tech careers",
            "awareness of clean tech career pathways",
        ),
    ),
    "interview_confidence": UploadField(
        key="interview_confidence",
        label="Interview confidence",
        aliases=(
            "interview confidence",
            "job interview confidence",
            "how confident are you participating in a job interview",
            "how confident are you in a job interview",
            "how confident are you interviewing",
            "participating in a job interview",
        ),
    ),
    "resume_readiness": UploadField(
        key="resume_readiness",
        label="Resume readiness",
        aliases=(
            "resume readiness",
            "resume confidence",
            "resume completion",
            "resume status",
            "resume url",
            "resume link",
            "has resume",
        ),
    ),
    "career_clarity": UploadField(
        key="career_clarity",
        label="Career clarity",
        aliases=(
            "career clarity",
            "career direction",
            "confidence in career direction",
            "clarity in career direction",
            "career path clarity",
        ),
    ),
    "workplace_readiness": UploadField(
        key="workplace_readiness",
        label="Workplace readiness",
        aliases=(
            "workplace readiness",
            "professional communication",
            "communication skills",
            "public speaking skills",
            "project management skills",
            "teamwork skills",
            "research skills",
            "professional workplace expectations",
            "taking initiative",
            "leading a project",
        ),
    ),
    "linkedin_completion": UploadField(
        key="linkedin_completion",
        label="LinkedIn completion",
        aliases=(
            "linkedin completion",
            "linkedin status",
            "linkedin",
            "linkedin profile",
            "linkedin profile complete",
            "linkedin url",
            "linkedin link",
        ),
    ),
    "program_completion": UploadField(
        key="program_completion",
        label="Program completion",
        aliases=(
            "program completion",
            "completion status",
            "completed program",
            "completed 8-week program",
            "program status",
        ),
    ),
    "testimonial_text": UploadField(
        key="testimonial_text",
        label="Testimonial or quote text",
        aliases=(
            "testimonial",
            "testimonial response",
            "testimonial responses",
            "quote",
            "participant quote",
            "response text",
            "story",
            "what did this program mean to you",
            "what was the most valuable part of this experience",
            "what was the most valuable part of the internship for you",
            "what was the most valuable part of the program",
            "share a reflection",
            "share your reflection",
            "what would you tell someone considering this program",
            "what would you tell someone considering the program",
            "what did you gain from this program",
            "what did you gain from the program",
            "what stood out most from this experience",
            "what stood out most from the program",
            "what is one way the green careers launchpad internship changed how you see your future and what has been your biggest accomplishment throughout this internship",
        ),
    ),
    "project_name": UploadField(
        key="project_name",
        label="Project or initiative",
        aliases=(
            "project",
            "project name",
            "project/initiative",
            "project / initiative",
            "initiative",
            "project or initiative",
            "initiative or project",
        ),
    ),
    "deliverable_name": UploadField(
        key="deliverable_name",
        label="Deliverable completed",
        aliases=(
            "deliverable completed",
            "deliverable",
            "deliverables",
            "completed deliverable",
            "deliverable name",
        ),
    ),
    "completion_status": UploadField(
        key="completion_status",
        label="Completion or status",
        aliases=(
            "status",
            "completion",
            "completion status",
            "deliverable completed",
            "completed",
            "progress",
        ),
    ),
    "category": UploadField(
        key="category",
        label="Category",
        aliases=(
            "category",
            "deliverable category",
            "skill category",
        ),
    ),
    "deliverable_link": UploadField(
        key="deliverable_link",
        label="Link to deliverable",
        aliases=(
            "link to deliverable",
            "deliverable link",
            "deliverable url",
            "artifact link",
            "link",
            "url",
        ),
    ),
    "impact_evidence": UploadField(
        key="impact_evidence",
        label="Impact or evidence",
        aliases=(
            "impact/evidence",
            "impact evidence",
            "evidence",
            "impact",
            "notes",
            "summary of impact",
        ),
    ),
    "photo_reference": UploadField(
        key="photo_reference",
        label="Photo filename, URL, or reference",
        aliases=(
            "photo",
            "photo url",
            "photo link",
            "image",
            "image url",
            "filename",
            "file name",
            "photo filename",
        ),
    ),
}


SCHEMA_DEFINITIONS: dict[str, UploadSchema] = {
    "post-program": UploadSchema(
        component="post-program",
        required_fields=("participant_identifier", "post_program_survey_ratings"),
        optional_fields=("testimonial_text",),
    ),
    "weekly": UploadSchema(
        component="weekly",
        required_fields=(
            "participant_identifier",
            "reflection_text",
        ),
        optional_fields=("week",),
    ),
    "deliverables": UploadSchema(
        component="deliverables",
        required_fields=(
            "participant_identifier",
            "project_name",
            "completion_status",
        ),
        optional_fields=(
            "week",
            "deliverable_name",
            "category",
            "deliverable_link",
            "impact_evidence",
        ),
    ),
    "resume-linkedin": UploadSchema(
        component="resume-linkedin",
        required_fields=(
            "participant_identifier",
            "resume_readiness",
            "linkedin_completion",
        ),
        optional_fields=("completion_status",),
    ),
    "testimonials": UploadSchema(
        component="testimonials",
        required_fields=(
            "participant_identifier",
            "testimonial_text",
        ),
    ),
    "photos": UploadSchema(
        component="photos",
        required_fields=("photo_reference",),
    ),
}


def _normalize_columns(columns: list[str]) -> dict[str, str]:
    """Map normalized column names back to their original spreadsheet headers."""
    return {normalize_name(str(column)): str(column) for column in columns if column is not None}


def _match_alias_column(dataframe: Any, aliases: tuple[str, ...]) -> str | None:
    """Return the first spreadsheet column whose normalized name matches any alias."""
    normalized_columns = _normalize_columns(list(dataframe.columns))
    for alias in aliases:
        normalized_alias = normalize_name(alias)
        if normalized_alias in normalized_columns:
            return normalized_columns[normalized_alias]
    return None


def _resolve_required_field(dataframe: Any, field_key: str) -> str | None:
    """Resolve one logical schema field to an actual spreadsheet column when possible."""
    if field_key == "participant_identifier":
        participant_column = find_participant_key(dataframe)
        if participant_column:
            return participant_column

    if field_key == "post_program_survey_ratings":
        outcome_pairs = find_post_program_survey_outcomes(dataframe)
        if len(outcome_pairs) == len(POST_PROGRAM_RATING_DEFINITIONS):
            return "paired before/after skill ratings"

    outcome_definition = OUTCOME_DEFINITIONS.get(field_key)
    if outcome_definition:
        metric_column = find_metric_column(dataframe, outcome_definition)
        if metric_column:
            return metric_column

    field = FIELD_DEFINITIONS[field_key]
    return _match_alias_column(dataframe, field.aliases)


def serialize_component_schema(component: str) -> dict[str, Any]:
    """Return a frontend-friendly version of one component schema."""
    schema = SCHEMA_DEFINITIONS[component]
    return {
        "component": schema.component,
        "required_fields": [
            {
                "key": field_key,
                "label": FIELD_DEFINITIONS[field_key].label,
            }
            for field_key in schema.required_fields
        ],
        "optional_fields": [
            {
                "key": field_key,
                "label": FIELD_DEFINITIONS[field_key].label,
            }
            for field_key in schema.optional_fields
        ],
    }


def validate_component_dataframe(component: str, component_name: str, dataframe: Any) -> dict[str, Any]:
    """Check whether an uploaded spreadsheet contains the required schema fields."""
    schema = SCHEMA_DEFINITIONS[component]

    matched_required_fields: dict[str, str] = {}
    missing_required_fields: list[str] = []

    for field_key in schema.required_fields:
        if field_key == "post_program_survey_ratings":
            outcome_pairs = find_post_program_survey_outcomes(dataframe)
            missing_outcomes = [
                label
                for key, label in POST_PROGRAM_RATING_DEFINITIONS.items()
                if key not in outcome_pairs
            ]
            if missing_outcomes:
                missing_required_fields.append(
                    f"Before/after ratings for: {', '.join(missing_outcomes)}"
                )
            else:
                matched_required_fields[field_key] = "paired before/after skill ratings"
            continue
        matched_column = _resolve_required_field(dataframe, field_key)
        if matched_column:
            matched_required_fields[field_key] = matched_column
        else:
            missing_required_fields.append(FIELD_DEFINITIONS[field_key].label)

    matched_optional_fields: dict[str, str] = {}
    for field_key in schema.optional_fields:
        matched_column = _resolve_required_field(dataframe, field_key)
        if matched_column:
            matched_optional_fields[field_key] = matched_column

    is_valid = len(missing_required_fields) == 0

    return {
        "valid": is_valid,
        "required_fields": list(schema.required_fields),
        "optional_fields": list(schema.optional_fields),
        "matched_required_fields": matched_required_fields,
        "matched_optional_fields": matched_optional_fields,
        "missing_required_fields": missing_required_fields,
        "message": (
            f"{component_name} matches the required schema."
            if is_valid
            else f"{component_name} is missing required fields: {', '.join(missing_required_fields)}."
        ),
    }
