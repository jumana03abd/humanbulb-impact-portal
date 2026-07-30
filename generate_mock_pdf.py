from pathlib import Path


PAGE_WIDTH = 612
PAGE_HEIGHT = 792
LEFT = 58
RIGHT = 554
TOP = 756
BOTTOM = 54


def escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def wrap_text(text: str, width: int) -> list[str]:
    words = text.split()
    lines = []
    current = []
    current_len = 0
    for word in words:
        add_len = len(word) + (1 if current else 0)
        if current and current_len + add_len > width:
            lines.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += add_len
    if current:
        lines.append(" ".join(current))
    return lines


def text_block(lines: list[str], x: int, y: int, font: str, size: int, leading: int | None = None) -> str:
    leading = leading or int(size * 1.35)
    out = [f"BT /{font} {size} Tf {x} {y} Td {leading} TL"]
    for index, line in enumerate(lines):
        if index == 0:
            out.append(f"({escape_pdf_text(line)}) Tj")
        else:
            out.append(f"T* ({escape_pdf_text(line)}) Tj")
    out.append("ET")
    return "\n".join(out)


class PdfLayout:
    def __init__(self) -> None:
        self.pages: list[list[str]] = []
        self.page_number = 0
        self.y = TOP
        self.new_page()

    def new_page(self) -> None:
        self.page_number += 1
        self.pages.append([])
        self.y = TOP
        self._draw_page_shell()

    @property
    def content(self) -> list[str]:
        return self.pages[-1]

    def add(self, command: str) -> None:
        self.content.append(command)

    def ensure_space(self, needed: int) -> None:
        if self.y - needed < BOTTOM + 28:
            self.new_page()

    @property
    def usable_bottom(self) -> int:
        return BOTTOM + 28

    @property
    def available_height(self) -> int:
        return self.y - self.usable_bottom

    def max_lines_for_current_page(self, leading: int, reserve: int = 0) -> int:
        return max(0, (self.available_height - reserve) // leading)

    def _draw_page_shell(self) -> None:
        self.add("1 1 1 rg 0 0 612 792 re f")
        self.add("0.66 0.78 0.71 RG 1 w 36 36 540 720 re S")
        self.add("0.06 0.15 0.28 rg 36 690 540 66 re f")
        self.add("1 0.77 0.19 rg 36 678 540 6 re f")
        self.add("1 1 1 rg")
        self.add(text_block(["HUMANBULB"], 58, 727, "F2", 24))
        self.add(text_block(["GREEN CAREERS LAUNCHPAD | SPRING 2026 IMPACT BRIEF"], 58, 705, "F1", 10))
        self.add("0.66 0.78 0.71 RG 0.8 w 58 74 482 1 re f")
        self.add("0.33 0.41 0.48 rg")
        footer = f"HUMANBULB Impact Portal  |  Mock Exported PDF  |  Page {self.page_number}"
        self.add(text_block([footer], 58, 56, "F1", 9))
        self.y = 650

    def section_title(self, title: str, gap_before: int = 0, keep_with: int = 0) -> None:
        self.ensure_space(34 + gap_before + keep_with)
        self.y -= gap_before
        self.add("0.06 0.15 0.28 rg")
        self.add(text_block([title], LEFT, self.y, "F2", 16))
        self.y -= 24

    def paragraph(self, text: str, width: int = 88, size: int = 10, leading: int = 14, gap_after: int = 18) -> None:
        lines = wrap_text(text, width)
        self.add("0.33 0.41 0.48 rg")
        while lines:
            reserve = gap_after if len(lines) <= self.max_lines_for_current_page(leading) else 0
            capacity = self.max_lines_for_current_page(leading, reserve)
            if capacity <= 0:
                self.new_page()
                continue
            chunk = lines[:capacity]
            lines = lines[capacity:]
            self.add(text_block(chunk, LEFT, self.y, "F1", size, leading))
            self.y -= len(chunk) * leading
            if lines:
                self.new_page()
            else:
                self.y -= gap_after

    def bullet_list(self, items: list[str], width: int = 82, size: int = 10, leading: int = 14, gap_after: int = 18) -> None:
        self.add("0.33 0.41 0.48 rg")
        wrapped_items = [wrap_text(item, width) for item in items]
        for item_index, lines in enumerate(wrapped_items):
            pending = list(lines)
            first_line = True
            while pending:
                reserve = gap_after if item_index == len(wrapped_items) - 1 and len(pending) == 1 else 0
                capacity = self.max_lines_for_current_page(leading, reserve)
                if capacity <= 0:
                    self.new_page()
                    continue
                chunk_size = min(len(pending), max(1, capacity))
                chunk = pending[:chunk_size]
                pending = pending[chunk_size:]
                prefix = "- " if first_line else ""
                indent = LEFT if first_line else LEFT + 14
                self.add(text_block([prefix + chunk[0]], indent, self.y, "F1", size, leading))
                self.y -= leading
                for line in chunk[1:]:
                    self.add(text_block([line], LEFT + 14, self.y, "F1", size, leading))
                    self.y -= leading
                first_line = False
                if pending:
                    self.new_page()
            self.y -= 4
        self.y -= gap_after - 4

    def metrics_row(self, metrics: list[tuple[str, str]]) -> None:
        box_w = 112
        gap = 12
        row_size = 4
        for start in range(0, len(metrics), row_size):
            row_metrics = metrics[start:start + row_size]
            label_lines = [wrap_text(label, 14) for _, label in row_metrics]
            max_label_lines = max(len(lines) for lines in label_lines)
            box_h = max(72, 42 + max_label_lines * 10 + 18)
            self.ensure_space(box_h + 24)
            y_bottom = self.y - box_h
            for index, ((value, _), lines) in enumerate(zip(row_metrics, label_lines)):
                x = LEFT + index * (box_w + gap)
                self.add("0.86 0.93 0.88 rg")
                self.add(f"{x} {y_bottom} {box_w} {box_h} re f")
                self.add("0.66 0.78 0.71 RG 0.8 w")
                self.add(f"{x} {y_bottom} {box_w} {box_h} re S")
                self.add("0.06 0.15 0.28 rg")
                self.add(text_block([value], x + 14, y_bottom + box_h - 28, "F2", 21))
                self.add("0.33 0.41 0.48 rg")
                self.add(text_block(lines, x + 14, y_bottom + 18, "F1", 8, 10))
            self.y = y_bottom - 24

    def quote_box(self, title: str, quote: str) -> None:
        lines = wrap_text(quote, 74)
        line_height = 14
        pending = list(lines)
        continued = False
        while pending:
            title_text = f"{title} (cont.)" if continued else title
            header_h = 52
            footer_pad = 18
            max_lines = max(1, (self.available_height - header_h - footer_pad) // line_height)
            if max_lines <= 0:
                self.new_page()
                continued = True
                continue
            chunk = pending[:max_lines]
            pending = pending[max_lines:]
            box_h = header_h + len(chunk) * line_height + footer_pad
            self.ensure_space(box_h + 24)
            y_bottom = self.y - box_h
            self.add("0.98 0.92 0.67 rg")
            self.add(f"{LEFT} {y_bottom} 482 {box_h} re f")
            self.add("0.96 0.77 0.19 RG 1 w")
            self.add(f"{LEFT} {y_bottom} 482 {box_h} re S")
            self.add("0.06 0.15 0.28 rg")
            self.add(text_block([title_text], LEFT + 16, y_bottom + box_h - 24, "F2", 16))
            self.add("0.2 0.3 0.35 rg")
            self.add(text_block(chunk, LEFT + 16, y_bottom + box_h - 50, "F1", 10, line_height))
            self.y = y_bottom - 24
            if pending:
                self.new_page()
                continued = True


def build_pages() -> list[str]:
    layout = PdfLayout()

    layout.add("0.06 0.15 0.28 rg")
    layout.add(text_block(["Program Overview"], LEFT, layout.y, "F2", 18))
    layout.y -= 22
    overview = (
        "HUMANBULB's Green Careers Launchpad is an 8-week workforce development internship that helps "
        "young people build career readiness, clean tech awareness, and professional confidence through "
        "hands-on projects, coaching, and community-based learning."
    )
    layout.paragraph(overview, width=90, size=11, leading=15, gap_after=20)

    layout.metrics_row([
        ("48", "interns served"),
        ("91%", "attendance"),
        ("86%", "completion"),
        ("+90%", "knowledge growth"),
    ])

    executive = (
        "Connected surveys, attendance data, deliverables tracking, and participant reflections show strong "
        "engagement and measurable growth in career readiness. Participants demonstrated the largest gains in "
        "clean tech knowledge, interview confidence, and clarity about future pathways."
    )
    executive_lines = wrap_text(executive, 88)
    layout.section_title("Executive Summary", keep_with=len(executive_lines) * 14 + 18)
    layout.paragraph(executive, width=88)

    accomplishments = [
        "19 projects completed across team and individual assignments.",
        "57 deliverables submitted, including resumes, profiles, and presentations.",
        "79% resume and LinkedIn completion by the end of the program.",
        "High participation sustained through the full 8-week experience.",
    ]
    accomplishment_lines = sum(len(wrap_text(item, 82)) + 1 for item in accomplishments) * 14 + 18
    layout.section_title("Key Accomplishments", keep_with=accomplishment_lines)
    layout.bullet_list([
        "19 projects completed across team and individual assignments.",
        "57 deliverables submitted, including resumes, profiles, and presentations.",
        "79% resume and LinkedIn completion by the end of the program.",
        "High participation sustained through the full 8-week experience.",
    ])

    quote = (
        '"This program helped me picture myself in a green career for the first time, and it gave me proof '
        'that I can contribute in professional spaces."'
    )
    layout.quote_box("Participant Voice", quote)

    why = (
        "Green Careers Launchpad expands access to innovation, entrepreneurship, and workforce development "
        "for young people who benefit from practical exposure, mentorship, and structured skill-building."
    )
    why_lines = wrap_text(why, 88)
    layout.section_title("Why It Matters", keep_with=len(why_lines) * 14 + 18)
    layout.paragraph(why, width=88)

    narrative = (
        "Based on uploaded surveys, tracker data, and participant reflections, Green Careers Launchpad delivered "
        "a high-engagement internship experience with strong signs of career readiness growth. Participants showed "
        "meaningful gains in clean tech knowledge, interview confidence, and resume completion while contributing "
        "to project work and community-facing activities."
    )
    narrative_lines = wrap_text(narrative, 92)
    layout.section_title("Grant-Ready Narrative", keep_with=len(narrative_lines) * 14 + 12)
    layout.paragraph(narrative, width=92, gap_after=12)

    return ["\n".join(page) for page in layout.pages]


def build_pdf_bytes(page_streams: list[str]) -> bytes:
    page_count = len(page_streams)
    font_helvetica_obj = 3
    font_bold_obj = 4
    first_page_obj = 5
    first_stream_obj = first_page_obj + page_count

    objects: list[bytes] = []
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

    kids = " ".join(f"{first_page_obj + i} 0 R" for i in range(page_count))
    objects.append(f"2 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {page_count} >>\nendobj\n".encode("latin-1"))
    objects.append(b"3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
    objects.append(b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n")

    for index in range(page_count):
        page_obj = first_page_obj + index
        stream_obj = first_stream_obj + index
        page = (
            f"{page_obj} 0 obj\n"
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 {font_helvetica_obj} 0 R /F2 {font_bold_obj} 0 R >> >> "
            f"/Contents {stream_obj} 0 R >>\nendobj\n"
        )
        objects.append(page.encode("latin-1"))

    for index, page_stream in enumerate(page_streams):
        stream_obj = first_stream_obj + index
        stream_bytes = page_stream.encode("latin-1", errors="replace")
        header = f"{stream_obj} 0 obj\n<< /Length {len(stream_bytes)} >>\nstream\n".encode("latin-1")
        objects.append(header + stream_bytes + b"\nendstream\nendobj\n")

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("latin-1")
    )
    return bytes(pdf)


def main() -> None:
    out_path = Path(__file__).with_name("mock-exported-impact-brief.pdf")
    out_path.write_bytes(build_pdf_bytes(build_pages()))
    print(out_path)


if __name__ == "__main__":
    main()
