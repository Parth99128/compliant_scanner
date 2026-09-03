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


def _tesseract(image_bytes: bytes) -> OcrResult | None:
    try:
        import io
        import os

        import pytesseract  # type: ignore
        from PIL import Image

        # Auto-detect Windows default install (present but not on PATH).
        for candidate in (
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ):
            if os.path.exists(candidate):
                pytesseract.pytesseract.tesseract_cmd = candidate
                break
        img = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(img)
        if text and text.strip():
            return OcrResult(text=text.strip(), engine="tesseract", confidence=_mean_confidence(image_bytes))
        return None
    except Exception:
        return None


def _mean_confidence(image_bytes: bytes) -> float:
    """Mean word confidence (0-100); 0.0 when unavailable. Never raises."""
    try:
        import io

        import pytesseract  # type: ignore
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        confs = [
            float(c)
            for c, t in zip(data.get("conf", []), data.get("text", []))
            if str(t).strip() and float(c) >= 0
        ]
        return round(sum(confs) / len(confs), 1) if confs else 0.0
    except Exception:
        return 0.0


def word_boxes(image_bytes: bytes) -> list[WordBox]:
    """Word-level bounding boxes for frontend overlays. Empty list on any failure."""
    try:
        import io

        import pytesseract  # type: ignore
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        boxes: list[WordBox] = []
        n = len(data.get("text", []))
        for i in range(n):
            t = str(data["text"][i]).strip()
            if not t:
                continue
            try:
                conf = float(data["conf"][i])
            except (ValueError, TypeError):
                conf = -1.0
            boxes.append(
                WordBox(
                    text=t,
                    x=int(data["left"][i]),
                    y=int(data["top"][i]),
                    w=int(data["width"][i]),
                    h=int(data["height"][i]),
                    confidence=conf,
                )
            )
        return boxes
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
    if primary and primary.text:
        return primary
    return OcrResult(text="", engine="none", confidence=0.0)
