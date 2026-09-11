"""Optional TrOCR line re-reader (local transformer, CPU, off by default).

Where Tesseract wins: page layout, word boxes, speed. Where it loses: mangled
lines on stylized/curved/embossed print ("0/08/26", "MICRENIC", glued words).
TrOCR (Microsoft, MIT license) re-reads individual line crops with a
vision-encoder-decoder transformer — far stronger per-line, far slower per
page. So it is a *repair crew*, not the primary reader:

Delegation position: TrOCR is a *repair crew*, not the primary reader —
and it only changes text it can prove improves: a repaired row is accepted
only when the new text parses as a machine-readable declaration (MRP
amount, date, quantity) that the old row lacked. Fluent-but-wrong
rewrites are rejected by construction.

- `TROCR_ENABLED=true` in `.env`, otherwise everything returns fast.
- torch + transformers import lazily; default `TROCR_MODEL`
  (trocr-small-printed, ~0.4 GB) downloads from Hugging Face on first use.
- Only weak rows (<70 mean conf) carrying a field cue (digits or
  declaration keywords) are attempted, cap 4 rows/scan; strong rows and
  name/address rows (unvalidatable) are never touched.
- Repaired rows keep a union bounding box so overlays and layout logic
  stay consistent; overall confidence is left conservative.

Never raises: every failure mode returns empty.
"""

from __future__ import annotations

import re

from app.core.config import get_settings

