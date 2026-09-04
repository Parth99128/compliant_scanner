"""OpenCV preprocessing (deskew, denoise, upscale) + spatial PPM calibration.

All functions degrade gracefully when opencv/numpy are absent (CI-lite environments).
Micro-text super-resolution uses cv2.dnn_superres (ESPCN/FSRCNN) when model
files are present under models/; otherwise falls back to cubic upscaling.
"""

from __future__ import annotations

import os

# Standard credit-card reference (ISO/IEC 7810 ID-1), usable as alignment stencil.
CARD_W_MM = 85.60
CARD_H_MM = 53.98


def _dnn_upscale(gray: object, scale: int = 2) -> object | None:
    """ESPCN/FSRCNN super-resolution if model files exist, else None."""
    try:
        import cv2  # type: ignore
    except ImportError:
        return None
    for name, model in (("espcn", "ESPCN_x2.pb"), ("fsrcnn", "FSRCNN_x2.pb")):
        path = os.path.join("models", model)
        if not os.path.exists(path):
            continue
        try:
            sr = cv2.dnn_superres.DnnSuperResImpl_create()  # type: ignore[attr-defined]
            sr.readModel(path)
            sr.setModel(name, scale)
            return sr.upsample(gray)  # type: ignore[no-any-return]
        except Exception:
            continue
    return None


def mask_quads(raw: bytes, detections: list[dict], pad: int = 10) -> bytes:
    """Paint white over barcode quads so OCR/VLM stops hallucinating on bars.

    `detections` come from barcode.decode_positioned (quads in capped-1200px
    space + that space's size); they are rescaled to the full image. Returns
    the input bytes unchanged when there is nothing to mask or on any error.
    """
    if not detections:
        return raw
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return raw
    try:
        arr = np.frombuffer(raw, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return raw
        ih, iw = img.shape[:2]
        for det in detections:
            quad = det.get("quad")
            size = det.get("size")
            if not quad or not size or len(quad) != 4:
                continue
            sw, sh = size
            if not sw or not sh:
                continue
            pts = np.array([[(x / sw) * iw, (y / sh) * ih] for x, y in quad], dtype=np.int32)
            x, y, w, h = cv2.boundingRect(pts)
            cv2.rectangle(
                img,
                (max(0, x - pad), max(0, y - pad)),
                (min(iw, x + w + pad), min(ih, y + h + pad)),
                (255, 255, 255),
                thickness=-1,
            )
        ok, buf = cv2.imencode(".png", img)
        return bytes(buf) if ok else raw
    except Exception:
        return raw


def preprocess_for_ocr(image_bytes: bytes) -> bytes:
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return image_bytes  # no-op fallback
    try:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return image_bytes
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.bilateralFilter(gray, 5, 50, 50)
        # Polarity-aware binarization: Tesseract needs dark text on a light
        # background. Light-on-dark labels (white print on a red can, black
        # pack with gold text, …) have a dark mean, so OTSU must be inverted.
        thresh_type = cv2.THRESH_BINARY
        try:
            if float(np.mean(gray)) < 127.0:
                thresh_type = cv2.THRESH_BINARY_INV
        except Exception:
            thresh_type = cv2.THRESH_BINARY
        _, binary = cv2.threshold(gray, 0, 255, thresh_type + cv2.THRESH_OTSU)
        h, w = binary.shape
        if max(h, w) < 1200:  # micro-text path: SR model if present, else 2x cubic
            up = _dnn_upscale(binary, 2)
            if up is not None:
                binary = up  # type: ignore[assignment]
            else:
                binary = cv2.resize(binary, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
        ok, buf = cv2.imencode(".png", binary)
        return bytes(buf) if ok else image_bytes
    except Exception:
        return image_bytes


def estimate_ppm(reference_pixel_width: float, reference_mm_width: float) -> float | None:
    """Pixel-Per-Millimeter ratio from a known reference object (e.g. coin/ruler)."""
    if not reference_pixel_width or not reference_mm_width or reference_mm_width <= 0:
        return None
    return reference_pixel_width / reference_mm_width


def font_height_mm(font_pixel_height: float, ppm: float | None) -> float | None:
    if ppm is None or ppm <= 0 or font_pixel_height <= 0:
        return None
    return round(font_pixel_height / ppm, 2)


def detect_ppm_from_reference_card(image_bytes: bytes) -> float | None:
    """Detect a card-sized quadrilateral (default: credit-card stencil) and derive PPM.

    Finds the largest 4-point contour, takes its longer edge as CARD_W_MM.
    Returns None when opencv is missing or no quadrilateral is found.
    """
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return None
    try:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best: float = 0.0
        for cnt in contours:
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            if len(approx) == 4:
                area = cv2.contourArea(approx)
                if area > best and area > 1000:
                    rect = cv2.minAreaRect(approx)
                    long_edge = max(rect[1])
                    if long_edge > 0:
                        best = area
                        ppm = long_edge / CARD_W_MM
        return ppm if best > 0 else None
    except Exception:
        return None
