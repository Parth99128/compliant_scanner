"""Polarity-aware binarization: light-on-dark labels must come out dark-on-light."""

import io

import pytest
from PIL import Image, ImageDraw

from app.services.vision import preprocess_for_ocr

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
