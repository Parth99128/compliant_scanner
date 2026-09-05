"""Printable PDF compliance report (ReportLab, CPU-only).

Contents: header (ids, engine, verdict, review, timestamps, GPS), rule table
with observed/expected captured values, annotated photo evidence (capture +
OCR boxes), warnings, and an enforcement summary. No raw OCR text dump.
"""

from __future__ import annotations

import io


def _annotated_capture(
    image_blob: bytes,
    boxes: list[dict],
    coord_w: int | None,
    coord_h: int | None,
    max_width_px: int = 900,
) -> bytes | None:
    """Stored capture with OCR word boxes drawn in (green >=60%, else red).

    Boxes live in preprocessed-image pixels; the stored capture keeps the
    same aspect ratio, so one uniform scale maps them. None on any failure.
    """
    try:
        from PIL import Image, ImageDraw

        img = Image.open(io.BytesIO(bytes(image_blob))).convert("RGB")
        if img.width > max_width_px:
            img = img.resize((max_width_px, int(max_width_px * img.height / img.width)))
        if coord_w and coord_h and boxes:
            sx, sy = img.width / coord_w, img.height / coord_h
            lw = max(2, img.width // 300)
            draw = ImageDraw.Draw(img)
            for b in boxes[:200]:
                if not isinstance(b, dict):
                    continue
                try:
                    x, y, w, h = (float(b.get(k, 0)) for k in ("x", "y", "w", "h"))
                    conf = float(b.get("confidence", 0.0))
                except (TypeError, ValueError):
                    continue
                color = (34, 139, 34) if conf >= 60 else (200, 30, 30)
                draw.rectangle([x * sx, y * sy, (x + w) * sx, (y + h) * sy], outline=color, width=lw)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return buf.getvalue()
    except Exception:
        return None


def _enforcement_summary(verdict: str, failed_ids: list[str]) -> list[str]:
    """Suggested next steps. Advisory only — the officer decides, per the
    applicable provisions of the Legal Metrology Act, 2009 and 2011 Rules."""
    if verdict == "COMPLIANT":
        return [
            "No violation found. No enforcement action required.",
            "Retain this report for record and routine follow-up.",
        ]
    if verdict == "INCOMPLETE":
        return [
            (
                "Evidence incomplete: rules marked NOT_ASSESSABLE could not run "
                "(usually the millimetre scale was missing)."
            ),
            (
                "Re-capture with a reference object (or supply PPM) and re-evaluate. "
                "Do NOT treat this scan as compliant."
            ),
        ]
    lines = [
        f"Non-compliance recorded on {len(failed_ids)} rule(s): {', '.join(failed_ids)}.",
        (
            "Record findings with photo evidence; issue a show-cause notice to the "
            "manufacturer/packer/importer under the applicable provisions, and "
            "re-inspect within the statutory compliance period."
        ),
    ]
    return lines


def build_report_pdf(
    scan,  # ScanRecord (duck-typed to avoid a hard model import)
    results: list[dict],
    warnings: list[str],
    boxes: list[dict] | None = None,
    coord_w: int | None = None,
    coord_h: int | None = None,
) -> bytes:
    from xml.sax.saxutils import escape

    from reportlab.lib.pagesizes import A4  # type: ignore
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore
    from reportlab.lib.units import mm  # type: ignore
    from reportlab.platypus import Image as RLImage  # type: ignore
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # type: ignore

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm)
    styles = getSampleStyleSheet()
    h3 = ParagraphStyle("h3", parent=styles["Heading3"], spaceBefore=6, spaceAfter=4)
    cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=8.5, leading=11)
    cell_small = ParagraphStyle("cellSmall", parent=cell, fontSize=8, leading=10)
    cell_head = ParagraphStyle("cellHead", parent=cell, fontName="Helvetica-Bold")

    def _ts(value) -> str:
        try:
            return value.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            return str(value or "—")

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
        Paragraph(
            f"Scanned at: {_ts(getattr(scan, 'created_at', None))}"
            + (
                f" &nbsp;&nbsp; Reviewed: {_ts(scan.reviewed_at)} by {scan.reviewed_by}"
                if getattr(scan, "reviewed_at", None)
                else " &nbsp;&nbsp; Reviewed: pending"
            ),
            styles["Normal"],
        ),
    ]
    lat, lon = getattr(scan, "scan_lat", None), getattr(scan, "scan_lon", None)
    if lat is not None and lon is not None:
        story.append(
            Paragraph(f"Inspection location (device GPS at upload): {lat:.5f}, {lon:.5f}", styles["Normal"])
        )
    else:
        story.append(
            Paragraph(
                "Inspection location: not provided (GPS unavailable or desktop upload)", styles["Normal"]
            )
        )
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Findings — with captured values", h3))
    rows = [[Paragraph("Rule", cell_head), Paragraph("Status", cell_head), Paragraph("Detail", cell_head)]]
    failed_ids: list[str] = []
    for r in results:
        status = str(r.get("status", "PASS"))
        if status in ("FAIL", "NOT_FOUND"):
            failed_ids.append(str(r.get("rule_id", "?")))
        # The exact captured value travels with every finding: a legal audit
        # must show what the OCR saw, not just "present".
        detail = r.get("message", "")
        if r.get("observed"):
            detail += f" Observed: {r['observed']}."
        if r.get("expected"):
            detail += f" Expected: {r['expected']}."
        if r.get("remedy"):
            detail += f" Remedy: {r['remedy']}"
        rows.append(
            [
                Paragraph(escape(str(r.get("rule_id", ""))), cell_small),
                Paragraph(escape(status), cell),
                Paragraph(escape(detail), cell),
            ]
        )
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

    story.append(Paragraph("Visual evidence", h3))
    annotated = (
        _annotated_capture(scan.image_blob, boxes or [], coord_w, coord_h) if scan.image_blob else None
    )
    if annotated:
        from PIL import Image

        with Image.open(io.BytesIO(annotated)) as probe:
            iw, ih = probe.size
        width = 170 * mm
        story.append(RLImage(io.BytesIO(annotated), width=width, height=width * ih / iw))
        story.append(
            Paragraph(
                "Stored capture with OCR word boxes (green: confidence ≥60%, "
                "red: verify against the physical package).",
                styles["Normal"],
            )
        )
    else:
        story.append(Paragraph("No stored capture for this scan.", styles["Normal"]))

    story.append(Paragraph("Enforcement summary (advisory)", h3))
    for line in _enforcement_summary(str(scan.verdict), failed_ids):
        story.append(Paragraph(escape(line), styles["Normal"]))
    story.append(
        Paragraph(
            "Suggested next steps only — the reviewing officer decides under the "
            "applicable provisions of the Legal Metrology Act, 2009 and the "
            "Packaged Commodities Rules, 2011.",
            styles["Normal"],
        )
    )
    doc.build(story)
    return buf.getvalue()
