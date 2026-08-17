from __future__ import annotations

from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_styles() -> dict[str, ParagraphStyle]:
    styles = getSampleStyleSheet()
    return {
        "eyebrow": ParagraphStyle("Eyebrow", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=7.2, leading=8.2, textColor=colors.HexColor("#6B7C8E")),
        "title": ParagraphStyle("Title", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=15.6, leading=17.2, textColor=colors.HexColor("#0F2747")),
        "subtitle": ParagraphStyle("Subtitle", parent=styles["BodyText"], fontSize=7.7, leading=9.0, textColor=colors.HexColor("#55697A")),
        "body": ParagraphStyle("Body", parent=styles["BodyText"], fontSize=7.25, leading=8.8, textColor=colors.HexColor("#21374C")),
        "metric_value": ParagraphStyle("MetricValue", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, leading=12.4, alignment=TA_LEFT, textColor=colors.HexColor("#0F2747")),
        "metric_label": ParagraphStyle("MetricLabel", parent=styles["BodyText"], fontSize=6.6, leading=7.8, textColor=colors.HexColor("#55697A")),
        "quote": ParagraphStyle("Quote", parent=styles["BodyText"], fontName="Helvetica-Oblique", fontSize=7.5, leading=9.6, textColor=colors.HexColor("#15345B")),
        "meta_label": ParagraphStyle("MetaLabel", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=6.4, leading=7.4, textColor=colors.HexColor("#6B7C8E")),
        "meta_value": ParagraphStyle("MetaValue", parent=styles["BodyText"], fontSize=7.55, leading=9.1, textColor=colors.HexColor("#1C3552")),
    }


def section_box(
    title: str,
    body: Any,
    width: float,
    *,
    background: str = "#FFFFFF",
    border: str = "#D8E1EA",
    min_body_height: float | None = None,
) -> Table:
    styles = build_styles()
    row_heights = [None, min_body_height] if min_body_height else None
    table = Table([[Paragraph(title, styles["eyebrow"])], [body]], colWidths=[width], rowHeights=row_heights)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(background)),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor(border)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def draw_page(canvas, doc) -> None:
    width, height = letter
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#F7FAFC"))
    canvas.rect(0, 0, width, height, stroke=0, fill=1)
    canvas.setFillColor(colors.HexColor("#0F2747"))
    canvas.rect(0, height - 28, width, 28, stroke=0, fill=1)
    canvas.setStrokeColor(colors.HexColor("#D8E1EA"))
    canvas.setLineWidth(0.75)
    canvas.line(doc.leftMargin, 32, width - doc.rightMargin, 32)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#6B7C8E"))
    canvas.drawString(doc.leftMargin, 20, "HUMANBULB Impact Portal")
    canvas.drawCentredString(width / 2, 20, "Green Careers Launchpad")
    canvas.drawRightString(width - doc.rightMargin, 20, "Page 1 of 1")
    canvas.restoreState()


def compact_quote(text: str, max_chars: int = 170) -> str:
    """Trim long testimonial text to a short quote-friendly excerpt."""
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= max_chars:
        return normalized
    sentence_break = normalized[:max_chars].rfind(". ")
    cutoff = sentence_break + 1 if sentence_break > 90 else max_chars - 3
    return f"{normalized[:cutoff].strip()}..."


def build_project_summary(project: dict[str, Any], analysis: dict[str, Any]) -> str:
    """Summarize the program model using only uploaded project evidence."""
    metrics = analysis.get("metrics", [])
    objectives = analysis.get("objectives", [])
    interns_served = next((metric["value"] for metric in metrics if "interns served" in metric["label"].lower()), "N/A")
    deliverables_logged = next((metric["value"] for metric in metrics if "deliverables" in metric["label"].lower()), "N/A")
    career_materials = next((objective["actual"] for objective in objectives if "career materials" in objective["title"].lower()), "N/A")
    return (
        "Green Careers Launchpad combines clean-tech career exposure, workplace-readiness development, and project-based learning for youth interns. "
        f"The current reporting set reflects {interns_served} interns served, {deliverables_logged} deliverables logged, "
        f"and {career_materials} achievement on resume and LinkedIn completion based on connected tracker records."
    )


