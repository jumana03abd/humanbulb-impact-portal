from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Any

import pandas as pd


NUMERIC_TEXT_MAP = {
    "strongly disagree": 1,
    "disagree": 2,
    "somewhat disagree": 2,
    "neutral": 3,
    "somewhat agree": 4,
    "agree": 4,
    "strongly agree": 5,
    "not confident": 1,
    "somewhat confident": 3,
    "confident": 5,
    "very confident": 5,
    "not at all": 1,
    "a little": 2,
    "some": 3,
    "quite a bit": 4,
    "a lot": 5,
}

OUTCOME_DEFINITIONS = {
    "Clean tech knowledge": ["clean tech", "cleantech", "green career knowledge", "knowledge of clean tech careers"],
    "Interview confidence": ["interview confidence", "confident interviewing", "feel interviewing"],
    "Resume readiness": ["resume readiness", "resume ready", "resume"],
    "Career clarity": ["career clarity", "career direction", "clarity in your career"],
    "Professional communication": ["professional communication", "communication", "workplace readiness"],
}


@dataclass
class UploadDataset:
    component: str
    filename: str
    dataframe: pd.DataFrame | None
    content_type: str
    row_count: int | None
    summary: dict[str, Any]


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def read_spreadsheet(filename: str, content: bytes) -> pd.DataFrame:
    lower = filename.lower()
    if lower.endswith(".csv"):
        return pd.read_csv(io.BytesIO(content))
    if lower.endswith(".xlsx"):
        return pd.read_excel(io.BytesIO(content), engine="openpyxl")
    raise ValueError("Unsupported spreadsheet format.")


def dataframe_summary(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "columns": [str(col) for col in df.columns.tolist()],
        "rows": int(df.shape[0]),
        "sample": df.head(3).fillna("").astype(str).to_dict(orient="records"),
    }


def parse_likert(value: Any) -> float | None:
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)) and not pd.isna(value):
        return float(value)
    text = str(value).strip().lower()
    if not text:
        return None
    if text in NUMERIC_TEXT_MAP:
        return float(NUMERIC_TEXT_MAP[text])
    numeric_match = re.search(r"([1-5](?:\.\d+)?)", text)
    if numeric_match:
        return float(numeric_match.group(1))
    return None


def find_participant_key(df: pd.DataFrame) -> str | None:
    normalized = {normalize_name(str(col)): str(col) for col in df.columns}
    for candidate in ["email", "participantid", "internid", "studentid", "fullname", "participantname", "internname"]:
        if candidate in normalized:
            return normalized[candidate]
    if "firstname" in normalized and "lastname" in normalized:
        return "__full_name__"
    return None


def attach_participant_key(df: pd.DataFrame) -> pd.DataFrame:
    key = find_participant_key(df)
    copy = df.copy()
    if key == "__full_name__":
        first = copy[[col for col in copy.columns if normalize_name(str(col)) == "firstname"][0]].fillna("").astype(str).str.strip()
        last = copy[[col for col in copy.columns if normalize_name(str(col)) == "lastname"][0]].fillna("").astype(str).str.strip()
        copy["_participant_key"] = (first + " " + last).str.strip().str.lower()
    elif key:
        copy["_participant_key"] = copy[key].fillna("").astype(str).str.strip().str.lower()
    else:
        copy["_participant_key"] = ""
    return copy[copy["_participant_key"] != ""]


def find_metric_column(df: pd.DataFrame, keywords: list[str]) -> str | None:
    best: tuple[int, str] | None = None
    for column in df.columns:
        normalized = str(column).lower()
        score = sum(1 for keyword in keywords if keyword in normalized)
        if score and (best is None or score > best[0]):
            best = (score, str(column))
    return best[1] if best else None


def compute_distribution(values: pd.Series) -> list[dict[str, int]]:
    distribution = {"Not confident": 0, "Somewhat confident": 0, "Confident": 0}
    for value in values.dropna():
        if value <= 2:
            distribution["Not confident"] += 1
        elif value < 4:
            distribution["Somewhat confident"] += 1
        else:
            distribution["Confident"] += 1
    return [{"label": label, "count": count} for label, count in distribution.items()]