MAX_ROWS = 4
WEAK_LINE_CONF = 70.0
_ROW_DATE_RE = re.compile(
    r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{1,2}[/\-]\d{2,4}|[A-Za-z]{3,9}[\s\-/]+\d{2,4}"
)
_ROW_CUE_RE = re.compile(
    r"\d|MRP|M\.?R\.?P\.?|retail\s*price|mfg|manufactur|exp|expiry|best\s*before"
    r"|use\s*by|net\s*q|care|helpline|toll|rs\.?|inr|₹",
    re.IGNORECASE,
)
_ROW_MRP_RE = re.compile(
    r"(?:MRP|M\.?R\.?P\.?|maximum\s*retail\s*price|retail\s*price)"
    r"[\s()\-–—]{0,8}(?:Rs\.?|INR|₹|%)?[\s()\-–—]{0,8}:?\s*(?:Rs\.?|INR|₹|%)?\s*"
    r"([\d,]+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
_ROW_QTY_RE = re.compile(
    r"net\s*(?:q?t[yl]|quantity|wt|weight|vol|content|o?t?y)[^\d]*([\d.,]+)\s*"
    r"(kg|g|mg|ml|l|litre?s?|cm|m|nos?|pcs?|pc|units?)\b"
    r"|\b([\d.,]+)\s*(kg|g\b|mg|ml|l\b|litre?s?|units?)\b",
    re.IGNORECASE,
)

_model = None
_processor = None


def is_enabled() -> bool:
    try:
        return get_settings().trocr_enabled.lower() == "true"
    except Exception:
        return False


def _load():
    """Lazily load TrOCR on CPU. Raises ImportError/RuntimeError on failure."""
    global _model, _processor
    if _model is not None:
        return _model, _processor
    import torch  # lazy: torch stays optional for default installs
    from transformers import (  # type: ignore[import-untyped]
        TrOCRProcessor,
        VisionEncoderDecoderModel,
    )

    model_id = get_settings().trocr_model
    _processor = TrOCRProcessor.from_pretrained(model_id)
    _model = VisionEncoderDecoderModel.from_pretrained(model_id, torch_dtype=torch.float32).eval()
    return _model, _processor


def _row_groups(boxes: list) -> list[tuple[list[int], float, str]]:
    """(member indexes, mean confidence, joined text) per visual row. Pure."""
    groups: dict[int, list[int]] = {}
    for i, b in enumerate(boxes or []):
        try:
            if isinstance(b, dict):
                y, h = float(b.get("y", 0)), float(b.get("h", 0))
            else:
                y, h = float(b.y), float(b.h)
        except (TypeError, ValueError, AttributeError):
            continue
        groups.setdefault(round(y / max(h, 1.0)), []).append(i)

    def _text(i: int) -> str:
        b = boxes[i]
        try:
            t = b.get("text", "") if isinstance(b, dict) else b.text
            return str(t or "")
        except (AttributeError, TypeError):
            return ""

    def _conf(i: int) -> float | None:
        b = boxes[i]
        try:
            raw = b.get("confidence", None) if isinstance(b, dict) else b.confidence
            if raw is None:
                return None
            return float(raw)
        except (TypeError, ValueError, AttributeError):
            return None

    out = []
    for idxs in groups.values():
        confs = [c for c in (_conf(i) for i in idxs) if c is not None]
        mean = sum(confs) / len(confs) if confs else 100.0
        out.append((idxs, mean, " ".join(_text(i) for i in idxs)))
    return out


def _row_parses(text: str) -> bool:
    """Does this row already yield a machine-readable declaration? Pure."""
    try:
        if _ROW_MRP_RE.search(text) or _ROW_QTY_RE.search(text):
            return True
        from app.services import extraction as _ex

        return any(_ex._parse_date(tok) is not None for tok in _ROW_DATE_RE.findall(text))
    except Exception:
        return False


def pick_weak_lines(boxes: list, limit: int = MAX_ROWS) -> list[int]:
    """Legacy flat index picker (kept for API stability). Prefer repair_rows."""
    try:
        out: list[int] = []
        for idxs, mean, _text in _row_groups(boxes):
            if mean < WEAK_LINE_CONF:
                out.extend(idxs)
            if len(out) >= limit * 4:
                break
        return out[: limit * 4]
    except Exception:
        return []


def _union_box(boxes: list, idxs: list[int]) -> dict | None:
    """Union bounding box of member words with their mean confidence."""
    try:
        xs, ys, xe, ye, confs = [], [], [], [], []
        for i in idxs:
            b = boxes[i]
            if isinstance(b, dict):
                x, y, w, h = (float(b.get(k, 0) or 0) for k in ("x", "y", "w", "h"))
                c = float(b.get("confidence", 0) or 0)
            else:
                x, y, w, h = (float(getattr(b, k)) for k in ("x", "y", "w", "h"))
                c = float(getattr(b, "confidence", 0))
            if w < 1 or h < 1:
                continue
            xs.append(x)
            ys.append(y)
            xe.append(x + w)
            ye.append(y + h)
            confs.append(c)
        if not xs:
            return None
        return {
            "text": "",
            "x": min(xs),
            "y": min(ys),
            "w": max(xe) - min(xs),
            "h": max(ye) - min(ys),
            "confidence": sum(confs) / len(confs),
        }
    except Exception:
        return None


def repair_rows(
    image_bytes: bytes, boxes: list, limit_rows: int = MAX_ROWS
) -> list[tuple[list[int], dict, str]]:
    """Validated row repairs: [(member indexes, union box, new text)].

    A row is attempted only when it is weak (<70), carries a field cue, and
    does NOT already parse; the TrOCR output is accepted only when it DOES
    parse as an MRP amount, date or quantity. Name/address rows are never
    attempted (unvalidatable). Empty list when disabled, deps missing, or on
    any error. Never raises.
    """
    if not is_enabled():
        return []
    try:
        import io

        from PIL import Image

        model, processor = _load()
        import torch

        img = Image.open(io.BytesIO(bytes(image_bytes))).convert("RGB")
        accepted: list[tuple[list[int], dict, str]] = []
        tried = 0
        for idxs, mean, text in sorted(_row_groups(boxes), key=lambda t: t[1]):
            if len(accepted) >= limit_rows or tried >= limit_rows * 2:
                break
            if mean >= WEAK_LINE_CONF or not _ROW_CUE_RE.search(text) or _row_parses(text):
                continue
            union = _union_box(boxes, idxs)
            if union is None or union["w"] < 16 or union["h"] < 10:
                continue
            tried += 1
            try:
                pad = 4
                crop = img.crop(
                    (
                        max(0, int(union["x"] - pad)),
                        max(0, int(union["y"] - pad)),
                        min(img.width, int(union["x"] + union["w"] + pad)),
                        min(img.height, int(union["y"] + union["h"] + pad)),
                    )
                )
                if crop.width < 16 or crop.height < 10:
                    continue
                pixel_values = processor(crop, return_tensors="pt").pixel_values
                with torch.no_grad():
                    ids = model.generate(pixel_values, max_length=64)
                new = processor.batch_decode(ids, skip_special_tokens=True)[0].strip()
            except Exception:
                continue
            if new and new != text and _row_parses(new):
                union["text"] = new
                accepted.append((idxs, union, new))
        return accepted
    except Exception:
        return []