def expand_executive_summary(summary: str, analysis: dict[str, Any]) -> str:
    """Expand the executive summary with grounded milestone context."""
    metrics = analysis.get("metrics", [])
    objectives = analysis.get("objectives", [])
    interns_served = next((metric["value"] for metric in metrics if "interns served" in metric["label"].lower()), "N/A")
    clean_tech_goal = next((objective for objective in objectives if "clean tech awareness" in objective["title"].lower()), None)
    workplace_goal = next((objective for objective in objectives if "workplace readiness" in objective["title"].lower()), None)
    details = [
        f"The current dataset captures {interns_served} interns served across the connected reporting period.",
        f"Clean-tech awareness currently tracks against a goal of {clean_tech_goal['target']} with {clean_tech_goal['actual']} achieved." if clean_tech_goal else "",
        f"Workplace-readiness growth currently tracks against a goal of {workplace_goal['target']} with {workplace_goal['actual']} achieved." if workplace_goal else "",
    ]
    return " ".join([summary.strip(), *[detail for detail in details if detail]]).strip()


def expand_grant_summary(summary: str, analysis: dict[str, Any]) -> str:
    """Expand the closing grant-ready summary with concrete measurable outcomes."""
    objectives = analysis.get("objectives", [])
    milestone_sentences = []
    for objective in objectives[:3]:
        milestone_sentences.append(
            f"{objective['title']} is currently measured against a goal of {objective['target']} with {objective['actual']} achieved."
        )
    metrics = analysis.get("metrics", [])
    interns_served = next((metric["value"] for metric in metrics if "interns served" in metric["label"].lower()), "N/A")
    deliverables_logged = next((metric["value"] for metric in metrics if "deliverables" in metric["label"].lower()), "N/A")
    weekly_themes = analysis.get("weekly_themes") or []
    theme_sentence = ""
    if weekly_themes:
        theme_sentence = f"Weekly reflections most often highlighted {', '.join(weekly_themes[:3])} as recurring areas of learning and contribution."
    close_sentence = (
        f"This reporting set documents {interns_served} interns served and {deliverables_logged} deliverables captured in verified program records."
    )
    return " ".join([summary.strip(), close_sentence, theme_sentence, *milestone_sentences]).strip()


