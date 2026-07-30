from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output" / "pdf"
PDF_PATH = OUTPUT_DIR / "humanbulb-grant-summary-mock.pdf"
LOGO_PATH = ROOT / "assets" / "humanbulb-logo.png"


GRANT_METRICS = [
    ("48", "Interns served"),
    ("86%", "Program completion"),
    ("+90%", "Clean tech knowledge growth"),
    ("84%", "Career confidence and clarity"),
]

GRANT_OBJECTIVES = [
    ("Enrollment Reach", "Target: 30 participants", "48 enrolled"),
    ("Program Completion", "Target: 90% completion", "86% completion"),
    ("Clean Tech Awareness", "Target: 80%", "90%"),
    ("Career Materials", "Target: 85%", "79%"),
    ("Workplace Readiness", "Target: 85%", "87%"),
    ("Career Confidence", "Target: 80%", "84%"),
]

EXEC_SUMMARY = (
    "HUMANBULB's Green Careers Launchpad served 48 interns through an 8-week "
    "work-based learning experience focused on clean technology, career readiness, "
    "and community impact. Connected surveys, trackers, and participant reflections "
    "show strong engagement, measurable growth, and steady progress across core "
    "professional milestones."
)

QUOTE = (
    '"This program helped me picture myself in a green career for the first time, '
    'and it gave me proof that I can contribute in professional spaces."'
)

NARRATIVE = (
    "Based on uploaded surveys, tracker data, and participant reflections, Green "
    "Careers Launchpad delivered a high-engagement internship experience with strong "
    "signs of career readiness growth. Participants showed meaningful gains in clean "
    "tech knowledge, interview confidence, and resume completion while contributing "
    "to project-based and community-facing work. The program's structured reflection, "
    "skill-building workshops, and employer-connected exposure appear to be a strong "
    "model for future cohorts and funder investment."
)


def build_styles():
    styles = getSampleStyleSheet()
    return {
        "eyebrow": ParagraphStyle(
            "Eyebrow",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=9,
            textColor=colors.HexColor("#6B7C8E"),
            spaceAfter=4,
            textTransform=None,
        ),
        "title": ParagraphStyle(
            "Title",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=20,
            textColor=colors.HexColor("#0F2747"),
            spaceAfter=3,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=10,
            textColor=colors.HexColor("#55697A"),
        ),
        "meta_label": ParagraphStyle(
            "MetaLabel",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=7,
            leading=8,
            textColor=colors.HexColor("#6B7C8E"),
        ),
        "meta_value": ParagraphStyle(
            "MetaValue",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#0F2747"),
        ),
        "section_label": ParagraphStyle(
            "SectionLabel",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=9,
            textColor=colors.HexColor("#6B7C8E"),
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.3,
            leading=10.6,
            textColor=colors.HexColor("#21374C"),
        ),
        "metric_value": ParagraphStyle(
            "MetricValue",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=14,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#0F2747"),
        ),
        "metric_label": ParagraphStyle(
            "MetricLabel",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=7.2,
            leading=8.6,
            textColor=colors.HexColor("#55697A"),
        ),
        "objective_title": ParagraphStyle(
            "ObjectiveTitle",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=9,
            textColor=colors.HexColor("#0F2747"),
        ),
        "objective_sub": ParagraphStyle(
            "ObjectiveSub",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=7,
            leading=8,
            textColor=colors.HexColor("#647789"),
        ),
        "objective_actual": ParagraphStyle(
            "ObjectiveActual",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=9,
            alignment=TA_RIGHT,
            textColor=colors.HexColor("#0F2747"),
        ),
        "quote": ParagraphStyle(
            "Quote",
            parent=styles["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#15345B"),
        ),
        "footer": ParagraphStyle(
            "Footer",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9,
            textColor=colors.HexColor("#6B7C8E"),
        ),
    }


def metric_card(value, label, styles):
    card = Table(
        [[Paragraph(value, styles["metric_value"]), Paragraph(label, styles["metric_label"])]],
        colWidths=[0.52 * inch, 1.06 * inch],
    )
    card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#D8E1EA")),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return card


