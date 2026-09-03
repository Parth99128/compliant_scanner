"""Offline multi-engine OCR tests — Florence-2 disabled, so no weights/network."""

from app.services import ocr
from app.services.florence import is_enabled, run_florence_ocr


def test_florence_disabled_by_default():
    assert is_enabled() is False
    assert run_florence_ocr(b"not-an-image") is None


def test_run_ocr_unchanged_without_florence():
    # Empty bytes: Tesseract yields nothing -> empty result, never raises.
    r = ocr.run_ocr(b"")
    assert isinstance(r, ocr.OcrResult)
    assert r.engine in ("none", "tesseract", "cloud-vision-stub")
