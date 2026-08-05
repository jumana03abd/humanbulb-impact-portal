"""Define upload schemas and validate spreadsheet columns before analysis."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .analysis import OUTCOME_DEFINITIONS, find_metric_column, find_participant_key, normalize_name


SCHEMA_DEFINITIONS: dict[str, dict[str, Any]] = {
    "pre": {
        "required_fields": [
            {
                "key": "participant_identifier",
                "label": "Participant identifier",
                "kind": "participant",
                "description": "Use Email, Participant ID, Intern ID, Student ID, Full Name, or First Name + Last Name.",
            },
            {
                "key": "clean_tech_knowledge",
                "label": "Clean tech knowledge",
                "kind": "metric",
                "aliases": OUTCOME_DEFINITIONS["Clean tech knowledge"],
                "description": "A Week 1 self-rating for clean tech knowledge or awareness.",
            },
            {
                "key": "interview_confidence",
                "label": "Interview confidence",
                "kind": "metric",
                "aliases": OUTCOME_DEFINITIONS["Interview confidence"],
                "description": "A Week 1 self-rating for interview confidence.",
            },
            {
                "key": "resume_readiness",
                "label": "Resume readiness",
                "kind": "metric",
                "aliases": OUTCOME_DEFINITIONS["Resume readiness"],
                "description": "A Week 1 self-rating for resume readiness.",
            },
            {
                "key": "career_clarity",
                "label": "Career clarity",
                "kind": "metric",
                "aliases": OUTCOME_DEFINITIONS["Career clarity"],
                "description": "A Week 1 self-rating for career clarity or direction.",
            },
            {
                "key": "workplace_readiness",
                "label": "Workplace readiness",
                "kind": "metric",
                "aliases": [
                    *OUTCOME_DEFINITIONS["Professional communication"],
                    "time management",
                    "digital collaboration",
                    "professionalism",
                    "work readiness",
                ],
                "description": "A Week 1 self-rating for a workplace readiness skill such as communication, time management, or digital collaboration.",
            },
        ],
        "optional_fields": [
            {
                "key": "cohort_year",
                "label": "Cohort year",
                "kind": "column",
                "aliases": ["cohort year", "program year", "year"],
                "description": "Optional cohort or program year field.",
            }
        ],
        "notes": [
            "Each row should represent one participant response.",
            "Likert answers can be numeric or text such as Agree or Very confident.",
        ],
    },
    "weekly": {
        "required_fields": [
            {
                "key": "participant_identifier",
                "label": "Participant identifier",
                "kind": "participant",
                "description": "Use Email, Participant ID, Intern ID, Student ID, Full Name, or First Name + Last Name.",
            },
            {
                "key": "week_marker",
                "label": "Week or check-in marker",
                "kind": "column",
                "aliases": ["week", "week number", "check in", "check-in", "session", "date", "submitted at"],
                "description": "A field that tells the portal which weekly check-in the row belongs to.",
            },
            {
                "key": "reflection_text",
                "label": "Reflection or response text",
                "kind": "column",
                "aliases": ["reflection", "response", "feedback", "comment", "highlight", "what did you learn", "story"],
                "description": "An open-response field the AI can summarize into participant themes.",
            },
        ],
        "optional_fields": [
            {
                "key": "satisfaction",
                "label": "Satisfaction or experience rating",
                "kind": "column",
                "aliases": ["satisfaction", "experience", "weekly satisfaction", "how satisfied", "confidence"],
                "description": "Optional numeric or text rating for the weekly experience.",
            }
        ],
        "notes": [
            "Multiple weekly files are allowed.",
            "Each row should represent one participant response for one week.",
        ],
    },
    "post": {
        "required_fields": [
            {
                "key": "participant_identifier",
                "label": "Participant identifier",
                "kind": "participant",
                "description": "Use the same identifier approach as the pre-survey so participants can be matched.",
            },
            {
                "key": "clean_tech_knowledge",
                "label": "Clean tech knowledge",
                "kind": "metric",
                "aliases": OUTCOME_DEFINITIONS["Clean tech knowledge"],
                "description": "A Week 8 self-rating for clean tech knowledge or awareness.",
            },
            {
                "key": "interview_confidence",
                "label": "Interview confidence",
                "kind": "metric",
                "aliases": OUTCOME_DEFINITIONS["Interview confidence"],
                "description": "A Week 8 self-rating for interview confidence.",
            },
            {
                "key": "resume_readiness",
                "label": "Resume readiness",
                "kind": "metric",
                "aliases": OUTCOME_DEFINITIONS["Resume readiness"],
                "description": "A Week 8 self-rating for resume readiness.",
            },
            {
                "key": "career_clarity",
                "label": "Career clarity",
                "kind": "metric",
                "aliases": OUTCOME_DEFINITIONS["Career clarity"],
                "description": "A Week 8 self-rating for career clarity or direction.",
            },
            {
                "key": "workplace_readiness",
                "label": "Workplace readiness",
                "kind": "metric",
                "aliases": [
                    *OUTCOME_DEFINITIONS["Professional communication"],
                    "time management",
                    "digital collaboration",
                    "professionalism",
                    "work readiness",
                ],
                "description": "A Week 8 self-rating for a workplace readiness skill such as communication, time management, or digital collaboration.",
            },
        ],
        "optional_fields": [
            {
                "key": "open_reflection",
                "label": "Open-ended reflection",
                "kind": "column",
                "aliases": ["reflection", "response", "testimonial", "quote", "story"],
                "description": "Optional open-response field for quotes and narrative generation.",
            }
        ],
        "notes": [
            "The post-survey should mirror the pre-survey outcome areas so matched comparisons can be calculated.",
        ],
    },
    "deliverables": {
        "required_fields": [
            {
                "key": "participant_identifier",
                "label": "Intern or participant name",
                "kind": "participant",
                "description": "Use Intern Name, Participant Name, Full Name, or another participant identifier.",
            },
            {
                "key": "project_or_initiative",
                "label": "Project or initiative",
                "kind": "column",
                "aliases": ["project", "project/initiative", "initiative", "workshop", "activity", "deliverable title"],
                "description": "The project, initiative, or activity tied to the deliverable row.",
            },
            {
                "key": "completion_status",
                "label": "Deliverable completion or status",
                "kind": "column",
                "aliases": ["status", "completed", "deliverable completed", "completion", "submitted"],
                "description": "A field that shows whether the deliverable was completed or submitted.",
            },
        ],
        "optional_fields": [
            {
                "key": "deliverable_link",
                "label": "Link to deliverable",
                "kind": "column",
                "aliases": ["link", "url", "deliverable link", "artifact link"],
                "description": "Optional URL to the deliverable or artifact.",
            },
            {
                "key": "impact_evidence",
                "label": "Impact or evidence note",
                "kind": "column",
                "aliases": ["impact", "evidence", "outcome", "notes"],
                "description": "Optional note about what the deliverable achieved.",
            },
        ],
        "notes": [
            "Each row should represent one deliverable, project milestone, or completion event.",
        ],
    },
    "resume-linkedin": {
        "required_fields": [
            {
                "key": "participant_identifier",
                "label": "Intern or participant name",
                "kind": "participant",
                "description": "Use Intern Name, Participant Name, Full Name, or another participant identifier.",
            },
            {
                "key": "resume_status",
                "label": "Resume status",
                "kind": "column",
                "aliases": ["resume status", "resume completed", "resume complete", "resume"],
                "description": "A field showing whether the participant completed a resume.",
            },
            {
                "key": "linkedin_status",
                "label": "LinkedIn status",
                "kind": "column",
                "aliases": ["linkedin status", "linkedin completed", "linkedin complete", "linkedin profile"],
                "description": "A field showing whether the participant completed a LinkedIn profile.",
            },
        ],
        "optional_fields": [
            {
                "key": "resume_link",
                "label": "Resume link or file",
                "kind": "column",
                "aliases": ["resume link", "resume file", "resume url"],
                "description": "Optional file or URL reference for the participant resume.",
            },
            {
                "key": "linkedin_url",
                "label": "LinkedIn URL",
                "kind": "column",
                "aliases": ["linkedin url", "linkedin link", "profile url"],
                "description": "Optional LinkedIn profile URL.",
            },
            {
                "key": "staff_verification",
                "label": "Staff verification",
                "kind": "column",
                "aliases": ["verified", "staff verified", "verification status"],
                "description": "Optional field for staff verification of completion.",
            },
        ],
        "notes": [
            "Resume and LinkedIn completion should be tracked in separate columns so the portal can calculate both-complete rates.",
        ],
    },
    "testimonials": {
        "required_fields": [
            {
                "key": "participant_identifier",
                "label": "Participant identifier",
                "kind": "participant",
                "description": "Use Email, Participant Name, Full Name, or another identifier tied to the participant response.",
            },
            {
                "key": "testimonial_text",
                "label": "Testimonial or quote text",
                "kind": "column",
                "aliases": ["testimonial", "quote", "response", "reflection", "story", "feedback"],
                "description": "An open-response field that contains participant testimonial text.",
            },
        ],
        "optional_fields": [
            {
                "key": "consent_status",
                "label": "Consent or permission status",
                "kind": "column",
                "aliases": ["consent", "permission", "media release"],
                "description": "Optional field showing whether the quote can be shared externally.",
            }
        ],
        "notes": [
            "Each row should contain one participant response or one representative quote.",
        ],
    },
    "photos": {
        "required_fields": [
            {
                "key": "photo_reference",
                "label": "Photo filename, URL, or file reference",
                "kind": "column",
                "aliases": ["photo", "photo file", "filename", "image", "image link", "photo url", "file path"],
                "description": "Required only when a spreadsheet is uploaded to describe photo metadata.",
            }
        ],
        "optional_fields": [
            {
                "key": "caption",
                "label": "Caption or description",
                "kind": "column",
                "aliases": ["caption", "description", "alt text"],
                "description": "Optional caption or description for the photo.",
            },
            {
                "key": "event_date",
                "label": "Event or photo date",
                "kind": "column",
                "aliases": ["date", "event date", "photo date", "captured on"],
                "description": "Optional event or capture date.",
            },
            {
                "key": "consent_status",
                "label": "Consent or permission status",
                "kind": "column",
                "aliases": ["consent", "permission", "media release"],
                "description": "Optional consent flag for external use.",
            },
        ],
        "notes": [
            "Photos can be uploaded directly as image or PDF files.",
            "If you upload a spreadsheet for photo metadata, include at least one photo reference column.",
        ],
    },
}


def _match_alias_column(df: pd.DataFrame, aliases: list[str]) -> str | None:
    """Find the closest column match for a list of acceptable aliases."""
    best: tuple[int, str] | None = None
    for column in df.columns:
        normalized_column = normalize_name(str(column))
        for alias in aliases:
            normalized_alias = normalize_name(alias)
            score = 0
            if not normalized_alias:
                continue
            if normalized_column == normalized_alias:
                score = 100 + len(normalized_alias)
            elif normalized_alias in normalized_column or normalized_column in normalized_alias:
                score = 10 + min(len(normalized_alias), len(normalized_column))
            if score and (best is None or score > best[0]):
                best = (score, str(column))
    return best[1] if best else None


def _resolve_required_field(df: pd.DataFrame, field: dict[str, Any]) -> str | None:
    """Resolve one required schema field against the uploaded dataframe."""
    kind = field["kind"]
    if kind == "participant":
        match = find_participant_key(df)
        if match == "__full_name__":
            return "First Name + Last Name"
        return match
    if kind == "metric":
        return find_metric_column(df, field["aliases"])
    if kind == "column":
        return _match_alias_column(df, field["aliases"])
    return None


def serialize_component_schema(component: str) -> dict[str, Any]:
    """Return the frontend-friendly schema description for one upload component."""
    schema = SCHEMA_DEFINITIONS[component]
    return {
        "required_fields": [
            {
                "key": field["key"],
                "label": field["label"],
                "description": field["description"],
                "examples": field.get("aliases", []),
            }
            for field in schema["required_fields"]
        ],
        "optional_fields": [
            {
                "key": field["key"],
                "label": field["label"],
                "description": field["description"],
                "examples": field.get("aliases", []),
            }
            for field in schema.get("optional_fields", [])
        ],
        "notes": schema.get("notes", []),
    }


def validate_component_dataframe(component: str, component_name: str, df: pd.DataFrame) -> dict[str, Any]:
    """Validate one uploaded spreadsheet against its required schema fields."""
    if df.empty:
        raise ValueError(f"{component_name} must include at least one row of data.")

    schema = SCHEMA_DEFINITIONS[component]
    matched_fields: dict[str, str] = {}
    missing_fields: list[str] = []

    for field in schema["required_fields"]:
        matched = _resolve_required_field(df, field)
        if matched:
            matched_fields[field["label"]] = matched
        else:
            missing_fields.append(field["label"])

    optional_matches = {}
    for field in schema.get("optional_fields", []):
        matched = _resolve_required_field(df, field)
        if matched:
            optional_matches[field["label"]] = matched

    if missing_fields:
        raise ValueError(
            f"{component_name} is missing required fields: {', '.join(missing_fields)}."
        )

    return {
        "matched_fields": matched_fields,
        "optional_matches": optional_matches,
        "missing_fields": [],
    }
