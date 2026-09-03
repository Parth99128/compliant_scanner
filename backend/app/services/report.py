"""Printable PDF compliance report (ReportLab, CPU-only)."""

from __future__ import annotations

import io

from app.models.tables import ScanRecord


def build_report_pdf(scan: ScanRecord, results: list[dict], warnings: list[str]) -> bytes:
    from reportlab.lib.pagesizes import A4  # type: ignore
    from reportlab.lib.styles import getSampleStyleSheet  # type: ignore
    from reportlab.lib.units import mm  # type: ignore
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # type: ignore

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm)
    styles = getSampleStyleSheet()
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
    rows = [["Rule", "Status", "Detail"]]
    for r in results:
        status = str(r.get("status", "PASS"))
        detail = r.get("message", "")
        if r.get("remedy"):
            detail += f" Remedy: {r['remedy']}"
        rows.append([r["rule_id"], status, detail])
    table = Table(rows, colWidths=[45 * mm, 20 * mm, 110 * mm])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, (0, 0, 0))]))
    story += [table, Spacer(1, 4 * mm)]
    for w in warnings:
        story.append(Paragraph(f"Warning: {w}", styles["Normal"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("OCR excerpt:", styles["Heading3"]))
    story.append(Paragraph((scan.ocr_text or "")[:1500].replace("\n", "<br/>"), styles["Normal"]))
    doc.build(story)
    return buf.getvalue()
