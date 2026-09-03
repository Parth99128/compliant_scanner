"""Regression pin (DELEGATION-ADDENDUM §A): `ocr_confidence` lives on the raw
Tesseract 0–100 scale — NOT a 0–1 extractor-style score.

The legibility threshold (<60) must be evaluated on the 0–100 scale.
Conflating the scales makes it fire almost always (0–1 input vs 60) or almost
never (0–100 input vs 0.6), silently. These tests pin the scale so a future
refactor can't silently swap it.
"""

from app.services.ocr import run_ocr
from app.services.rule_engine import ProductDeclaration, evaluate_compliance


def _label_image() -> bytes:
    import io

    from PIL import Image, ImageDraw

    img = Image.new("RGB", (800, 200), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 20), "Wheat Biscuits", fill="black")
    d.text((20, 80), "MRP Rs. 50 Inclusive of all taxes", fill="black")
    d.text((20, 140), "Net Qty: 100 g", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_tesseract_confidence_uses_0_to_100_scale():
    ocr = run_ocr(_label_image())
    assert ocr.engine == "tesseract"
    assert 0.0 <= ocr.confidence <= 100.0
    # A 0–1 ratio-scale value could never exceed 1.0 on real OCR output —
    # this proves we carry the raw Tesseract scale, not a normalized ratio.
    assert ocr.confidence > 1.0


def test_legibility_threshold_boundary_on_100_scale():
    d = ProductDeclaration()
    assert evaluate_compliance(d, ocr_confidence=59.9).warnings  # just under -> warn
    assert not evaluate_compliance(d, ocr_confidence=60.0).warnings  # at threshold -> silent


def test_conflation_guard_low_ratio_score_must_warn():
    # 0.95 looks "high" on a 0–1 scale but is ~1% on the real scale — it MUST
    # warn. If someone refactors the threshold to 0.6 (ratio scale), this fails.
    assert evaluate_compliance(ProductDeclaration(), ocr_confidence=0.95).warnings
