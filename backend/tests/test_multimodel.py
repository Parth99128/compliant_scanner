"""Offline multi-engine OCR tests — hermetic regardless of local .env flags."""

from types import SimpleNamespace

import app.services.florence as fl_mod
from app.services import ocr
from app.services.florence import run_florence_ocr


def _off(monkeypatch):
    monkeypatch.setattr(
        fl_mod,
        "get_settings",
        lambda: SimpleNamespace(florence_enabled="false", florence_model="x"),
    )


def test_florence_disabled_by_default(monkeypatch):
    _off(monkeypatch)
    assert fl_mod.is_enabled() is False
    assert run_florence_ocr(b"not-an-image") is None


def test_run_ocr_unchanged_without_florence():
    # Empty bytes: Tesseract yields nothing -> empty result, never raises.
    r = ocr.run_ocr(b"")
    assert isinstance(r, ocr.OcrResult)
    assert r.engine in ("none", "tesseract", "cloud-vision-stub")
