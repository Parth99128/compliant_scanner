"""Gemini structured extraction: prompt, normalization, transport (mocked)."""

import httpx
import pytest

from app.services import llm as llm_mod
from app.services.llm import (
    LlmError,
    LlmNotConfigured,
    build_extract_prompt,
    extract_with_gemini,
    normalize_extract_payload,
)


def test_prompt_lists_all_fields():
    p = build_extract_prompt("MRP Rs. 120", 80.0)
    for key in llm_mod.EXTRACT_FIELDS:
        assert key in p
    assert "JSON" in p and "unit-sale" in p


def test_normalize_valid():
    from datetime import date

    out = normalize_extract_payload(
        {
            "mrp": 120,
            "mrp_includes_taxes": True,
            "net_quantity_value": 500,
            "net_quantity_unit": "G",
            "mfg_date": "2025-01-15",
            "expiry_date": "not-a-date",
            "manufacturer_name": " Acme Foods ",
            "junk_key": "dropped",
            "is_imported": "yes",
        }
    )
    assert out["mrp"] == 120.0
    assert out["mrp_includes_taxes"] is True
    assert out["net_quantity_value"] == 500.0
    assert out["net_quantity_unit"] == "g"
    assert out["mfg_date"] == date(2025, 1, 15)
    assert "expiry_date" not in out
    assert out["manufacturer_name"] == "Acme Foods"
    assert "junk_key" not in out
    assert "is_imported" not in out


def test_normalize_rejects():
    assert normalize_extract_payload(None) == {}
    assert normalize_extract_payload("[]") == {}
    assert normalize_extract_payload({"mrp": -5}) == {}
    assert normalize_extract_payload({"mrp": "free"}) == {}
    assert normalize_extract_payload({"net_quantity_unit": "furlongs"}) == {}


class _Resp:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _ok_payload():
    return {"candidates": [{"content": {"parts": [{"text": '```json\n{"mrp": 99.5}\n```'}]}}]}


def test_extract_happy_path(monkeypatch):
    monkeypatch.setattr(llm_mod, "get_settings", lambda: _Settings())
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp(200, _ok_payload()))
    patch, model = extract_with_gemini("MRP Rs. 99.50", 70.0)
    assert patch == {"mrp": 99.5} and model == "gemini-2.0-flash"


def test_extract_http_error(monkeypatch):
    monkeypatch.setattr(llm_mod, "get_settings", lambda: _Settings())
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp(429, text="quota"))
    with pytest.raises(LlmError):
        extract_with_gemini("x")


def test_extract_not_json(monkeypatch):
    monkeypatch.setattr(llm_mod, "get_settings", lambda: _Settings())
    bad = {"candidates": [{"content": {"parts": [{"text": "no braces here"}]}}]}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp(200, bad))
    with pytest.raises(LlmError):
        extract_with_gemini("x")


def test_digits_grounded():
    from app.api.v1.routes import _digits_grounded

    assert _digits_grounded(12499.0, "MRP Rs. 12,499.00") is True
    assert _digits_grounded(50.0, "F500; USPR100") is True
    assert _digits_grounded(96.0, "MRP Rs 95") is False  # hallucinated amount
    assert _digits_grounded(96.0, "no digits here") is False
    assert _digits_grounded(None, "MRP 95") is False


def test_heading_fill_guards():
    from app.api.v1.routes import _CARE_FILL_RE, _CONTACT_EVIDENCE_RE, _looks_heading

    assert _looks_heading("For Consumer Care Contact Manager-") is True
    assert _looks_heading("Baby Care Soap") is False
    assert _looks_heading("Patanjali Foods Limited") is False
    assert _looks_heading("") is False
    assert _CARE_FILL_RE.search("Customer Care Manager") is not None
    assert _CARE_FILL_RE.search("TTK Prestige Ltd") is None
    assert _CONTACT_EVIDENCE_RE.search("Call 1800 123 456") is not None
    assert _CONTACT_EVIDENCE_RE.search("wecare@example.in") is not None
    assert _CONTACT_EVIDENCE_RE.search("For Consumer Care Contact Manager-") is None


def test_extract_not_configured(monkeypatch):
    monkeypatch.setattr(llm_mod, "get_settings", lambda: _Off())
    with pytest.raises(LlmNotConfigured):
        extract_with_gemini("x")


class _Settings:
    llm_provider = "gemini"
    gemini_api_key = "k"
    llm_model = "gemini-2.0-flash"


class _Off:
    llm_provider = "off"
    gemini_api_key = ""
    llm_model = ""
