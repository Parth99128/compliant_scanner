"""Printable PDF compliance report (ReportLab, CPU-only)."""

from __future__ import annotations

import io

from app.models.tables import ScanRecord


def build_report_pdf(scan: ScanRecord, results: list[dict], warnings: list[str]) -> bytes:
    from xml.sax.saxutils import escape

    from reportlab.lib.pagesizes import A4  # type: ignore
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore
    from reportlab.lib.units import mm  # type: ignore
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # type: ignore

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm)
    styles = getSampleStyleSheet()
    # Table cells MUST be Paragraphs — raw strings never wrap and bleed across
    # columns (e.g. NOT_ASSESSABLE + long remedy text).
    cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=8.5, leading=11)
    cell_small = ParagraphStyle("cellSmall", parent=cell, fontSize=8, leading=10)
    cell_head = ParagraphStyle("cellHead", parent=cell, fontName="Helvetica-Bold")
    story = [
        Paragraph("LMPC Compliance Report", styles["Title"]),
        Spacer(1, 6 * mm),
        Paragraph(f"Scan ID: {scan.id} &nbsp;&nbsp; Request: {scan.request_id}", styles["Normal"]),
        Paragraph(
            f"Engine: {scan.ocr_engine} (confidence {scan.ocr_confidence}%) &nbsp;&nbsp; "
            f"Verdict: {scan.verdict} &nbsp;&nbsp; Review: {scan.status}"
            + (f" by {scan.reviewed_by}" if scan.reviewed_by else ""),
            styles["Normal"],
        ),
        Spacer(1, 4 * mm),
    ]
    rows = [
        [Paragraph("Rule", cell_head), Paragraph("Status", cell_head), Paragraph("Detail", cell_head)]
    ]
    for r in results:
        status = str(r.get("status", "PASS"))
        detail = r.get("message", "")
        if r.get("remedy"):
            detail += f" Remedy: {r['remedy']}"
        rows.append(
            [
                Paragraph(escape(str(r.get("rule_id", ""))), cell_small),
                Paragraph(escape(status), cell),
                Paragraph(escape(detail), cell),
            ]
        )
    # 38 + 30 + 106 = 174mm = A4 width minus 2x18mm margins. Longest tokens:
    # rule ids (~22ch @8pt fit 38mm), NOT_ASSESSABLE (78.4pt @8.5pt fits 30mm).
    table = Table(rows, colWidths=[38 * mm, 30 * mm, 106 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, (0, 0, 0)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, 0), (0.93, 0.93, 0.93)),
            ]
        )
    )
    story += [table, Spacer(1, 4 * mm)]
    for w in warnings:
        story.append(Paragraph(f"Warning: {escape(w)}", styles["Normal"]))
    doc.build(story)
    return buf.getvalue()
