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
    "not at all confident": 1,
    "slightly confident": 3,
    "somewhat confident": 3,
    "confident": 4,
    "very confident": 5,
    "not at all": 1,
    "a little": 2,
    "some": 3,
    "somewhat": 3,
    "quite a bit": 4,
    "a lot": 5,
    "very familiar": 5,
}

OUTCOME_DEFINITIONS = {
    "clean_tech_knowledge": [
        "how familiar are you with clean tech careers",
        "clean tech careers",
        "clean tech knowledge",
        "awareness of clean tech career pathways",
    ],
    "interview_confidence": [
        "how confident are you participating in a job interview",
        "job interview",
        "interview confidence",
    ],
    "resume_readiness": [
        "resume readiness",
        "resume confidence",
        "resume status",
    ],
    "career_clarity": [
        "career clarity",
        "career direction",
        "clarity in career direction",
    ],
    "workplace_readiness": [
        "professional workplace expectations",
        "workplace readiness",
    ],
    "communication_skills": [
        "communication skills",
        "rate your communication skills",
    ],
    "public_speaking_skills": [
        "public speaking skills",
        "rate your public speaking skills",
    ],
    "project_management_skills": [
        "project management skills",
        "rate your project management skills",
    ],
    "teamwork_skills": [
        "teamwork skills",
        "rate your teamwork skills",
    ],
    "research_skills": [
        "research skills",
        "rate your research skills",
    ],
    "professional_intro_confidence": [
        "introducing yourself to a professional",
        "introducing yourself",
    ],
    "leadership_confidence": [
        "taking initiative or leading a group",
        "leading a group",
        "taking initiative",
    ],
}

POST_PROGRAM_RATING_DEFINITIONS = {
    "professional_communication": "Professional Communication",
    "teamwork_skills": "Teamwork and Collaboration",
    "leadership_skills": "Leadership",
    "public_speaking_skills": "Public Speaking and Presentation",
    "networking_skills": "Networking with Professionals",
    "time_management_skills": "Time Management",
    "project_management_skills": "Project Management",
    "problem_solving_skills": "Problem-Solving",
    "taking_initiative": "Taking Initiative",
    "seeking_help": "Asking Questions and Seeking Help",
    "workplace_expectations": "Understanding Workplace Expectations",
    "workforce_readiness": "Workforce Readiness",
    "clean_tech_knowledge": "Understanding of Clean Technology & Sustainability",
}

OUTCOME_LABELS = {
    "professional_communication": "Professional communication",
    "teamwork_skills": "Teamwork and collaboration",
    "leadership_skills": "Leadership",
    "public_speaking_skills": "Public speaking and presentation",
    "networking_skills": "Networking with professionals",
    "time_management_skills": "Time management",
    "project_management_skills": "Project management",
    "problem_solving_skills": "Problem-solving",
    "taking_initiative": "Taking initiative",
    "seeking_help": "Asking questions and seeking help",
    "workplace_expectations": "Understanding workplace expectations",
    "workforce_readiness": "Workforce readiness",
    "clean_tech_knowledge": "Clean technology and sustainability understanding",
}

WORKPLACE_READINESS_KEYS = [
    "professional_communication",
    "public_speaking_skills",
    "project_management_skills",
    "teamwork_skills",
    "leadership_skills",
    "time_management_skills",
    "problem_solving_skills",
    "taking_initiative",
    "workplace_expectations",
    "workforce_readiness",
]

CAREER_CONFIDENCE_KEYS = [
    "networking_skills",
    "leadership_skills",
    "public_speaking_skills",
    "professional_communication",
]

HEADER_HINTS = (
    "timestamp",
    "name",
    "before",
    "after",
    "internship",
    "professional",
    "career",
    "week",
    "project",
    "deliverable",
    "linkedin",
    "resume",
    "verified",
    "impact",
    "testimonial",
    "quote",
    "response",
    "skill",
    "confidence",
    "familiar",
)


