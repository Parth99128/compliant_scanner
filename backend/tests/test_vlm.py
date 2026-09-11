"""Generic local VLM reader: disabled-by-default, honest arbitration."""

from app.services import vlm as vlm_mod
from app.services.vlm import PROMPT, is_enabled


def test_prompt_is_transcription_only():
    assert "verbatim" in PROMPT and "transcription" in PROMPT.lower()


def test_disabled_by_default(monkeypatch):
    monkeypatch.setattr(vlm_mod, "get_settings", lambda: _Off())
    assert is_enabled() is False
    assert vlm_mod.run_vlm_ocr(b"junk") is None


def test_run_none_without_weights(monkeypatch):
    # Enabled but torch/transformers absent or model missing -> None, never raises.
    monkeypatch.setattr(vlm_mod, "get_settings", lambda: _On())
    assert vlm_mod.run_vlm_ocr(b"not-an-image") is None


class _Off:
    vlm_enabled = "false"
    vlm_model = ""


class _On:
    vlm_enabled = "true"
    vlm_model = "no-such-model-xyz"
