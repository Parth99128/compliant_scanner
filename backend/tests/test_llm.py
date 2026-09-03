"""Offline tests for the optional Gemini adapter — no network, no key needed."""

from types import SimpleNamespace

import app.services.llm as llm_mod
from app.services.llm import LlmNotConfigured, build_explain_prompt


def test_prompt_contains_verdict_and_rules():
    results = [
        {
            "rule_id": "LMPC-6.1-mrp",
            "status": "FAIL",
            "message": "MRP must state 'inclusive of all taxes'",
            "observed": "tax phrase absent",
            "expected": "'inclusive of all taxes'",
        }
    ]
    prompt = build_explain_prompt("NON_COMPLIANT", results, [], 82.5)
    assert "NON_COMPLIANT" in prompt
    assert "LMPC-6.1-mrp" in prompt
    assert "82.5" in prompt


def test_gemini_off_by_default_without_network(monkeypatch):
    # Hermetic: force "off" regardless of any ambient .env on the dev machine.
    monkeypatch.setattr(
        llm_mod,
        "get_settings",
        lambda: SimpleNamespace(llm_provider="off", gemini_api_key="", llm_model="x"),
    )
    try:
        llm_mod.explain_with_gemini("hello", timeout_s=1.0)
    except LlmNotConfigured:
        return
    raise AssertionError("expected LlmNotConfigured when no API key is set")
