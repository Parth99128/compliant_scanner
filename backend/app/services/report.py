"""Printable PDF compliance report (ReportLab, CPU-only).

Sample-locked layout (docs: DrishtiLM_Sample_Report.pdf):
running header (brand + ids + page), CASE DETAILS box, verdict banner with
counts, 5-column RULE-WISE FINDINGS (short refs like 6.1(e) / 2(m)), advisory
ENFORCEMENT SUMMARY with per-failure Why + numbered next steps, annotated
VISUAL EVIDENCE, OFFICER REVIEW & SIGN-OFF box, integrity ID. No raw OCR dump.
"""

from __future__ import annotations

import io
import re
from datetime import UTC, datetime

from reportlab.lib.units import mm  # type: ignore[import-untyped]

# Short refs + requirement text for the findings table. Rule 7 numeral/letter
# rows are dynamic (tier basis comes from the expected string).
_RULE_LABELS = {
    "LMPC-6.1-manufacturer": ("6.1(a)", "Manufacturer name & address"),
    "LMPC-6.1-generic": ("6.1(b)", "Generic / common name"),
    "LMPC-6.1-netqty": ("6.1(c)", "Net quantity"),
    "LMPC-6.1-mrp": ("6.1(e) / 2(m)", "MRP inclusive of all taxes"),
    "LMPC-6.1-dates": ("6.1(d)", "Date of manufacture / packing"),
    "LMPC-6.1-care": ("6.1", "Consumer care details"),
    "LMPC-6.1-origin": ("6.1", "Country of origin"),
    "LMPC-7.3-width": ("7.3", "Letter width / height ratio"),
}

_ENGINE_LABELS = (("tesseract", "Tesseract OCR"), ("florence", "Florence-2 VLM"))


def _pdf(text: object) -> str:
    """Sanitize for WinAnsi (Helvetica): ₹/≥/≤ have no glyph and print as boxes."""
    out = str(text or "").strip()
    return out.replace("₹", "Rs. ").replace("≥", ">=").replace("≤", "<=").replace("×", "x")


def _short_rule(rule_id: str, expected: str | None) -> tuple[str, str]:
    if rule_id in _RULE_LABELS:
        return _RULE_LABELS[rule_id]
    if rule_id == "LMPC-7.2-numeral":
        return "7.2", _rule7_requirement("Numeral height", expected)
    if rule_id == "LMPC-7.3-letter":
        return "7.3", _rule7_requirement("Letter height", expected)
    if rule_id.startswith("LMPC-gtin"):
        return rule_id, "Barcode identity cross-check"
    return rule_id, rule_id


def _rule7_requirement(base: str, expected: str | None) -> str:
    exp = expected or ""
    table = ""
    if "Table-II" in exp:
        table = "Table-II"
    elif "Table-I" in exp:
        table = "Table-I"
    qty = ""
    m = re.search(r"net ([\d.]+)g/ml", exp)
    if m:
        qty = f"{m.group(1)}g"
    else:
        m = re.search(r"panel ([\d.]+)cm", exp)
        if m:
            qty = f"{m.group(1)}cm² panel"
    tag = ""
    low = exp.lower()
    if "embossed" in low:
        tag = "embossed"
    elif "ordinary print" in low:
        tag = "ordinary print"
    bits = ", ".join(b for b in (table, qty, tag) if b)
    return f"{base} ({bits})" if bits else base


def _display_observed(value: object) -> str:
    s = _pdf(value)
    if not s or s.lower() == "absent":
        return "Not detected on scanned panel"
    if s.lower() == "unmeasured":
        return "Not measured"
    return s


def _engine_label(engine: object, confidence: object) -> str:
    name = _pdf(engine) or "OCR"
    for key, label in _ENGINE_LABELS:
        if key in name.lower():
            name = label
            break
    try:
        conf = float(str(confidence or 0))
    except (TypeError, ValueError):
        conf = 0.0
    return f"{name} — {conf:g}%"


def _status_color(status: str):
    from reportlab.lib import colors as _colors  # type: ignore[import-untyped]

    if status == "PASS":
        return _colors.HexColor("#0E6B2E")
    if status == "NOT_ASSESSABLE":
        return _colors.HexColor("#8A6D00")
    return _colors.HexColor("#C0392B")