def generate_grant_pdf(project: dict[str, Any], analysis: dict[str, Any], narrative: dict[str, Any]) -> bytes:
    styles = build_styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=0.45 * inch, rightMargin=0.45 * inch, topMargin=0.48 * inch, bottomMargin=0.5 * inch)
    story: list[Any] = []
    participant_quotes = [compact_quote(quote) for quote in narrative.get("participant_quotes", []) if str(quote or "").strip()][:3]
    if not participant_quotes and narrative.get("participant_quote"):
        participant_quotes = [compact_quote(narrative["participant_quote"])]
    project_summary = build_project_summary(project, analysis)
    executive_summary = expand_executive_summary(narrative["executive_summary"], analysis)
    grant_ready_summary = expand_grant_summary(narrative["grant_narrative"], analysis)

    story.append(Paragraph("Green Careers Launchpad", styles["eyebrow"]))
    story.append(Paragraph(f"{project['name']} Impact Summary", styles["title"]))
    story.append(Paragraph("One-page impact brief for external reporting and grant submissions", styles["subtitle"]))
    story.append(Spacer(1, 0.05 * inch))
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#D8E1EA")))
    story.append(Spacer(1, 0.06 * inch))

    reporting_period = project.get("reporting_period") or f"{project.get('cohort_year', 'Current')} cohort"

    meta = Table(
        [[
            Paragraph("Prepared for", styles["meta_label"]),
            Paragraph("Data sources", styles["meta_label"]),
            Paragraph("Reporting period", styles["meta_label"]),
        ], [
            Paragraph("Leadership and funders", styles["meta_value"]),
            Paragraph("Surveys, trackers, testimonials", styles["meta_value"]),
            Paragraph(reporting_period, styles["meta_value"]),
    ]],
        colWidths=[2.4 * inch, 2.4 * inch, 2.4 * inch],
    )
    meta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FBFD")),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#D8E1EA")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E7EDF3")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 4),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
        ("TOPPADDING", (0, 1), (-1, 1), 1),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 5),
    ]))
    story.append(meta)
    story.append(Spacer(1, 0.06 * inch))

    story.append(section_box("Executive Summary", Paragraph(executive_summary, styles["body"]), 7.2 * inch, background="#FFFFFF"))
    story.append(Spacer(1, 0.05 * inch))

    project_block = section_box(
        "Project",
        Paragraph(project_summary, styles["body"]),
        3.68 * inch,
        background="#F8FBFE",
        min_body_height=1.4 * inch,
    )
    metric_cards = []
    metric_backgrounds = ["#F8FCFB", "#F8FBFE", "#FCFAF3", "#FAF8FD"]
    for index, metric in enumerate(analysis["metrics"][:4]):
        card = Table(
            [[Paragraph(metric["value"], styles["metric_value"]), Paragraph(metric["label"], styles["metric_label"])]],
            colWidths=[0.58 * inch, 1.0 * inch],
        )
        card.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(metric_backgrounds[index])),
            ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#D8E1EA")),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        metric_cards.append(card)

    metric_rows = [
        metric_cards[:2],
        metric_cards[2:4] if len(metric_cards) > 2 else [],
    ]
    normalized_rows = []
    for row in metric_rows:
        padded_row = list(row)
        while len(padded_row) < 2:
            padded_row.append(Paragraph("", styles["body"]))
        normalized_rows.append(padded_row)

    metrics_table = Table(normalized_rows, colWidths=[1.67 * inch, 1.67 * inch], rowHeights=[0.54 * inch, 0.54 * inch])
    metrics_table.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    outcomes_snapshot = section_box(
        "Outcomes Snapshot",
        metrics_table,
        3.52 * inch,
        background="#FFFFFF",
        min_body_height=1.4 * inch,
    )
    project_snapshot_row = Table([[project_block, outcomes_snapshot]], colWidths=[3.68 * inch, 3.52 * inch], rowHeights=[1.82 * inch])
    project_snapshot_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(project_snapshot_row)
    story.append(Spacer(1, 0.05 * inch))

    objective_rows = []
    objectives = analysis["objectives"]
    last_row_index = None
    for index in range(0, len(objectives), 2):
        left = objectives[index]
        right = objectives[index + 1] if index + 1 < len(objectives) else None
        left_text = Paragraph(
            f"<b>{left['title']}</b><br/>{left['description']}<br/><font color='#55697A'>Goal: {left['target']}</font><br/><font color='#0F2747'><b>Achieved: {left['actual']}</b></font>",
            styles["body"],
        )
        right_text = (
            Paragraph(
                f"<b>{right['title']}</b><br/>{right['description']}<br/><font color='#55697A'>Goal: {right['target']}</font><br/><font color='#0F2747'><b>Achieved: {right['actual']}</b></font>",
                styles["body"],
            )
            if right
            else Paragraph("", styles["body"])
        )
        objective_rows.append([left_text, right_text])
        if not right:
            last_row_index = len(objective_rows) - 1
    objectives_table = Table(objective_rows, colWidths=[3.48 * inch, 3.48 * inch])
    objective_table_styles = [
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#FBFCFE")]),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#D8E1EA")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E7EDF3")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    if last_row_index is not None:
        objective_table_styles.extend(
            [
                ("SPAN", (0, last_row_index), (1, last_row_index)),
                ("BACKGROUND", (0, last_row_index), (1, last_row_index), colors.white),
            ]
        )
    objectives_table.setStyle(TableStyle(objective_table_styles))
    story.append(section_box("Outcomes", objectives_table, 7.2 * inch, background="#FFFFFF"))
    story.append(Spacer(1, 0.05 * inch))

    credibility_items = [Paragraph(f"• \"{quote}\"", styles["quote"]) for quote in participant_quotes]
    credibility_body: Any
    if credibility_items:
        credibility_body = Table([[item] for item in credibility_items], colWidths=[2.38 * inch])
        credibility_body.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), -3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
    else:
        credibility_body = Paragraph("Participant testimonials will populate here after testimonial responses are uploaded.", styles["body"])

    lower = Table(
        [[
            section_box("Credibility", credibility_body, 2.62 * inch, background="#F8FBFE", min_body_height=1.55 * inch),
            section_box("Grant-Ready Summary", Paragraph(grant_ready_summary, styles["body"]), 4.38 * inch, background="#FFFCF1", min_body_height=1.55 * inch),
        ]],
        colWidths=[2.8 * inch, 4.5 * inch],
    )
    lower.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), -6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(lower)

    doc.build(story, onFirstPage=draw_page)
    return buffer.getvalue()
