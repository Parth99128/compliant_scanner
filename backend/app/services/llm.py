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
    lines.append("Keep it under 150 words. Do not invent rule text beyond what is listed.")
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


EXTRACT_FIELDS = (
    "mrp",
    "mrp_includes_taxes",
    "net_quantity_value",
    "net_quantity_unit",
    "mfg_date",
    "expiry_date",
    "manufacturer_name",
    "manufacturer_address",
    "generic_name",
    "consumer_care",
    "country_of_origin",
    "is_imported",
)

_VALID_UNITS = frozenset({"g", "kg", "mg", "ml", "l", "cm", "m", "nos", "no", "pc", "pcs", "unit"})


def build_extract_prompt(ocr_text: str, ocr_confidence: float | None = None) -> str:
    """Deterministic extraction prompt — pure function, unit-tested, no network.

    The JSON-only demand sits LAST: small models obey recency over preamble.
    """
    return "\n".join(
        [
            "OCR text from an Indian packaged-commodity label:",
            (ocr_text or "")[:4000],
            f"OCR confidence: {ocr_confidence}%." if ocr_confidence is not None else "",
            "Extract: mrp (printed price, never a unit-sale price like Rs. 1/g), "
            + "mrp_includes_taxes, net_quantity_value + net_quantity_unit "
            + "(g|kg|mg|ml|l|cm|m|nos|pc), mfg_date and expiry_date (YYYY-MM-DD), "
            + "manufacturer_name, manufacturer_address, generic_name, consumer_care, "
            + "country_of_origin, is_imported. Null when the text does not state it.",
            "Reply with ONLY a JSON object with exactly these keys, no other text:",
            '{"mrp": 0, "mrp_includes_taxes": true, "net_quantity_value": 0, '
            + '"net_quantity_unit": "g", "mfg_date": "2025-01-15", '
            + '"expiry_date": null, "manufacturer_name": null, '
            + '"manufacturer_address": null, "generic_name": null, '
            + '"consumer_care": null, "country_of_origin": null, "is_imported": null}',
        ]
    )


def _clean_json(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return text


def normalize_extract_payload(payload: object) -> dict:
    """Validate + normalize a model JSON blob into declaration patch keys.

    Unknown keys dropped, wrong types coerced-or-dropped, dates parsed with
    the same parser as the regex path. Pure function, unit-tested.
    """
    from app.services import extraction as _ex

    out: dict = {}
    if not isinstance(payload, dict):
        return out
    try:
        mrp = payload.get("mrp")
        if isinstance(mrp, bool):
            pass
        elif isinstance(mrp, (int, float)) and mrp > 0:
            out["mrp"] = float(mrp)
        taxes = payload.get("mrp_includes_taxes")
        if isinstance(taxes, bool):
            out["mrp_includes_taxes"] = taxes
        qty = payload.get("net_quantity_value")
        unit = payload.get("net_quantity_unit")
        if isinstance(qty, (int, float)) and not isinstance(qty, bool) and qty > 0:
            out["net_quantity_value"] = float(qty)
        if isinstance(unit, str) and unit.lower().rstrip("s") in _VALID_UNITS:
            out["net_quantity_unit"] = unit.lower().rstrip("s")
        for key in ("mfg_date", "expiry_date"):
            raw = payload.get(key)
            if isinstance(raw, str) and raw.strip():
                parsed = _ex._parse_date(raw.strip())
                if parsed is not None:
                    out[key] = parsed
        for key in (
            "manufacturer_name",
            "manufacturer_address",
            "generic_name",
            "consumer_care",
            "country_of_origin",
        ):
            raw = payload.get(key)
            if isinstance(raw, str) and raw.strip():
                out[key] = raw.strip()[:300]
        imp = payload.get("is_imported")
        if isinstance(imp, bool):
            out["is_imported"] = imp
    except Exception:
        return {}
    return out


def extract_with_gemini(
    ocr_text: str,
    ocr_confidence: float | None = None,
    image_bytes: bytes | None = None,
    timeout_s: float = 45.0,
) -> tuple[dict, str]:
    """Structured declaration extraction. Returns (patch_dict, model).

    Sends OCR text plus (when available) the label photo for visual grounding.
    Raises LlmNotConfigured/LlmError. Never returns unvalidated model output —
    everything passes through normalize_extract_payload.
    """
    import base64

    settings = get_settings()
    if settings.llm_provider.lower() not in ("gemini", "gemma") or not settings.gemini_api_key:
        raise LlmNotConfigured(
            "LLM is off: set LLM_PROVIDER=gemini (or gemma) and GEMINI_API_KEY in .env to enable."
        )
    model = settings.llm_model
    parts: list[dict] = [{"text": build_extract_prompt(ocr_text, ocr_confidence)}]
    if image_bytes:
        try:
            parts.append(
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": base64.b64encode(bytes(image_bytes)).decode("ascii"),
                    }
                }
            )
        except Exception:  # noqa: S110 — text-only fallback when bytes are unusable
            pass
    # Small models occasionally echo the prompt instead of answering: one
    # retry, then give up loudly (the pipeline treats it as assist-off).
    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            return _extract_once(model, settings.gemini_api_key, parts, timeout_s)
        except LlmNotConfigured:
            raise
        except LlmError as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


def _extract_once(model: str, api_key: str, parts: list[dict], timeout_s: float) -> tuple[dict, str]:
    try:
        resp = httpx.post(
            GEMINI_ENDPOINT.format(model=model),
            params={"key": api_key},
            json={
                "contents": [{"parts": parts}],
                "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"},
            },
            timeout=timeout_s,
        )
    except Exception as exc:
        raise LlmError(f"Gemini request failed: {exc}") from exc
    if resp.status_code != 200:
        raise LlmError(f"Gemini HTTP {resp.status_code}: {resp.text[:300]}")
    try:
        raw_parts = resp.json()["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in raw_parts).strip()
    except (KeyError, IndexError, ValueError) as exc:
        raise LlmError(f"Unexpected Gemini response shape: {resp.text[:300]}") from exc
    if not text:
        raise LlmError("Gemini returned an empty extraction.")
    import json as _json

    try:
        payload = _json.loads(_clean_json(text))
    except ValueError as exc:
        raise LlmError(f"Gemini did not return JSON: {text[:200]}") from exc
    return normalize_extract_payload(payload), model
