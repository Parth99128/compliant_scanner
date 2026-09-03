"""Optional Gemini LLM adapter: plain-language explanations of scan findings.

Delegation position: the core pipeline is 100% local CPU and never needs a
key. This adapter is OFF by default (`LLM_PROVIDER=off`) and only fires when
an authenticated officer explicitly taps "AI explain" — the API key stays
server-side in `.env`, never ships to the frontend.

When enabled (`LLM_PROVIDER=gemini` + `GEMINI_API_KEY`), the backend sends a
text-only prompt (verdict + per-rule outcomes, no images) to the Gemini
`generateContent` REST endpoint via httpx (already a backend dependency).
"""

from __future__ import annotations

import httpx

from app.core.config import get_settings

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class LlmNotConfigured(Exception):
    """Raised when the LLM feature is off or has no API key."""


class LlmError(Exception):
    """Raised when the provider call fails (network, auth, quota, bad payload)."""


def build_explain_prompt(
    verdict: str,
    results: list[dict],
    warnings: list[str],
    ocr_confidence: float | None = None,
) -> str:
    """Deterministic prompt builder — pure function, unit-tested, no network."""
    lines = [
        "You explain Legal Metrology (Packaged Commodities) Rules, 2011 label-scan",
        "results to a non-technical seller in 3 short sections: Verdict, Issues, Next steps.",
        f"Overall verdict: {verdict}.",
    ]
    if ocr_confidence is not None:
        lines.append(f"OCR confidence: {ocr_confidence}%.")
    lines.append("Per-rule findings:")
    for r in results:
        lines.append(
            f"- {r.get('rule_id')} [{r.get('status')}]: {r.get('message')}"
            f" (observed: {r.get('observed')}; expected: {r.get('expected')})"
        )
    if warnings:
        lines.append("Warnings: " + "; ".join(warnings))
    lines.append(
        "Keep it under 150 words. Do not invent rule text beyond what is listed."
    )
    return "\n".join(lines)


def explain_with_gemini(prompt: str, timeout_s: float = 60.0) -> tuple[str, str]:
    """Call Gemini and return (explanation_text, model). Raises LlmNotConfigured/LlmError."""
    settings = get_settings()
    if settings.llm_provider.lower() not in ("gemini", "gemma") or not settings.gemini_api_key:
        raise LlmNotConfigured(
            "LLM is off: set LLM_PROVIDER=gemini (or gemma) and GEMINI_API_KEY in .env to enable."
        )
    model = settings.llm_model
    try:
        resp = httpx.post(
            GEMINI_ENDPOINT.format(model=model),
            params={"key": settings.gemini_api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=timeout_s,
        )
    except Exception as exc:
        raise LlmError(f"Gemini request failed: {exc}") from exc
    if resp.status_code != 200:
        raise LlmError(f"Gemini HTTP {resp.status_code}: {resp.text[:300]}")
    try:
        parts = resp.json()["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts).strip()
    except (KeyError, IndexError, ValueError) as exc:
        raise LlmError(f"Unexpected Gemini response shape: {resp.text[:300]}") from exc
    if not text:
        raise LlmError("Gemini returned an empty explanation.")
    return text, model
