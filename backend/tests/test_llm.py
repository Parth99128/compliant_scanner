"""Offline tests for the optional Gemini adapter — no network, no key needed."""

from app.services.llm import LlmNotConfigured, build_explain_prompt, explain_with_gemini


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


def test_gemini_off_by_default_without_network():
    # Default config has no key -> must fail closed without any HTTP call.
    try:
        explain_with_gemini("hello", timeout_s=1.0)
    except LlmNotConfigured:
        return
    raise AssertionError("expected LlmNotConfigured when no API key is set")
