"""OpenCV preprocessing (deskew, denoise, upscale) + spatial PPM calibration.

All functions degrade gracefully when opencv/numpy are absent (CI-lite environments).
Micro-text super-resolution uses cv2.dnn_superres (ESPCN/FSRCNN) when model
files are present under models/; otherwise falls back to cubic upscaling.
"""

from __future__ import annotations

import os
from typing import Any

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
        gray = _deskew_array(gray)  # straighten tilted phone shots before OCR
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


def sharpness_score(image_bytes: bytes) -> float | None:
    """Laplacian variance focus measure. Higher = sharper. None on any failure.

    Typical phone-label frames: <30 very blurry, 30-100 soft, >100 sharp enough
    for OCR. Used by the live-preview endpoint to gate auto-capture.
    Never raises.
    """
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return None
    try:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return None
        # Downscale huge frames: variance scale is size-invariant enough and
        # this keeps live previews cheap.
        h, w = img.shape[:2]
        if max(h, w) > 800:
            scale = 800.0 / max(h, w)
            img = cv2.resize(img, (int(w * scale), int(h * scale)))
        return round(float(cv2.Laplacian(img, cv2.CV_64F).var()), 1)
    except Exception:
        return None


def estimate_skew_angle(image_bytes: bytes) -> float | None:
    """Dominant text skew in degrees, normalized to [-45, 45). None when undetectable.

    Positive = clockwise tilt. None when opencv is missing, the image is
    undecodable, or there is too little foreground text. Never raises.
    """
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return None
    try:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        gray = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if gray is None:
            return None
        return _skew_of_gray(gray)
    except Exception:
        return None


def _skew_of_gray(gray: Any) -> float | None:
    """Skew of a grayscale ndarray. None when undetectable. Never raises."""
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return None
    try:
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        coords = np.column_stack(np.where(bw > 0))
        if coords.shape[0] < 100:
            return None
        angle = cv2.minAreaRect(coords)[-1]
        # minAreaRect reports [-90, 0); fold into [-45, 45) so the magnitude
        # is the rotation that straightens the text.
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        return round(float(angle), 2)
    except Exception:
        return None


def _deskew_array(gray: Any, max_correct_deg: float = 15.0) -> Any:
    """Rotate a grayscale ndarray straight. Passthrough on failure/tiny/wild tilt."""
    try:
        import cv2  # type: ignore
    except ImportError:
        return gray
    try:
        angle = _skew_of_gray(gray)
        if angle is None or abs(angle) < 0.5 or abs(angle) > max_correct_deg:
            return gray
        h, w = gray.shape[:2]
        matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        return cv2.warpAffine(gray, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    except Exception:
        return gray


def deskew_image_bytes(image_bytes: bytes, max_correct_deg: float = 15.0) -> bytes:
    """Deskew an encoded image. Returns input unchanged on any failure. Never raises."""
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return image_bytes
    try:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        gray = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if gray is None:
            return image_bytes
        fixed = _deskew_array(gray, max_correct_deg)
        ok, buf = cv2.imencode(".png", fixed)
        return bytes(buf) if ok else image_bytes
    except Exception:
        return image_bytes


def _tesseract_cmd() -> None:
    """Point pytesseract at the Windows default install (mirror of ocr.py). Never raises."""
    try:
        import os

        import pytesseract  # type: ignore
    except Exception:
        return
    try:
        for candidate in (
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ):
            if os.path.exists(candidate):
                pytesseract.pytesseract.tesseract_cmd = candidate
                break
    except Exception:  # noqa: S110 — default PATH lookup is the fallback
        pass


def detect_rotation_degrees(image_bytes: bytes) -> int:
    """Clockwise degrees needed to upright the text: one of 0/90/180/270.

    Uses Tesseract OSD on a downscaled copy. Returns 0 whenever unsure
    (weak text, missing binary, garbage input) — callers treat 0 as "leave
    it". Threshold (orientation confidence >= 3) was probe-tuned: confident
    reads score ~7, undecodable text scores ~0. Never raises.
    """
    try:
        import io
        import re

        import pytesseract  # type: ignore
        from PIL import Image
    except Exception:
        return 0
    try:
        _tesseract_cmd()
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        if max(w, h) > 1000:
            scale = 1000.0 / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)))  # type: ignore[assignment]
        osd = pytesseract.image_to_osd(img)
        m_deg = re.search(r"Rotate:\s*(\d+)", osd)
        m_conf = re.search(r"Orientation confidence:\s*([\d.]+)", osd)
        if not m_deg or not m_conf:
            return 0
        deg, conf = int(m_deg.group(1)) % 360, float(m_conf.group(1))
        return deg if deg in (90, 180, 270) and conf >= 3.0 else 0
    except Exception:
        return 0


def upright_image_bytes(image_bytes: bytes) -> bytes:
    """Rotate sideways/upside-down captures upright. Passthrough otherwise. Never raises."""
    try:
        deg = detect_rotation_degrees(image_bytes)
        if not deg:
            return image_bytes
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        rotated = img.rotate(-deg, expand=True)  # OSD degrees are clockwise; PIL is CCW
        buf = io.BytesIO()
        rotated.save(buf, format="PNG")
        return buf.getvalue()
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
