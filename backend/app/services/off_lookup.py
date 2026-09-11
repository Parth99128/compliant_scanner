"""Open Food Facts cross-check: validate a decoded barcode against public data.

When the pipeline decodes a GTIN, OFF often knows that product's name and
quantity. That public record becomes an independent second opinion over our
OCR read — surfaced as a *warning* (verify on pack), never as an overwrite.

Offline-first: timeouts, DNS failures and unknown barcodes all yield None
fast. Only digits the camera saw are sent (no PII). Pure stdlib.
"""

from __future__ import annotations

import json
import urllib.request

UA = {"User-Agent": "DrishtiLM-SIH26034/1.0 (accuracy cross-check)"}
_ENDPOINT = "https://world.openfoodfacts.org/api/v2/product/{code}?fields=product_name,quantity,brands"


def lookup_by_barcode(digits: str, timeout_s: float = 8.0) -> dict | None:
    """OFF record for a barcode, or None on any failure. Never raises."""
    try:
        code = "".join(c for c in str(digits or "") if c.isdigit())
        if len(code) < 8:
            return None
        req = urllib.request.Request(_ENDPOINT.format(code=code), headers=UA)
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            payload = json.load(resp)
        product = (payload or {}).get("product") or {}
        name = str(product.get("product_name") or "").strip()
        quantity = str(product.get("quantity") or "").strip()
        if not name and not quantity:
            return None
        return {"code": code, "name": name or None, "quantity": quantity or None}
    except Exception:
        return None


def cross_check_warning(record: dict | None, product_name: str | None, qty_text: str | None) -> str | None:
    """Human-readable agree/disagree note, or None when there is nothing to say."""
    try:
        if not record or (not record.get("name") and not record.get("quantity")):
            return None
        name = record.get("name")
        qty = record.get("quantity")
        bits: list[str] = []
        if name:
            bits.append(f"'{name}'")
        if qty:
            bits.append(str(qty))
        ref = " ".join(bits)
        agree: list[str] = []
        if isinstance(name, str) and name and isinstance(product_name, str) and product_name:
            agree.append("name matches" if name.lower() in product_name.lower() else "name DIFFERS")
        if isinstance(qty, str) and qty and isinstance(qty_text, str) and qty_text:
            agree.append("quantity matches" if qty.lower() in qty_text.lower() else "quantity DIFFERS")
        verdict = "; ".join(agree) if agree else "compare with our read"
        return (
            f"Open Food Facts lists barcode {record.get('code')} as {ref} "
            f"({verdict}) — verify on the physical package."
        )
    except Exception:
        return None
