"""POST /scans/preview: live-camera frame analysis (no DB write)."""

import io

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.main import create_app
from app.services.vision import sharpness_score

client = TestClient(create_app())


def _png_bytes(lines=("Wheat Biscuits", "Net Qty: 500 g", "MRP Rs. 120 Inclusive of all taxes")):
    img = Image.new("RGB", (900, 400), "white")
    d = ImageDraw.Draw(img)
    y = 20
    for ln in lines:
        d.text((20, y), ln, fill="black")
        y += 60
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _auth() -> str:
    body = {"username": "previewuser", "password": "previewpass123"}
    client.post("/api/v1/auth/register", json=body)
    r = client.post("/api/v1/auth/login", json=body)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_sharpness_orders_sharp_above_blur():
    sharp = _png_bytes()
    blurred = Image.open(io.BytesIO(sharp)).filter(
        __import__("PIL.ImageFilter", fromlist=["x"]).GaussianBlur(5)
    )
    buf = io.BytesIO()
    blurred.save(buf, format="PNG")
    s_sharp = sharpness_score(sharp)
    s_blur = sharpness_score(buf.getvalue())
    assert s_sharp is not None and s_blur is not None
    assert s_sharp > s_blur
    assert sharpness_score(b"junk") is None


def test_preview_returns_checklist_and_size():
    tok = _auth()
    r = client.post(
        "/api/v1/scans/preview",
        files={"file": ("frame.png", _png_bytes(), "image/png")},
        data={"ppm": "10"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["word_count"] > 0
    assert body["font_height_mm"] is not None  # ppm supplied -> size calc runs
    assert body["ppm_used"] == 10
    assert set(body["fields_found"]) == {"generic", "manufacturer", "net_qty", "mrp", "mfg_date", "care"}
    assert body["fields_total"] == 6
    assert isinstance(body["ready"], bool) and body["ready_reason"]
    assert "request_id" in body


def test_preview_requires_auth_and_rejects_bad_type():
    r = client.post("/api/v1/scans/preview", files={"file": ("f.png", _png_bytes(), "image/png")})
    assert r.status_code == 401
    tok = _auth()
    r = client.post(
        "/api/v1/scans/preview",
        files={"file": ("x.txt", b"hi", "text/plain")},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 415


def test_preview_does_not_create_scan():
    tok = _auth()
    before = client.get("/api/v1/scans", headers={"Authorization": f"Bearer {tok}"}).json()
    client.post(
        "/api/v1/scans/preview",
        files={"file": ("frame.png", _png_bytes(), "image/png")},
        headers={"Authorization": f"Bearer {tok}"},
    )
    after = client.get("/api/v1/scans", headers={"Authorization": f"Bearer {tok}"}).json()
    assert len(before) == len(after)