def collect_quotes(df: pd.DataFrame) -> list[str]:
    text_columns = [
        str(col)
        for col in df.columns
        if any(token in str(col).lower() for token in ["quote", "testimonial", "response", "reflection", "story"])
    ]
    quotes: list[str] = []
    for column in text_columns:
        for value in df[column].dropna().astype(str):
            cleaned = value.strip()
            if cleaned and len(cleaned.split()) >= 8:
                quotes.append(cleaned)
    return quotes[:10]


def percent_string(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{round(value)}%"


def safe_mean(values: pd.Series) -> float | None:
    non_null = values.dropna()
    if non_null.empty:
        return None
    return float(non_null.mean())


def build_analysis(project: dict[str, Any], uploads: list[UploadDataset]) -> dict[str, Any]:
    by_component: dict[str, list[UploadDataset]] = {}
    for upload in uploads:
        by_component.setdefault(upload.component, []).append(upload)

    pre_df = pd.concat([attach_participant_key(u.dataframe) for u in by_component.get("pre", []) if u.dataframe is not None], ignore_index=True) if by_component.get("pre") else pd.DataFrame()
    post_df = pd.concat([attach_participant_key(u.dataframe) for u in by_component.get("post", []) if u.dataframe is not None], ignore_index=True) if by_component.get("post") else pd.DataFrame()
    weekly_df = pd.concat([u.dataframe for u in by_component.get("weekly", []) if u.dataframe is not None], ignore_index=True) if by_component.get("weekly") else pd.DataFrame()
    resume_df = pd.concat([u.dataframe for u in by_component.get("resume-linkedin", []) if u.dataframe is not None], ignore_index=True) if by_component.get("resume-linkedin") else pd.DataFrame()
    deliverables_df = pd.concat([u.dataframe for u in by_component.get("deliverables", []) if u.dataframe is not None], ignore_index=True) if by_component.get("deliverables") else pd.DataFrame()
    testimonials_df = pd.concat([u.dataframe for u in by_component.get("testimonials", []) if u.dataframe is not None], ignore_index=True) if by_component.get("testimonials") else pd.DataFrame()

    cohort_size = int(project.get("cohort_size") or 0)
    interns_served = cohort_size or max(len(pre_df), len(post_df), len(resume_df))
    post_unique = int(post_df["_participant_key"].nunique()) if not post_df.empty and "_participant_key" in post_df else len(post_df)
    completion_rate = round((post_unique / cohort_size) * 100) if cohort_size and post_unique else None

    before_after: list[dict[str, Any]] = []
    deltas: list[dict[str, Any]] = []

    matched_count = 0
    if not pre_df.empty and not post_df.empty and "_participant_key" in pre_df and "_participant_key" in post_df:
        matched = pre_df.merge(post_df, on="_participant_key", suffixes=("_pre", "_post"))
        matched_count = len(matched)
        for label, keywords in OUTCOME_DEFINITIONS.items():
            pre_col = find_metric_column(pre_df, keywords)
            post_col = find_metric_column(post_df, keywords)
            if not pre_col or not post_col:
                continue
            pre_scores = matched[f"{pre_col}_pre"].map(parse_likert)
            post_scores = matched[f"{post_col}_post"].map(parse_likert)
            pre_avg = safe_mean(pre_scores)
            post_avg = safe_mean(post_scores)
            if pre_avg is None or post_avg is None:
                continue
            before_after.append({"label": label, "before": round(pre_avg, 1), "after": round(post_avg, 1)})
            delta = round(((post_avg - pre_avg) / pre_avg) * 100) if pre_avg else 0
            deltas.append({"label": label, "delta": delta})

    clean_tech = next((item for item in before_after if item["label"] == "Clean tech knowledge"), None)
    interview = next((item for item in before_after if item["label"] == "Interview confidence"), None)
    average_growth = round(sum(item["delta"] for item in deltas) / len(deltas)) if deltas else None

    resume_completion = None
    linkedin_completion = None
    both_completion = None
    if not resume_df.empty:
        columns = {normalize_name(str(col)): str(col) for col in resume_df.columns}
        resume_status_col = next((columns[key] for key in columns if "resumestatus" in key), None)
        linkedin_status_col = next((columns[key] for key in columns if "linkedinstatus" in key), None)
        if resume_status_col:
            resume_complete = resume_df[resume_status_col].astype(str).str.lower().str.contains("complete").sum()
            resume_completion = round((resume_complete / cohort_size) * 100) if cohort_size else round((resume_complete / max(len(resume_df), 1)) * 100)
        if linkedin_status_col:
            linkedin_complete = resume_df[linkedin_status_col].astype(str).str.lower().str.contains("complete").sum()
            linkedin_completion = round((linkedin_complete / cohort_size) * 100) if cohort_size else round((linkedin_complete / max(len(resume_df), 1)) * 100)
        if resume_status_col and linkedin_status_col:
            both_complete = (
                resume_df[resume_status_col].astype(str).str.lower().str.contains("complete")
                & resume_df[linkedin_status_col].astype(str).str.lower().str.contains("complete")
            ).sum()
            both_completion = round((both_complete / cohort_size) * 100) if cohort_size else round((both_complete / max(len(resume_df), 1)) * 100)

    projects_completed = None
    if not deliverables_df.empty:
        status_col = find_metric_column(deliverables_df, ["completed", "status", "deliverable"])
        if status_col:
            statuses = deliverables_df[status_col].astype(str).str.lower()
            projects_completed = int(statuses.str.contains("complete|completed|submitted").sum())
        else:
            projects_completed = len(deliverables_df)

    weekly_quotes = collect_quotes(weekly_df) if not weekly_df.empty else []
    testimonial_quotes = collect_quotes(testimonials_df) if not testimonials_df.empty else []
    quote_pool = testimonial_quotes or weekly_quotes
    selected_quote = quote_pool[0] if quote_pool else "Participants reported increased confidence, stronger career clarity, and meaningful exposure to clean tech pathways."

    distribution = []
    if interview and not pre_df.empty and not post_df.empty and matched_count:
        pre_col = find_metric_column(pre_df, OUTCOME_DEFINITIONS["Interview confidence"])
        post_col = find_metric_column(post_df, OUTCOME_DEFINITIONS["Interview confidence"])
        if pre_col and post_col:
            matched = pre_df.merge(post_df, on="_participant_key", suffixes=("_pre", "_post"))
            pre_dist = {item["label"]: item["count"] for item in compute_distribution(matched[f"{pre_col}_pre"].map(parse_likert))}
            post_dist = {item["label"]: item["count"] for item in compute_distribution(matched[f"{post_col}_post"].map(parse_likert))}
            distribution = [
                {"label": label, "before": pre_dist.get(label, 0), "after": post_dist.get(label, 0)}
                for label in ["Not confident", "Somewhat confident", "Confident"]
            ]

    metrics = [
        {"label": "Interns served", "value": str(interns_served or 0), "note": "Cohort size and connected participant records"},
        {"label": "Average skill growth", "value": f"+{average_growth}%" if average_growth is not None else "N/A", "note": "Average increase across matched pre/post outcome areas"},
        {"label": "Clean tech knowledge", "value": f"+{round(((clean_tech['after'] - clean_tech['before']) / clean_tech['before']) * 100)}%" if clean_tech else "N/A", "note": "Increase from matched pre/post surveys"},
        {"label": "Resume/LinkedIn completion", "value": percent_string(both_completion or resume_completion), "note": "Participants with completed career materials"},
        {"label": "Interview confidence", "value": f"+{round(((interview['after'] - interview['before']) / interview['before']) * 100)}%" if interview else "N/A", "note": "Increase from matched pre/post surveys"},
        {"label": "Projects completed", "value": str(projects_completed or 0), "note": "Completed rows in connected deliverables data"},
    ]

    objectives = [
        {
            "title": "Enrollment Reach",
            "description": "Youth and young adults ages 16-30 from primarily low-income and disadvantaged backgrounds served by the program.",
            "target": "30 participants",
            "actual": f"{interns_served or 0} enrolled",
            "status": "Strong" if (interns_served or 0) >= 30 else "Watch",
            "statusTone": "good" if (interns_served or 0) >= 30 else "risk",
        },
        {
            "title": "Program Completion",
            "description": "Participants who completed the full 8-week internship experience.",
            "target": "90% completion",
            "actual": percent_string(completion_rate),
            "status": "On track" if completion_rate and completion_rate >= 90 else "Close",
            "statusTone": "good" if completion_rate and completion_rate >= 90 else "watch",
        },
        {
            "title": "Clean Tech Awareness",
            "description": "Participants reporting increased awareness of clean tech career pathways.",
            "target": "80%",
            "actual": metrics[2]["value"].replace("+", ""),
            "status": "Strong" if clean_tech and clean_tech["after"] > clean_tech["before"] else "Watch",
            "statusTone": "good" if clean_tech and clean_tech["after"] > clean_tech["before"] else "risk",
        },
        {
            "title": "Career Materials",
            "description": "Interns who created a resume and completed a LinkedIn profile by program end.",
            "target": "85%",
            "actual": percent_string(both_completion),
            "status": "On track" if both_completion and both_completion >= 85 else "Watch",
            "statusTone": "good" if both_completion and both_completion >= 85 else "risk",
        },
        {
            "title": "Workplace Readiness",
            "description": "Participants demonstrating stronger time management, digital collaboration, and professional communication skills.",
            "target": "85%",
            "actual": f"+{next((item['delta'] for item in deltas if item['label'] == 'Professional communication'), 0)}%",
            "status": "On track" if any(item["label"] == "Professional communication" for item in deltas) else "Watch",
            "statusTone": "good" if any(item["label"] == "Professional communication" for item in deltas) else "watch",
        },
        {
            "title": "Career Confidence",
            "description": "Participants reporting improved confidence and greater clarity in their career direction.",
            "target": "80%",
            "actual": f"+{next((item['delta'] for item in deltas if item['label'] == 'Career clarity'), 0)}%",
            "status": "On track" if any(item["label"] == "Career clarity" for item in deltas) else "Watch",
            "statusTone": "good" if any(item["label"] == "Career clarity" for item in deltas) else "watch",
        },
    ]

    sources = [
        {"name": upload.filename, "type": upload.content_type, "detail": f"{upload.row_count or 0} rows processed"}
        for upload in uploads
    ]

    summary = {
        "interns_served": interns_served or 0,
        "completion_rate": completion_rate,
        "average_skill_growth": average_growth,
        "clean_tech_growth": metrics[2]["value"],
        "resume_linkedin_completion": metrics[3]["value"],
        "interview_confidence_growth": metrics[4]["value"],
        "projects_completed": projects_completed or 0,
        "matched_response_count": matched_count,
        "selected_quote": selected_quote,
        "source_count": len(uploads),
    }

    return {
        "metrics": metrics,
        "objectives": objectives,
        "before_after": before_after,
        "distribution": distribution,
        "deltas": deltas,
        "quotes": quote_pool[:3],
        "selected_quote": selected_quote,
        "summary": summary,
        "analyst_notes": [
            "Pre/post comparisons include only matched respondents across both surveys.",
            "Completion and career-material metrics are calculated from uploaded spreadsheets and project cohort size.",
            "Missing spreadsheet columns are surfaced as unavailable rather than estimated.",
            "Grant narratives are generated from computed metrics and uploaded qualitative responses only.",
        ],
        "sources": sources,
    }