def build_objective_table(styles):
    rows = []
    for index in range(0, len(GRANT_OBJECTIVES), 2):
        pair = []
        for title, target, actual in GRANT_OBJECTIVES[index:index + 2]:
            pair.append(
                Paragraph(
                    f"{title}<br/><font color='#647789'>{target}</font><br/><font color='#0F2747'><b>{actual}</b></font>",
                    styles["objective_title"],
                )
            )
        if len(pair) == 1:
            pair.append(Paragraph("", styles["objective_title"]))
        rows.append(pair)

    table = Table(rows, colWidths=[3.35 * inch, 3.35 * inch], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#FBFCFE")]),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#D8E1EA")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E7EDF3")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def section_box(title, content, styles, width):
    inner = [
        [Paragraph(title, styles["section_label"])],
        [content],
    ]
    table = Table(inner, colWidths=[width])
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


def draw_page(canvas, doc):
    canvas.saveState()
    width, height = letter
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


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    styles = build_styles()
    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=letter,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.58 * inch,
        bottomMargin=0.62 * inch,
    )

    story = []

    header_left = []
    if LOGO_PATH.exists():
        header_left.append(Image(str(LOGO_PATH), width=0.82 * inch, height=0.82 * inch))
    header_left.append(Spacer(1, 0.04 * inch))
    header_left.append(Paragraph("Green Careers Launchpad", styles["section_label"]))
    header_left.append(Paragraph("Spring 2026 Impact Summary", styles["title"]))
    header_left.append(
        Paragraph(
            "One-page impact brief for external reporting and grant submissions",
            styles["subtitle"],
        )
    )

    header_right = Table(
        [[Paragraph("Grant-ready draft", styles["meta_value"])]],
        colWidths=[1.65 * inch],
    )
    header_right.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4C430")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0F2747")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("ROUNDEDCORNERS", [10, 10, 10, 10]),
            ]
        )
    )

    header = Table(
        [[header_left, header_right]],
        colWidths=[5.6 * inch, 1.2 * inch],
        hAlign="LEFT",
    )
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(header)
    story.append(Spacer(1, 0.09 * inch))
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#D8E1EA")))
    story.append(Spacer(1, 0.09 * inch))

    meta_cells = []
    for label, value in [
        ("Prepared for", "Leadership and funders"),
        ("Data sources", "Surveys, trackers, testimonials"),
        ("Reporting period", "Spring 2026 cohort"),
    ]:
        meta_cells.append(
            Table(
                [[Paragraph(label, styles["meta_label"])], [Paragraph(value, styles["meta_value"])]],
                colWidths=[2.1 * inch],
            )
        )
    meta = Table([meta_cells], colWidths=[2.15 * inch, 2.15 * inch, 2.15 * inch])
    meta.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#D8E1EA")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E7EDF3")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(meta)
    story.append(Spacer(1, 0.1 * inch))

    story.append(section_box("Executive Summary", Paragraph(EXEC_SUMMARY, styles["body"]), styles, 6.9 * inch))
    story.append(Spacer(1, 0.08 * inch))

    metric_row = [metric_card(value, label, styles) for value, label in GRANT_METRICS]
    metrics = Table([metric_row], colWidths=[1.72 * inch] * 4)
    metrics.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(section_box("Headline Outcomes", metrics, styles, 6.9 * inch))
    story.append(Spacer(1, 0.08 * inch))

    story.append(section_box("Cohort Milestones", build_objective_table(styles), styles, 6.9 * inch))
    story.append(Spacer(1, 0.08 * inch))

    lower = Table(
        [[
            section_box("Participant Voice", Paragraph(QUOTE, styles["quote"]), styles, 2.1 * inch),
            section_box("Grant-Ready Narrative", Paragraph(NARRATIVE, styles["body"]), styles, 4.48 * inch),
        ]],
        colWidths=[2.3 * inch, 4.6 * inch],
    )
    lower.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(lower)

    doc.build(story, onFirstPage=draw_page)
    print(PDF_PATH)


if __name__ == "__main__":
    main()