@dataclass
class UploadDataset:
    """Carry one uploaded source file and its parsed dataframe into the analysis layer."""
    component: str
    filename: str
    dataframe: pd.DataFrame | None
    content_type: str
    row_count: int | None
    summary: dict[str, Any]


def normalize_name(value: str) -> str:
    """Normalize headers and identifiers so loose column matching stays consistent."""
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _score_header_row(values: list[Any]) -> int:
    """Estimate which spreadsheet row is most likely to contain the real headers."""
    score = 0
    for value in values:
        text = str(value or "").strip().lower()
        if not text:
            continue
        if text.startswith("unnamed:"):
            continue
        score += 1
        if any(hint in text for hint in HEADER_HINTS):
            score += 2
        if len(text.split()) <= 6:
            score += 1
    return score


def _promote_header_row(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Convert the best detected header row into dataframe column names."""
    if raw_df.empty:
        return raw_df

    best_index = 0
    best_score = -1
    max_scan = min(len(raw_df), 8)
    for index in range(max_scan):
        row_values = raw_df.iloc[index].tolist()
        score = _score_header_row(row_values)
        if score > best_score:
            best_score = score
            best_index = index

    header = []
    for position, value in enumerate(raw_df.iloc[best_index].tolist()):
        text = str(value or "").strip()
        header.append(text or f"Unnamed: {position}")

    data = raw_df.iloc[best_index + 1 :].reset_index(drop=True).copy()
    data.columns = header
    data = data.dropna(how="all")
    return data


def read_spreadsheet(filename: str, content: bytes) -> pd.DataFrame:
    """Parse uploaded CSV/XLSX bytes into a cleaned dataframe with promoted headers."""
    lower = filename.lower()
    if lower.endswith(".csv"):
        raw_df = pd.read_csv(io.BytesIO(content), header=None)
        return _promote_header_row(raw_df)
    if lower.endswith(".xlsx"):
        raw_df = pd.read_excel(io.BytesIO(content), engine="openpyxl", header=None)
        return _promote_header_row(raw_df)
    raise ValueError("Unsupported spreadsheet format.")


def dataframe_summary(df: pd.DataFrame) -> dict[str, Any]:
    """Capture lightweight dataframe metadata for upload previews and debugging."""
    return {
        "columns": [str(col) for col in df.columns.tolist()],
        "rows": int(df.shape[0]),
        "sample": df.head(3).fillna("").astype(str).to_dict(orient="records"),
    }


def parse_likert(value: Any) -> float | None:
    """Convert survey text and numeric responses into a shared 1-5 scoring scale."""
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
    """Find the best column to use for matching the same participant across files."""
    normalized = {normalize_name(str(col)): str(col) for col in df.columns}
    for candidate in [
        "email",
        "participantidentifier",
        "participantid",
        "participantkey",
        "internid",
        "studentid",
        "fullname",
        "participantname",
        "internname",
        "namefirstlast",
        "firstlastname",
        "name",
    ]:
        if candidate in normalized:
            return normalized[candidate]
    if "firstname" in normalized and "lastname" in normalized:
        return "__full_name__"
    return None


def attach_participant_key(df: pd.DataFrame) -> pd.DataFrame:
    """Append a normalized participant key column used for cohort matching."""
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
    """Pick the survey column that best matches a requested outcome concept."""
    best: tuple[int, str] | None = None
    for column in df.columns:
        normalized = str(column).lower()
        score = sum(1 for keyword in keywords if keyword in normalized)
        if score and (best is None or score > best[0]):
            best = (score, str(column))
    return best[1] if best else None


def compute_distribution(values: pd.Series) -> list[dict[str, int]]:
    """Bucket confidence-style scores into simple share-of-cohort chart groups."""
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
    """Pull longer free-response text that can be reused in summaries and quotes."""
    text_columns = [
        str(col)
        for col in df.columns
        if any(
            token in str(col).lower()
            for token in [
                "quote",
                "testimonial",
                "response",
                "reflection",
                "story",
                "learned",
                "improved",
                "valuable",
                "grown",
                "career goals",
                "wish",
                "challenge",
                "future",
                "accomplishment",
            ]
        )
    ]
    quotes: list[str] = []
    for column in text_columns:
        for value in df[column].dropna().astype(str):
            cleaned = value.strip()
            if cleaned and len(cleaned.split()) >= 6:
                quotes.append(cleaned)
    return quotes[:10]


def percent_string(value: float | None) -> str:
    """Format optional percentage values into the portal display style."""
    if value is None:
        return "N/A"
    return f"{round(value)}%"


def safe_mean(values: pd.Series) -> float | None:
    """Return a mean only when there is real non-empty numeric data to average."""
    non_null = values.dropna()
    if non_null.empty:
        return None
    return float(non_null.mean())


def _unique_participants(df: pd.DataFrame) -> int:
    """Count unique participants from the normalized participant key column."""
    if df.empty or "_participant_key" not in df:
        return 0
    return int(df["_participant_key"].nunique())


def _build_outcome_lookup(df: pd.DataFrame) -> dict[str, str]:
    """Map each internal outcome key to the uploaded survey column that supports it."""
    return {
        key: column
        for key, keywords in OUTCOME_DEFINITIONS.items()
        if (column := find_metric_column(df, keywords))
    }


def find_post_program_survey_outcomes(df: pd.DataFrame) -> dict[str, tuple[str, str]]:
    """Locate paired before/after rating columns in the HUMANBULB post-program survey."""
    outcomes: dict[str, tuple[str, str]] = {}
    normalized_headers = [(str(column), normalize_name(str(column))) for column in df.columns]
    before_marker = normalize_name("before the internship")
    after_marker = normalize_name("after the internship")

    for key, survey_label in POST_PROGRAM_RATING_DEFINITIONS.items():
        normalized_label = normalize_name(survey_label)
        before_column = next(
            (column for column, header in normalized_headers if before_marker in header and normalized_label in header),
            None,
        )
        after_column = next(
            (column for column, header in normalized_headers if after_marker in header and normalized_label in header),
            None,
        )
        if before_column and after_column:
            outcomes[key] = (before_column, after_column)
    return outcomes


def _paired_outcome_delta(survey_df: pd.DataFrame, before_col: str, after_col: str) -> tuple[float | None, float | None, float | None, float | None]:
    """Calculate before/after change from paired ratings in one participant survey row."""
    pre_scores = survey_df[before_col].map(parse_likert)
    post_scores = survey_df[after_col].map(parse_likert)
    mask = pre_scores.notna() & post_scores.notna()
    pre_scores = pre_scores[mask]
    post_scores = post_scores[mask]
    pre_avg = safe_mean(pre_scores)
    post_avg = safe_mean(post_scores)
    if pre_avg is None or post_avg is None:
        return None, None, None, None
    absolute_change = post_avg - pre_avg
    percent_change = ((absolute_change / pre_avg) * 100) if pre_avg else None
    improved_rate = float(((post_scores - pre_scores) > 0).dropna().mean() * 100) if not pre_scores.dropna().empty else None
    return pre_avg, post_avg, absolute_change, percent_change if percent_change is not None else None


def _paired_improved_rate(survey_df: pd.DataFrame, before_col: str, after_col: str) -> float | None:
    """Measure the share of respondents whose paired rating increased for one outcome."""
    pre_scores = survey_df[before_col].map(parse_likert)
    post_scores = survey_df[after_col].map(parse_likert)
    mask = pre_scores.notna() & post_scores.notna()
    if not mask.any():
        return None
    return float(((post_scores[mask] - pre_scores[mask]) > 0).mean() * 100)


def _paired_composite_frame(survey_df: pd.DataFrame, outcome_pairs: dict[str, tuple[str, str]], keys: list[str]) -> tuple[pd.Series | None, pd.Series | None]:
    """Build before/after composite score series from related paired survey items."""
    pre_columns: list[pd.Series] = []
    post_columns: list[pd.Series] = []
    for key in keys:
        pair = outcome_pairs.get(key)
        if not pair:
            continue
        before_col, after_col = pair
        pre_columns.append(survey_df[before_col].map(parse_likert))
        post_columns.append(survey_df[after_col].map(parse_likert))
    if not pre_columns or not post_columns:
        return None, None
    pre_scores = pd.concat(pre_columns, axis=1).mean(axis=1, skipna=True)
    post_scores = pd.concat(post_columns, axis=1).mean(axis=1, skipna=True)
    return pre_scores, post_scores


def _composite_improvement(pre_scores: pd.Series | None, post_scores: pd.Series | None) -> tuple[float | None, float | None]:
    """Summarize improvement rate and mean percent change for a composite metric."""
    if pre_scores is None or post_scores is None:
        return None, None
    mask = pre_scores.notna() & post_scores.notna()
    if not mask.any():
        return None, None
    percent_improved = float(((post_scores[mask] - pre_scores[mask]) > 0).mean() * 100)
    pre_avg = float(pre_scores[mask].mean())
    post_avg = float(post_scores[mask].mean())
    mean_delta = ((post_avg - pre_avg) / pre_avg) * 100 if pre_avg else None
    return percent_improved, mean_delta


def _nonempty_count(series: pd.Series) -> int:
    """Count rows that contain a real non-blank value."""
    return int(series.fillna("").astype(str).str.strip().ne("").sum())


def _rate(count: int, denominator: int) -> float | None:
    """Turn a raw count into a percentage when a valid denominator exists."""
    if denominator <= 0:
        return None
    return float((count / denominator) * 100)


def _status_from_target(actual: float | None, target: float) -> tuple[str, str]:
    """Translate actual performance against a target into the portal status labels."""
    if actual is None:
        return "Pending", "watch"
    if actual >= target:
        return "Strong", "good"
    if actual >= target - 10:
        return "Close", "watch"
    return "Watch", "risk"


def build_analysis(project: dict[str, Any], uploads: list[UploadDataset]) -> dict[str, Any]:
    """Combine all validated uploads into the dashboard, analytics, and grant outputs."""
    by_component: dict[str, list[UploadDataset]] = {}
    for upload in uploads:
        by_component.setdefault(upload.component, []).append(upload)

    post_program_df = pd.concat([attach_participant_key(u.dataframe) for u in by_component.get("post-program", []) if u.dataframe is not None], ignore_index=True) if by_component.get("post-program") else pd.DataFrame()
    weekly_df = pd.concat([attach_participant_key(u.dataframe) for u in by_component.get("weekly", []) if u.dataframe is not None], ignore_index=True) if by_component.get("weekly") else pd.DataFrame()
    resume_df = pd.concat([attach_participant_key(u.dataframe) for u in by_component.get("resume-linkedin", []) if u.dataframe is not None], ignore_index=True) if by_component.get("resume-linkedin") else pd.DataFrame()
    deliverables_df = pd.concat([attach_participant_key(u.dataframe) for u in by_component.get("deliverables", []) if u.dataframe is not None], ignore_index=True) if by_component.get("deliverables") else pd.DataFrame()
    testimonials_df = pd.concat([attach_participant_key(u.dataframe) for u in by_component.get("testimonials", []) if u.dataframe is not None], ignore_index=True) if by_component.get("testimonials") else pd.DataFrame()

    outcome_pairs = find_post_program_survey_outcomes(post_program_df) if not post_program_df.empty else {}
    matched_count = _unique_participants(post_program_df)

    cohort_size = int(project.get("cohort_size") or 0)
    participant_counts = [
        _unique_participants(df)
        for df in [post_program_df, weekly_df, resume_df, deliverables_df, testimonials_df]
    ]
    interns_served = cohort_size or max(participant_counts or [0])

    before_after: list[dict[str, Any]] = []
    deltas: list[dict[str, Any]] = []
    improved_rates: dict[str, float | None] = {}

    if not post_program_df.empty:
        for key, label in OUTCOME_LABELS.items():
            pair = outcome_pairs.get(key)
            if not pair:
                continue
            before_col, after_col = pair
            pre_avg, post_avg, _absolute_change, percent_change = _paired_outcome_delta(post_program_df, before_col, after_col)
            if pre_avg is None or post_avg is None:
                continue
            before_after.append({"label": label, "before": round(pre_avg, 1), "after": round(post_avg, 1)})
            deltas.append({"label": label, "delta": round(percent_change or 0)})
            improved_rates[key] = _paired_improved_rate(post_program_df, before_col, after_col)

    workplace_pre, workplace_post = _paired_composite_frame(post_program_df, outcome_pairs, WORKPLACE_READINESS_KEYS)
    workplace_improved_rate, workplace_mean_delta = _composite_improvement(workplace_pre, workplace_post)

    confidence_pre, confidence_post = _paired_composite_frame(post_program_df, outcome_pairs, CAREER_CONFIDENCE_KEYS)
    confidence_improved_rate, confidence_mean_delta = _composite_improvement(confidence_pre, confidence_post)

    clean_tech_improved_rate = improved_rates.get("clean_tech_knowledge")

    columns = {normalize_name(str(col)): str(col) for col in resume_df.columns} if not resume_df.empty else {}
    linkedin_col = next((col for key, col in columns.items() if "linkedinurl" in key), None)
    resume_col = next((col for key, col in columns.items() if "resumeurl" in key), None)
    verified_col = next((col for key, col in columns.items() if "staffverifiedresume" in key or "verifiedresume" in key), None)

    denominator = cohort_size or _unique_participants(resume_df) or 0
    linkedin_completed_count = _nonempty_count(resume_df[linkedin_col]) if linkedin_col else 0
    resume_completed_count = _nonempty_count(resume_df[resume_col]) if resume_col else 0
    both_completed_count = 0
    resume_verified_count = 0
    if linkedin_col and resume_col:
        both_completed_count = int(
            (
                resume_df[linkedin_col].fillna("").astype(str).str.strip().ne("")
                & resume_df[resume_col].fillna("").astype(str).str.strip().ne("")
            ).sum()
        )
    if verified_col:
        verified_values = resume_df[verified_col].fillna("").astype(str).str.lower()
        resume_verified_count = int(verified_values.isin({"true", "1", "yes", "y", "checked", "x"}).sum())

    linkedin_completion_rate = _rate(linkedin_completed_count, denominator)
    resume_completion_rate = _rate(resume_completed_count, denominator)
    both_completion_rate = _rate(both_completed_count, denominator)
    resume_verified_rate = _rate(resume_verified_count, denominator)

    program_completion_rate = None

    deliverable_columns = {normalize_name(str(col)): str(col) for col in deliverables_df.columns} if not deliverables_df.empty else {}
    project_col = next((col for key, col in deliverable_columns.items() if "projectinitiative" in key or "projectorinitiative" in key), None)
    category_col = next((col for key, col in deliverable_columns.items() if key == "category" or "deliverablecategory" in key), None)
    link_col = next((col for key, col in deliverable_columns.items() if "linktodeliverable" in key or "deliverablelink" in key), None)
    impact_col = next((col for key, col in deliverable_columns.items() if "impactevidence" in key or key == "impact" or key == "evidence"), None)
    week_col = next((col for key, col in deliverable_columns.items() if key == "week"), None)

    deliverables_total = int(len(deliverables_df))
    unique_projects = int(deliverables_df[project_col].fillna("").astype(str).str.strip().replace("", pd.NA).dropna().nunique()) if project_col else 0
    deliverables_with_links = _nonempty_count(deliverables_df[link_col]) if link_col else 0
    deliverables_with_impact_notes = _nonempty_count(deliverables_df[impact_col]) if impact_col else 0

    deliverables_by_category: dict[str, int] = {}
    if category_col:
        category_series = deliverables_df[category_col].fillna("").astype(str).str.strip()
        deliverables_by_category = {
            label: int(count)
            for label, count in category_series[category_series != ""].value_counts().to_dict().items()
        }

    deliverables_by_week: dict[str, int] = {}
    if week_col:
        week_series = deliverables_df[week_col].dropna().astype(str).str.strip()
        deliverables_by_week = {
            label: int(count)
            for label, count in week_series[week_series != ""].value_counts().sort_index().to_dict().items()
        }

    weekly_count = int(len(weekly_df))
    weekly_unique_participants = _unique_participants(weekly_df)
    weeks_observed = sorted(
        {
            str(value).strip()
            for value in weekly_df[next((col for col in weekly_df.columns if normalize_name(str(col)) == "week"), "")]
            .dropna()
            .astype(str)
            if str(value).strip()
        }
    ) if not weekly_df.empty and any(normalize_name(str(col)) == "week" for col in weekly_df.columns) else []

    weekly_quotes = collect_quotes(weekly_df) if not weekly_df.empty else []
    testimonial_quotes = collect_quotes(testimonials_df) if not testimonials_df.empty else []
    quote_pool = testimonial_quotes or weekly_quotes
    selected_quote = quote_pool[0] if quote_pool else "Participants reported meaningful growth, stronger confidence, and increased exposure to career pathways."

    distribution = []
    networking_pair = outcome_pairs.get("networking_skills")
    if networking_pair:
        before_col, after_col = networking_pair
        pre_dist = {item["label"]: item["count"] for item in compute_distribution(post_program_df[before_col].map(parse_likert))}
        post_dist = {item["label"]: item["count"] for item in compute_distribution(post_program_df[after_col].map(parse_likert))}
        distribution = [
            {"label": label, "before": pre_dist.get(label, 0), "after": post_dist.get(label, 0)}
            for label in ["Not confident", "Somewhat confident", "Confident"]
        ]

    average_skill_growth = workplace_mean_delta

    metrics = [
        {"label": "Interns served", "value": str(interns_served or 0), "note": "Cohort size or the largest connected participant set."},
        {"label": "Clean tech understanding improved", "value": percent_string(clean_tech_improved_rate), "note": "Based on paired before/after understanding of clean technology and sustainability ratings."},
        {"label": "Workplace readiness improved", "value": percent_string(workplace_improved_rate), "note": "Composite of the paired before/after professional skill ratings in the post-program survey."},
        {"label": "Resume + LinkedIn completed", "value": percent_string(both_completion_rate), "note": "Participants with both a resume URL and LinkedIn URL in the tracker."},
        {"label": "Career confidence improved", "value": percent_string(confidence_improved_rate), "note": "Composite of paired networking, leadership, presentation, and communication ratings."},
        {"label": "Deliverables logged", "value": str(deliverables_total), "note": "Total rows in the deliverables tracker."},
    ]

    enrollment_status, enrollment_tone = _status_from_target(float(interns_served or 0), 30)
    awareness_status, awareness_tone = _status_from_target(clean_tech_improved_rate, 80)
    career_materials_status, career_materials_tone = _status_from_target(both_completion_rate, 85)
    workplace_status, workplace_tone = _status_from_target(workplace_improved_rate, 85)
    confidence_status, confidence_tone = _status_from_target(confidence_improved_rate, 80)

    objectives = [
        {
            "title": "Enrollment Reach",
            "description": "Youth and young adults ages 16–30 from primarily low-income and disadvantaged backgrounds served by the program.",
            "target": "30 participants",
            "actual": f"{interns_served or 0} enrolled",
            "status": enrollment_status,
            "statusTone": enrollment_tone,
        },
        {
            "title": "Clean Tech Awareness",
            "description": "Participants reporting increased understanding of clean technology and sustainability.",
            "target": "80%",
            "actual": percent_string(clean_tech_improved_rate),
            "status": awareness_status,
            "statusTone": awareness_tone,
        },
        {
            "title": "Career Materials",
            "description": "Interns who created a resume and completed a LinkedIn profile by program end.",
            "target": "85%",
            "actual": percent_string(both_completion_rate),
            "status": career_materials_status,
            "statusTone": career_materials_tone,
        },
        {
            "title": "Workplace Readiness",
            "description": "Participants demonstrating stronger workplace readiness across the paired professional-skill ratings in the post-program survey.",
            "target": "85%",
            "actual": percent_string(workplace_improved_rate),
            "status": workplace_status,
            "statusTone": workplace_tone,
        },
        {
            "title": "Career Confidence",
            "description": "Participants reporting improved confidence in professional and career-related settings, including networking, communication, presentations, and leadership.",
            "target": "80%",
            "actual": percent_string(confidence_improved_rate),
            "status": confidence_status,
            "statusTone": confidence_tone,
        },
    ]

    sources = [
        {"name": upload.filename, "type": upload.content_type, "detail": f"{upload.row_count or 0} rows processed"}
        for upload in uploads
    ]

    summary = {
        "cohort_size": cohort_size,
        "interns_served": interns_served or 0,
        "interns_with_post_program_survey": _unique_participants(post_program_df),
        "matched_response_count": matched_count,
        "weekly_checkin_count": weekly_count,
        "weekly_unique_participants": weekly_unique_participants,
        "deliverables_total": deliverables_total,
        "unique_projects_or_initiatives": unique_projects,
        "deliverables_with_links": deliverables_with_links,
        "deliverables_with_impact_notes": deliverables_with_impact_notes,
        "resume_completed_count": resume_completed_count,
        "linkedin_completed_count": linkedin_completed_count,
        "both_completed_count": both_completed_count,
        "resume_verified_count": resume_verified_count,
        "program_completion_rate": program_completion_rate,
        "average_skill_growth": percent_string(average_skill_growth),
        "clean_tech_growth": percent_string(clean_tech_improved_rate),
        "resume_linkedin_completion": percent_string(both_completion_rate),
        "career_confidence_growth": percent_string(confidence_improved_rate),
        "projects_completed": deliverables_total,
        "selected_quote": selected_quote,
        "source_count": len(uploads),
    }

    analyst_notes = [
        "Before/after comparisons use each respondent's paired self-ratings from the post-program survey.",
        "Career confidence is measured from paired networking, communication, presentation, and leadership ratings.",
        "Resume and LinkedIn metrics are calculated from uploaded tracker URLs and staff verification fields, not estimated.",
        "Weekly check-ins and deliverables provide supporting evidence, project activity context, and qualitative reporting themes.",
    ]

    if not weeks_observed:
        analyst_notes.append("Weekly progress check uploads currently do not include an explicit week field, so engagement is summarized without week-by-week breakdowns.")
    if not matched_count:
        analyst_notes.append("Before/after outcome comparisons will populate once the post-program survey is uploaded.")

    return {
        "metrics": metrics,
        "objectives": objectives,
        "before_after": before_after,
        "distribution": distribution,
        "deltas": deltas,
        "quotes": quote_pool[:3],
        "selected_quote": selected_quote,
        "summary": summary,
        "analyst_notes": analyst_notes,
        "sources": sources,
        "weekly_summary": {
            "weekly_checkin_count": weekly_count,
            "weekly_unique_participants": weekly_unique_participants,
            "weeks_observed": weeks_observed,
        },
        "deliverables_summary": {
            "deliverables_total": deliverables_total,
            "deliverables_by_category": deliverables_by_category,
            "deliverables_by_week": deliverables_by_week,
            "unique_projects_or_initiatives": unique_projects,
        },
    }