def _header(canvas, doc) -> None:
    canvas.saveState()
    try:
        from reportlab.lib.pagesizes import A4 as _A4  # type: ignore[import-untyped]

        W, H = _A4
        canvas.setFont("Helvetica-Bold", 13)
        canvas.drawString(18 * mm, H - 14 * mm, "DRISHTILM")
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(W - 18 * mm, H - 14 * mm, f"Page {doc.page}")
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawCentredString(
            W / 2, H - 22 * mm, "Legal Metrology (Packaged Commodities) Compliance Report"
        )
        canvas.setFont("Helvetica", 9)
        canvas.drawCentredString(
            W / 2, H - 30 * mm, f"SCAN ID: {doc.scan_id}    REQUEST ID: {doc.request_id}"
        )
        canvas.setFont("Helvetica-Oblique", 7.5)
        canvas.drawCentredString(
            W / 2,
            H - 34 * mm,
            "Suggested findings only — the reviewing officer decides under the "
            "Legal Metrology Act, 2009 and Rules, 2011.",
        )
        canvas.setStrokeColor(_gray())
        canvas.setLineWidth(0.5)
        canvas.line(18 * mm, H - 36 * mm, W - 18 * mm, H - 36 * mm)
    finally:
        canvas.restoreState()


def _gray():
    from reportlab.lib import colors as _colors  # type: ignore[import-untyped]

    return _colors.HexColor("#6B7280")


