"""POST /scans/merge: multi-angle captures merged into one verdict."""

import io

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.main import create_app

client = TestClient(create_app())


def _png_bytes(text="MRP Rs. 99 Inclusive of all taxes"):
    img = Image.new("RGB", (900, 300), "white")
    ImageDraw.Draw(img).text((20, 20), text, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _auth() -> str:
    body = {"username": "mergeuser", "password": "mergepass123"}
    client.post("/api/v1/auth/register", json=body)
    r = client.post("/api/v1/auth/login", json=body)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _files(n):
    return [("files", (f"m{i}.png", _png_bytes(), "image/png")) for i in range(n)]


def test_merge_two_images_ok():
    tok = _auth()
    r = client.post("/api/v1/scans/merge", files=_files(2), headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "+merge2" in body["ocr_engine"]
    assert any("Merged 2 captures" in w for w in body["warnings"])
    assert len(body["results"]) == 10


def test_merge_rejects_single_image():
    tok = _auth()
    r = client.post("/api/v1/scans/merge", files=_files(1), headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 422


def test_merge_rejects_six_images():
    tok = _auth()
    r = client.post("/api/v1/scans/merge", files=_files(6), headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 422


def test_merge_requires_auth():
    r = client.post("/api/v1/scans/merge", files=_files(2))
    assert r.status_code == 401


def test_merged_scan_appears_in_dashboard_list():
    """Phase 5 acceptance: a mobile-style 2-frame upload shows up live in /scans."""
    tok = _auth()
    up = client.post("/api/v1/scans/merge", files=_files(2), headers={"Authorization": f"Bearer {tok}"})
    assert up.status_code == 200, up.text
    scan_id = up.json()["id"]
    rows = client.get("/api/v1/scans", headers={"Authorization": f"Bearer {tok}"}).json()
    match = [r for r in rows if r["id"] == scan_id]
    assert len(match) == 1
    assert match[0]["verdict"] == up.json()["verdict"]
    assert "+merge2" in match[0]["ocr_engine"]
