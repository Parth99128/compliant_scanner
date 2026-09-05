"""Polarity-aware binarization: light-on-dark labels must come out dark-on-light."""

import io

import pytest
from PIL import Image, ImageDraw

from app.services.vision import (
    deskew_image_bytes,
    detect_rotation_degrees,
    estimate_skew_angle,
    preprocess_for_ocr,
    upright_image_bytes,
)

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")


def _label_png(text, fg, bg, size=(900, 300)):
    img = Image.new("RGB", size, bg)
    ImageDraw.Draw(img).text((30, 100), text, fill=fg)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _mean_gray(png: bytes) -> float:
    arr = np.frombuffer(png, dtype=np.uint8)
    return float(np.mean(cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)))


def test_dark_on_light_stays_light():
    out = preprocess_for_ocr(_label_png("MRP Rs. 99", "black", "white"))
    assert _mean_gray(out) > 127.0


def test_light_on_dark_is_inverted_to_light():
    # White print on a Coke-red can: must not stay dark-background.
    out = preprocess_for_ocr(_label_png("330 ml e", "white", (200, 0, 0)))
    assert _mean_gray(out) > 127.0


def test_garbage_bytes_pass_through():
    raw = b"not-an-image"
    assert preprocess_for_ocr(raw) == raw


def _tilted_label_png(degrees: float = 10.0) -> bytes:
    img = Image.new("RGB", (900, 400), "white")
    d = ImageDraw.Draw(img)
    d.text((60, 60), "Wheat Biscuits Net Qty: 500 g", fill="black")
    d.text((60, 160), "MRP Rs. 120 Inclusive of all taxes", fill="black")
    d.text((60, 260), "Mfg: 01/01/2025 Exp: 01/01/2026", fill="black")
    img = img.rotate(degrees, expand=True, fillcolor="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_skew_estimate_close_to_true_tilt():
    angle = estimate_skew_angle(_tilted_label_png(10.0))
    assert angle is not None
    assert abs(abs(angle) - 10.0) < 3.0


def test_deskew_straightens_tilted_label():
    raw = _tilted_label_png(10.0)
    fixed = deskew_image_bytes(raw)
    assert fixed != raw
    after = estimate_skew_angle(fixed)
    assert after is not None and abs(after) < 3.0


def test_deskew_passthrough_on_flat_and_garbage():
    flat = _label_png("MRP Rs. 99", "black", "white")
    # Sub-degree tilt is left untouched: same pixels back (re-encoded PNG).
    assert estimate_skew_angle(flat) is not None and abs(estimate_skew_angle(flat)) < 0.5  # type: ignore[operator]
    assert _mean_gray(deskew_image_bytes(flat)) == _mean_gray(flat)
    assert deskew_image_bytes(b"not-an-image") == b"not-an-image"
    assert estimate_skew_angle(b"not-an-image") is None


def _big_label_png(degrees: float = 0.0) -> bytes:
    """Dense large-type render: enough for Tesseract OSD at any angle."""
    from PIL import ImageFont

    try:
        font = ImageFont.load_default(size=48)
    except Exception:
        font = ImageFont.load_default()
    img = Image.new("RGB", (1400, 700), "white")
    d = ImageDraw.Draw(img)
    y = 30
    for ln in (
        "Wheat Biscuits Net Qty: 500 g",
        "MRP Rs. 120 Inclusive of all taxes",
        "Mfg: 01/01/2025 Exp: 01/01/2026",
        "Customer Care: care@acme.in 1800-123-456",
        "Acme Foods Plot 5 Mumbai 400001",
        "Country of Origin: India",
    ):
        d.text((40, y), ln, fill="black", font=font)
        y += 105
    if degrees:
        img = img.rotate(degrees, expand=True, fillcolor="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_osd_detects_sideways_and_upside_down():
    assert detect_rotation_degrees(_big_label_png(0)) == 0
    assert detect_rotation_degrees(_big_label_png(90)) == 90
    assert detect_rotation_degrees(_big_label_png(180)) == 180
    assert detect_rotation_degrees(_big_label_png(270)) == 270


def test_upright_repairs_sideways_capture():
    fixed = upright_image_bytes(_big_label_png(90))
    angle = estimate_skew_angle(fixed)
    assert angle is not None and abs(angle) < 3.0


def test_rotation_passthrough_when_unsure():
    assert detect_rotation_degrees(b"not-an-image") == 0
    assert upright_image_bytes(b"not-an-image") == b"not-an-image"
    blank = Image.new("RGB", (200, 200), "white")
    buf = io.BytesIO()
    blank.save(buf, format="PNG")
    assert detect_rotation_degrees(buf.getvalue()) == 0