def _annotated_capture(
    image_blob: bytes | bytearray,
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


def _nonpass_block(r: dict) -> list[str]:
    """Why + numbered next steps for one failing/unmeasurable rule (plain text)."""
    lines = []
    if r.get("why"):
        lines.append(_pdf(r["why"]))
    steps = r.get("next_steps") or []
    if steps:
        numbered = "; ".join(f"({n}) {s}" for n, s in enumerate(steps, start=1))
        lines.append(f"Recommended next steps: {numbered}")
    elif r.get("remedy"):
        lines.append(f"Recommended next steps: {_pdf(r['remedy'])}")
    return lines


def _enforcement_lines(verdict: str, results: list[dict]) -> list[str]:
    """Advisory enforcement summary with per-failure guidance."""
    bad = [r for r in results if str(r.get("status")) in ("FAIL", "NOT_FOUND")]
    unmeasured = [r for r in results if str(r.get("status")) == "NOT_ASSESSABLE"]
    lines: list[str] = []
    if verdict == "COMPLIANT":
        return [
            "No violation found. No enforcement action required.",
            "Retain this report for record and routine follow-up.",
        ]
    if verdict == "INCOMPLETE":
        lines.append(
            "Evidence incomplete: some declarations could not be verified "
            "(weak read or millimetre scale missing) — this scan is NOT a clean chit."
        )
        lines.append(
            "Re-capture (close-ups, reference object in frame) and re-evaluate. "
            "Do NOT treat this scan as compliant."
        )
        for r in bad + unmeasured:
            short, _req = _short_rule(str(r.get("rule_id", "?")), r.get("expected"))
            lines.append(f"{short}:")
            lines += _nonpass_block(r)
        return lines
    ids = ", ".join(_short_rule(str(r.get("rule_id", "?")), r.get("expected"))[0] for r in bad)
    plural = "" if len(bad) == 1 else "s"
    lines.append(f"Non-compliance recorded on {len(bad)} rule{plural}: {ids}.")
    for r in bad:
        short, _req = _short_rule(str(r.get("rule_id", "?")), r.get("expected"))
        lines.append(f"{short}:")
        lines += _nonpass_block(r)
    lines.append(
        "Record findings with photo evidence; issue a show-cause notice to the "
        "manufacturer/packer/importer under the applicable provisions, and "
        "re-inspect within the statutory compliance period."
    )
    return lines


def build_report_pdf(
    scan,  # ScanRecord (duck-typed to avoid a hard model import)
    results: list[dict],
    warnings: list[str],
    frames: list[dict] | None = None,
) -> bytes:
    """Sample-format compliance report: header, case box, verdict banner,
    rule table, advisory summary with guidance, evidence, sign-off.
    """
    from xml.sax.saxutils import escape

    from reportlab.lib.pagesizes import A4  # type: ignore
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore
    from reportlab.lib.units import mm  # type: ignore
    from reportlab.platypus import Image as RLImage  # type: ignore
    from reportlab.platypus import (  # type: ignore
        KeepTogether,  # type: ignore
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=40 * mm, bottomMargin=16 * mm
    )
    doc.scan_id = str(getattr(scan, "id", "—"))
    doc.request_id = str(getattr(scan, "request_id", "—"))
    styles = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=styles["Heading3"], spaceBefore=8, spaceAfter=4)
    cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=8.5, leading=11)
    cell_small = ParagraphStyle("cellSmall", parent=cell, fontSize=8, leading=10)
    cell_bold = ParagraphStyle("cellBold", parent=cell, fontName="Helvetica-Bold")
    label = ParagraphStyle("label", parent=cell, fontName="Helvetica-Bold")
    banner = ParagraphStyle(
        "banner", parent=styles["Normal"], fontSize=11, leading=14, fontName="Helvetica-Bold"
    )

    def _ts(value) -> str:
        try:
            return value.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            return str(value or "—")

    def _txt(value) -> str:
        text = _pdf(value)
        return text if text else "—"

    verdict = str(getattr(scan, "verdict", "INCOMPLETE"))
    flagged = sum(1 for r in results if str(r.get("status")) in ("FAIL", "NOT_FOUND"))
    passed = sum(1 for r in results if str(r.get("status")) == "PASS")
    total = len(results)

    story = [Paragraph("CASE DETAILS", h)]
    net_obs = "—"
    for r in results:
        if str(r.get("rule_id")) == "LMPC-6.1-netqty":
            obs = _display_observed(r.get("observed"))
            net_obs = obs if not obs.startswith("Not ") else "—"
    reviewed_by = getattr(scan, "reviewed_by", None)
    case_rows = [
        ("PRODUCT", _txt(getattr(scan, "product_name", None))),
        ("BRAND / MANUFACTURER", _txt(getattr(scan, "brand_name", None))),
        ("CATEGORY", _txt(getattr(scan, "category", None))),
        ("DECLARED NET QUANTITY", net_obs),
        ("SCANNED AT", _ts(getattr(scan, "created_at", None))),
        (
            "REVIEWED AT",
            _ts(getattr(scan, "reviewed_at", None)) if getattr(scan, "reviewed_at", None) else "—",
        ),
        ("REVIEWED BY", _txt(reviewed_by)),
        (
            "OCR ENGINE / CONFIDENCE",
            _engine_label(getattr(scan, "ocr_engine", ""), getattr(scan, "ocr_confidence", 0)),
        ),
    ]
    case_table = Table(
        [[Paragraph(escape(k), label), Paragraph(escape(v), cell)] for k, v in case_rows],
        colWidths=[52 * mm, 120 * mm],
    )
    case_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, (0, 0, 0)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, -1), (0.93, 0.93, 0.93)),
            ]
        )
    )
    story += [case_table]
    lat, lon = getattr(scan, "scan_lat", None), getattr(scan, "scan_lon", None)
    if lat is not None and lon is not None:
        story.append(
            Paragraph(f"Inspection location (device GPS at upload): {lat:.5f}, {lon:.5f}", styles["Normal"])
        )
    else:
        story.append(
            Paragraph(
                "Inspection location: Not provided (GPS unavailable / desktop upload)", styles["Normal"]
            )
        )
    if getattr(scan, "corrected_by", None):
        story.append(
            Paragraph(
                f"Officer corrections by {scan.corrected_by} at {_ts(getattr(scan, 'corrected_at', None))} "
                "— Rule 6 values below are officer-verified, measurements unchanged.",
                styles["Normal"],
            )
        )
    story.append(Spacer(1, 3 * mm))

    review_note_raw = f"Final review by {reviewed_by}" if reviewed_by else "Pending review"
    plural = "" if flagged == 1 else "s"
    banner_text = (
        f"VERDICT: {verdict}&nbsp;&nbsp;{flagged} rule{plural} flagged · "
        f"{passed} of {total} checks passed · {escape(review_note_raw)}"
    )
    banner_bg = {"COMPLIANT": (0.90, 0.95, 0.90), "NON_COMPLIANT": (0.96, 0.90, 0.90)}.get(
        verdict, (0.97, 0.94, 0.85)
    )
    banner_table = Table([[Paragraph(banner_text, banner)]], colWidths=[172 * mm])
    banner_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, (0, 0, 0)),
                ("BACKGROUND", (0, 0), (-1, -1), banner_bg),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story += [banner_table, Spacer(1, 2 * mm)]

    story.append(Paragraph("RULE-WISE FINDINGS", h))
    rows = [
        [
            Paragraph("Rule", cell_bold),
            Paragraph("Requirement", cell_bold),
            Paragraph("Status", cell_bold),
            Paragraph("Observed", cell_bold),
            Paragraph("Expected", cell_bold),
        ]
    ]
    row_colors = []
    for r in results:
        short, req = _short_rule(str(r.get("rule_id", "")), r.get("expected"))
        status = str(r.get("status", "PASS"))
        rows.append(
            [
                Paragraph(escape(_pdf(short)), cell_small),
                Paragraph(escape(_pdf(req)), cell),
                Paragraph(f'<font color="{_status_color(status).hexval()}">{escape(status)}</font>', cell),
                Paragraph(escape(_display_observed(r.get("observed"))), cell),
                Paragraph(escape(_pdf(r.get("expected")) or "—"), cell),
            ]
        )
        row_colors.append(_status_color(status))
    table = Table(rows, colWidths=[24 * mm, 42 * mm, 28 * mm, 39 * mm, 39 * mm], repeatRows=1)
    style_cmds = [
        ("GRID", (0, 0), (-1, -1), 0.5, (0, 0, 0)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, 0), (0.93, 0.93, 0.93)),
    ]
    table.setStyle(TableStyle(style_cmds))
    story += [table, Spacer(1, 2 * mm)]
    for w in warnings:
        story.append(Paragraph(f"Warning: {escape(_pdf(w))}", styles["Normal"]))

    evidence_story: list = [Paragraph("VISUAL EVIDENCE", h)]
    evidence = (
        frames
        if frames is not None
        else (
            [
                {
                    "label": "Angle 1 (Best capture)",
                    "blob": scan.image_blob,
                    "boxes": [],
                    "cw": None,
                    "ch": None,
                }
            ]
            if scan.image_blob
            else []
        )
    )
    shown = 0
    if evidence:
        from PIL import Image

        for frame in evidence:
            blob = frame.get("blob")
            if not isinstance(blob, (bytes, bytearray)):
                continue
            annotated = _annotated_capture(blob, frame.get("boxes") or [], frame.get("cw"), frame.get("ch"))
            if not annotated:
                continue
            with Image.open(io.BytesIO(annotated)) as probe:
                iw, ih = probe.size
            # Fit inside the page both ways: tall phone portraits at full
            # width overrun the frame and crash the build (LayoutError).
            width = 150 * mm
            height = width * ih / iw if iw else 0
            if height > 195 * mm:
                height = 195 * mm
                width = height * iw / ih if ih else width
            evidence_story.append(
                KeepTogether(
                    [
                        Paragraph(escape(_pdf(frame.get("label", "Capture"))), styles["Normal"]),
                        RLImage(io.BytesIO(annotated), width=width, height=height),
                    ]
                )
            )
            shown += 1
        if shown:
            evidence_story.append(
                Paragraph(
                    "OCR word boxes overlaid — green: confidence >= 60%, "
                    "red: verify against the physical package. Stored with scan "
                    "record for audit trail.",
                    styles["Normal"],
                )
            )
    if not shown:
        evidence_story.append(Paragraph("No stored capture for this scan.", styles["Normal"]))

    story.append(Paragraph("ENFORCEMENT SUMMARY (ADVISORY)", h))
    for line in _enforcement_lines(verdict, results):
        story.append(Paragraph(escape(line), styles["Normal"]))
    story.append(
        Paragraph(
            "Suggested next steps only — the reviewing officer decides under the "
            "applicable provisions of the Legal Metrology Act, 2009 and the "
            "Packaged Commodities Rules, 2011.",
            styles["Normal"],
        )
    )
    story += evidence_story

    story.append(Paragraph("OFFICER REVIEW & SIGN-OFF", h))
    try:
        import json as _json

        overridden = bool(getattr(scan, "overrides_json", None) and _json.loads(scan.overrides_json or "[]"))
    except Exception:
        overridden = False
    if getattr(scan, "status", "") == "final":
        review_status = "FINAL — Overridden with note" if overridden else "FINAL — Confirmed"
    else:
        review_status = "PENDING REVIEW"
    sign_rows = [
        ("Reviewing Officer", _txt(reviewed_by), "Review Status", review_status),
        (
            "Review Timestamp",
            _ts(getattr(scan, "reviewed_at", None)) if getattr(scan, "reviewed_at", None) else "—",
            "Report Generated",
            datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        ),
    ]
    sign_table = Table(
        [
            [
                Paragraph(escape(a), label),
                Paragraph(escape(b), cell),
                Paragraph(escape(c), label),
                Paragraph(escape(d), cell),
            ]
            for a, b, c, d in sign_rows
        ],
        colWidths=[36 * mm, 50 * mm, 36 * mm, 50 * mm],
    )
    sign_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, (0, 0, 0)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, -1), (0.93, 0.93, 0.93)),
                ("BACKGROUND", (2, 0), (2, -1), (0.93, 0.93, 0.93)),
            ]
        )
    )
    story += [
        sign_table,
        Spacer(1, 2 * mm),
        Paragraph(
            "This report is system-generated by DrishtiLM following officer confirmation "
            "and is intended as field-inspection evidence. A digital signature and per-request "
            "audit ID accompany the original record.",
            styles["Normal"],
        ),
        Paragraph(f"Document integrity ID: SCAN-{doc.scan_id} / REQ-{doc.request_id}", styles["Normal"]),
    ]
    doc.build(story, onFirstPage=_header, onLaterPages=_header)
    return buf.getvalue()
