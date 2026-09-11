"""OCR adapter: Tesseract CPU -> EasyOCR CPU -> Cloud Vision fallback (stub)."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import get_settings


@dataclass
class WordBox:
    text: str
    x: int
    y: int
    w: int
    h: int
    confidence: float


@dataclass
class OcrResult:
    text: str
    engine: str
    confidence: float = 0.0
    boxes: list[WordBox] = field(default_factory=list)
    config: str = "--oem 3 --psm 3"  # winning Tesseract config (box geometry source)


# Tesseract configs, best first per measured evidence (see ml tuning notes):
# PSM 3 = fully automatic page segmentation (flat scans); PSM 11 = sparse
# text (label photos with graphics). Dual-pass keeps the higher-confidence
# read; PSM 11 doubles photo readability (6/20 -> 12/20 @>=60%) with zero
# regression on clean labels, at ~2x OCR cost (still inside the 5 s budget).
TESS_CONFIGS = ("--oem 3 --psm 3", "--oem 3 --psm 11")


def _tesseract_full(image_bytes: bytes, config: str) -> tuple[str, float, list[WordBox]]:
    """One image_to_data pass -> (text, mean confidence 0-100, word boxes)."""
    import io

    import pytesseract  # type: ignore
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))
    data = pytesseract.image_to_data(img, config=config, output_type=pytesseract.Output.DICT)
    words: list[WordBox] = []
    confs: list[float] = []
    lines: list[str] = []
    cur: list[str] = []
    last_key: object = None
    n = len(data.get("text", []))
    for i in range(n):
        t = str(data["text"][i]).strip()
        if not t:
            continue
        # Rebuild line breaks (extraction + merge depend on line structure).
        try:
            key = (int(data["block_num"][i]), int(data["par_num"][i]), int(data["line_num"][i]))
        except (KeyError, ValueError, TypeError):
            key = (-1, -1, i)
        if key != last_key and cur:
            lines.append(" ".join(cur))
            cur = []
        last_key = key
        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError):
            conf = -1.0
        if conf >= 0:
            confs.append(conf)
        cur.append(t)
        try:
            x, y, w, h = (int(data[k][i]) for k in ("left", "top", "width", "height"))
        except (ValueError, TypeError, KeyError):
            continue
        words.append(WordBox(text=t, x=x, y=y, w=w, h=h, confidence=conf))
    if cur:
        lines.append(" ".join(cur))
    text = "\n".join(lines)
    conf = round(sum(confs) / len(confs), 1) if confs else 0.0
    return text, conf, words


# A first-pass read this strong is never beaten enough by PSM 11 to justify
# a second full pass (~2-3s saved on every clean label).
STRONG_READ_CONF = 80.0


def _tesseract(image_bytes: bytes) -> OcrResult | None:
    try:
        import os

        import pytesseract  # type: ignore

        # Auto-detect Windows default install (present but not on PATH).
        for candidate in (
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ):
            if os.path.exists(candidate):
                pytesseract.pytesseract.tesseract_cmd = candidate
                break
        best: OcrResult | None = None
        for n, config in enumerate(TESS_CONFIGS):
            text, conf, boxes = _tesseract_full(image_bytes, config)
            if text and text.strip():
                cand = OcrResult(
                    text=text.strip(), engine="tesseract", confidence=conf, config=config, boxes=boxes
                )
                if best is None or cand.confidence > best.confidence:
                    best = cand
                if n == 0 and best.confidence >= STRONG_READ_CONF:
                    break  # clean read: skip the second pass entirely
        return best
    except Exception:
        return None


def _apply_row_repairs(result: OcrResult, repaired: list) -> OcrResult:
    """Splice validated TrOCR row re-reads into boxes + text.

    Repaired rows replace their member words with one union box carrying the
    new text; remaining rows keep original geometry. Text is rebuilt from
    visual-row geometry so line-scoped extraction keeps working. No-op on
    any shape mismatch. Never raises.
    """
    try:
        if not repaired or not result.boxes:
            return result
        drop: set[int] = set()
        new_boxes: list[WordBox] = []
        for idxs, union, text in repaired:
            if not text or not idxs:
                continue
            if any(i < 0 or i >= len(result.boxes) for i in idxs):
                continue
            drop.update(idxs)
            try:
                new_boxes.append(
                    WordBox(
                        text=str(text),
                        x=int(union.get("x", 0)),
                        y=int(union.get("y", 0)),
                        w=int(union.get("w", 0)),
                        h=int(union.get("h", 0)),
                        confidence=float(union.get("confidence", 0.0)),
                    )
                )
            except (TypeError, ValueError):
                continue
        if not new_boxes:
            return result
        kept = [b for i, b in enumerate(result.boxes) if i not in drop]
        result.boxes[:] = kept + new_boxes
        try:
            from app.services.layout import build_lines

            lines = build_lines(result.boxes)
            if lines:
                result.text = "\n".join(ln.text for ln in lines).strip() or result.text
        except Exception:  # noqa: S110 — keep pre-repair text when regrouping fails
            pass
        result.engine = "tesseract+trocr"
        return result
    except Exception:
        return result


def _mean_confidence(image_bytes: bytes, config: str = "--oem 3 --psm 3") -> float:
    """Mean word confidence (0-100); 0.0 when unavailable. Never raises."""
    try:
        import io

        import pytesseract  # type: ignore
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        data = pytesseract.image_to_data(img, config=config, output_type=pytesseract.Output.DICT)
        confs = [
            float(c)
            for c, t in zip(data.get("conf", []), data.get("text", []))
            if str(t).strip() and float(c) >= 0
        ]
        return round(sum(confs) / len(confs), 1) if confs else 0.0
    except Exception:
        return 0.0


def word_boxes(image_bytes: bytes, config: str = "--oem 3 --psm 3") -> list[WordBox]:
    """Word-level bounding boxes for frontend overlays. Empty list on any failure."""
    try:
        return _tesseract_full(image_bytes, config)[2]
    except Exception:
        return []


def _cloud_vision_stub(_image_bytes: bytes) -> OcrResult | None:
    # Optional adapter: wire GOOGLE_APPLICATION_CREDENTIALS here. Kept as stub
    # so local CPU runs never require network/credentials.
    if get_settings().cloud_vision_enabled.lower() == "true":
        return OcrResult(text="", engine="cloud-vision-stub", confidence=0.0)
    return None


def run_ocr(image_bytes: bytes) -> OcrResult:
    """Best-effort local OCR. Never raises — returns empty result if engines missing.

    Multi-engine arbitration (all local): Tesseract is primary. When the
    optional Florence-2 VLM is enabled, a weak/empty Tesseract read (<60%
    confidence) falls back to the longer Florence-2 text. A strong Tesseract
    read is never overruled (Florence-2 reports no word confidences).
    """
    primary: OcrResult | None = None
    for fn in (_tesseract, _cloud_vision_stub):
        try:
            r = fn(image_bytes)
            if r and r.text:
                primary = r
                break
        except Exception:
            continue
    # TrOCR row repair (optional, local CPU transformer): re-read weak,
    # cue-carrying rows whose text does not parse — accepted only when the
    # re-read DOES parse as an MRP amount, date or quantity. Strong reads
    # (>=75%) skip it entirely; empty reads have nothing to align.
    # Confidence stays conservative (never revised up).
    if primary and primary.text.strip() and primary.confidence < 75 and primary.boxes:
        try:
            from app.services.trocr import is_enabled as _tr_enabled
            from app.services.trocr import repair_rows as _tr_rows
        except Exception:
            _tr_enabled = None  # type: ignore[assignment]
            _tr_rows = None  # type: ignore[assignment]
        if _tr_enabled is not None and _tr_enabled():
            try:
                assert _tr_rows is not None
                rows = _tr_rows(image_bytes, primary.boxes)
            except Exception:
                rows = []
            if rows:
                primary = _apply_row_repairs(primary, rows)
    try:
        from app.services.florence import is_enabled as _fl_enabled
        from app.services.florence import run_florence_ocr as _fl_ocr
    except Exception:  # Florence-2 adapter missing/broken -> single-engine mode
        _fl_enabled = None  # type: ignore[assignment]
        _fl_ocr = None  # type: ignore[assignment]
    if _fl_enabled is not None and _fl_enabled():
        try:
            alt = _fl_ocr(image_bytes)
        except Exception:
            alt = None
        if (
            alt
            and alt.text
            and (
                primary is None
                or primary.text.strip() == ""
                or (primary.confidence < 60 and len(alt.text) > len(primary.text))
            )
        ):
            return alt
    # Generic local VLM (optional, slower): same acceptance rule as Florence-2.
    # Consulted only when enabled AND the read is still weak or empty.
    if primary is None or not primary.text.strip() or primary.confidence < 60:
        try:
            from app.services.vlm import is_enabled as _vlm_enabled
            from app.services.vlm import run_vlm_ocr as _vlm_ocr
        except Exception:  # VLM adapter missing/broken -> skip silently
            _vlm_enabled = None  # type: ignore[assignment]
            _vlm_ocr = None  # type: ignore[assignment]
        if _vlm_enabled is not None and _vlm_enabled():
            try:
                valt = _vlm_ocr(image_bytes)
            except Exception:
                valt = None
            if (
                valt
                and valt.text
                and (
                    primary is None
                    or primary.text.strip() == ""
                    or (primary.confidence < 60 and len(valt.text) > len(primary.text))
                )
            ):
                return valt
    if primary and primary.text:
        return primary
    return OcrResult(text="", engine="none", confidence=0.0)
