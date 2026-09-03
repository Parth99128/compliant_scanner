"""CPU inference wrapper: OpenCV enhance -> Tesseract CPU -> regex (+spaCy) extract.

Usage:
    from ml.local_extract import extract_label
    out = extract_label(open("label.png", "rb").read(), ppm=10.0)
"""

from __future__ import annotations

import dataclasses
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.extraction import extract_fields  # noqa: E402
from app.services.ocr import run_ocr, word_boxes  # noqa: E402
from app.services.rule_engine import evaluate_compliance  # noqa: E402
from app.services.vision import (  # noqa: E402
    detect_ppm_from_reference_card,
    font_height_mm,
    preprocess_for_ocr,
)


def _median(xs: list[float]) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    mid = len(xs) // 2
    return xs[mid] if len(xs) % 2 else (xs[mid - 1] + xs[mid]) / 2


def extract_label(image_bytes: bytes, ppm: float | None = None) -> dict:
    t0 = time.perf_counter()
    clean = preprocess_for_ocr(image_bytes)
    if ppm is None:
        ppm = detect_ppm_from_reference_card(image_bytes)
    ocr = run_ocr(clean)
    boxes = word_boxes(clean)
    decl = extract_fields(ocr.text)
    med_px = _median([float(b.h) for b in boxes]) if boxes else None
    font_mm = font_height_mm(med_px, ppm) if med_px and ppm else None
    med_ratio = _median([float(b.w) / float(b.h) for b in boxes if b.h > 0]) if boxes else None
    if font_mm is not None or med_ratio is not None:
        decl = dataclasses.replace(
            decl,
            min_numeral_height_mm=font_mm,
            min_letter_height_mm=font_mm,
            min_width_to_height_ratio=round(med_ratio, 3) if med_ratio else None,
        )
    report = evaluate_compliance(decl, ocr_confidence=ocr.confidence or None)
    decl_d = dataclasses.asdict(decl)
    for k in ("mfg_date", "expiry_date"):
        decl_d[k] = decl_d[k].isoformat() if decl_d[k] else None
    return {
        "engine": ocr.engine,
        "confidence": ocr.confidence,
        "text": ocr.text,
        "boxes": [dataclasses.asdict(b) for b in boxes],
        "ppm": ppm,
        "median_font_height_mm": font_mm,
        "declaration": decl_d,
        "verdict": report.verdict,
        "compliant": report.compliant,
        "results": [dataclasses.asdict(r) for r in report.results],
        "warnings": report.warnings,
        "elapsed_s": round(time.perf_counter() - t0, 3),
    }
