"""
This file is essentially a template engine for a one-page impact report. It takes structured data (project, analysis, and narrative) and produces a professional-looking PDF with:

A branded header and footer
Project title and reporting information
Executive summary
Four headline KPI cards
A table of program objectives versus actual outcomes
A participant testimonial
A grant-ready narrative
"""
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
        "eyebrow": ParagraphStyle("Eyebrow", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=8, leading=9, textColor=colors.HexColor("#6B7C8E")),
        "title": ParagraphStyle("Title", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=17, leading=20, textColor=colors.HexColor("#0F2747")),
        "subtitle": ParagraphStyle("Subtitle", parent=styles["BodyText"], fontSize=8.5, leading=10, textColor=colors.HexColor("#55697A")),
        "body": ParagraphStyle("Body", parent=styles["BodyText"], fontSize=8.3, leading=10.6, textColor=colors.HexColor("#21374C")),
        "metric_value": ParagraphStyle("MetricValue", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13, leading=14, alignment=TA_LEFT, textColor=colors.HexColor("#0F2747")),
        "metric_label": ParagraphStyle("MetricLabel", parent=styles["BodyText"], fontSize=7.2, leading=8.6, textColor=colors.HexColor("#55697A")),
        "quote": ParagraphStyle("Quote", parent=styles["BodyText"], fontName="Helvetica-Oblique", fontSize=9, leading=12, textColor=colors.HexColor("#15345B")),
    }


def section_box(title: str, body: Any, width: float) -> Table:
    styles = build_styles()
    table = Table([[Paragraph(title, styles["eyebrow"])], [body]], colWidths=[width])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#D8E1EA")),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def draw_page(canvas, doc) -> None:
    width, height = letter
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#F5F8FB"))
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


def generate_grant_pdf(project: dict[str, Any], analysis: dict[str, Any], narrative: dict[str, str]) -> bytes:
    styles = build_styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch, topMargin=0.58 * inch, bottomMargin=0.62 * inch)
    story: list[Any] = []

    story.append(Paragraph("Green Careers Launchpad", styles["eyebrow"]))
    story.append(Paragraph(f"{project['name']} Impact Summary", styles["title"]))
    story.append(Paragraph("One-page impact brief for external reporting and grant submissions", styles["subtitle"]))
    story.append(Spacer(1, 0.09 * inch))
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#D8E1EA")))
    story.append(Spacer(1, 0.1 * inch))

    meta = Table(
        [[
            Paragraph("<b>Prepared for</b><br/>Leadership and funders", styles["body"]),
            Paragraph("<b>Data sources</b><br/>Surveys, trackers, testimonials", styles["body"]),
            Paragraph(f"<b>Reporting period</b><br/>{project.get('cohort_year', 'Current')} cohort", styles["body"]),
        ]],
        colWidths=[2.15 * inch, 2.15 * inch, 2.15 * inch],
    )
    meta.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.white), ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#D8E1EA")), ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E7EDF3")), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story.append(meta)
    story.append(Spacer(1, 0.1 * inch))

    story.append(section_box("Executive Summary", Paragraph(narrative["executive_summary"], styles["body"]), 6.9 * inch))
    story.append(Spacer(1, 0.08 * inch))

    metric_cards = []
    for metric in analysis["metrics"][:4]:
        card = Table([[Paragraph(metric["value"], styles["metric_value"]), Paragraph(metric["label"], styles["metric_label"])]], colWidths=[0.52 * inch, 1.06 * inch])
        card.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FAFC")), ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#D8E1EA")), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        metric_cards.append(card)
    metrics_table = Table([metric_cards], colWidths=[1.72 * inch] * 4)
    story.append(section_box("Headline Outcomes", metrics_table, 6.9 * inch))
    story.append(Spacer(1, 0.08 * inch))

    objective_rows = []
    objectives = analysis["objectives"]
    for index in range(0, len(objectives), 2):
        left = objectives[index]
        right = objectives[index + 1] if index + 1 < len(objectives) else None
        left_text = Paragraph(f"<b>{left['title']}</b><br/>{left['target']}<br/><font color='#0F2747'><b>{left['actual']}</b></font>", styles["body"])
        right_text = Paragraph(f"<b>{right['title']}</b><br/>{right['target']}<br/><font color='#0F2747'><b>{right['actual']}</b></font>", styles["body"]) if right else Paragraph("", styles["body"])
        objective_rows.append([left_text, right_text])
    objectives_table = Table(objective_rows, colWidths=[3.35 * inch, 3.35 * inch])
    objectives_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.white), ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#FBFCFE")]), ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#D8E1EA")), ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E7EDF3")), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story.append(section_box("Cohort Milestones", objectives_table, 6.9 * inch))
    story.append(Spacer(1, 0.08 * inch))

    lower = Table(
        [[
            section_box("Participant Voice", Paragraph(f"\"{narrative['participant_quote']}\"", styles["quote"]), 2.1 * inch),
            section_box("Grant-Ready Narrative", Paragraph(narrative["grant_narrative"], styles["body"]), 4.48 * inch),
        ]],
        colWidths=[2.3 * inch, 4.6 * inch],
    )
    story.append(lower)

    doc.build(story, onFirstPage=draw_page)
    return buffer.getvalue()
