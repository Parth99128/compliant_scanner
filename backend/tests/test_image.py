"""Stored-capture endpoint for the scan viewer."""

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())
IMG = "../data/samples/sample_00000.png"


def _auth() -> str:
    body = {"username": "imageuser", "password": "imagepass123"}
    client.post("/api/v1/auth/register", json=body)
    return client.post("/api/v1/auth/login", json=body).json()["access_token"]


def test_image_round_trip():
    tok = _auth()
    with open(IMG, "rb") as fh:
        scan = client.post(
            "/api/v1/scans",
            files={"file": ("s.png", fh, "image/png")},
            headers={"Authorization": f"Bearer {tok}"},
        ).json()
    assert scan["has_image"] is True
    r = client.get(f"/api/v1/scans/{scan['id']}/image", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "image/jpeg"
    assert r.content[:2] == b"\xff\xd8"
    det = client.get(f"/api/v1/scans/{scan['id']}", headers={"Authorization": f"Bearer {tok}"}).json()
    assert det["has_image"] is True
    assert len(det["boxes"]) > 0
    assert det["coord_w"] and det["coord_h"]
    rows = client.get("/api/v1/scans", headers={"Authorization": f"Bearer {tok}"}).json()
    match = [r for r in rows if r["id"] == scan["id"]]
    assert len(match) == 1 and match[0]["has_image"] is True


def test_image_unknown_id_404():
    tok = _auth()
    r = client.get("/api/v1/scans/doesnotexist/image", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 404


def test_gps_round_trip_and_validation():
    tok = _auth()
    h = {"Authorization": f"Bearer {tok}"}
    with open(IMG, "rb") as fh:
        scan = client.post(
            "/api/v1/scans",
            files={"file": ("s.png", fh, "image/png")},
            data={"scan_lat": "19.0760", "scan_lon": "72.8777"},
            headers=h,
        ).json()
    assert scan["scan_lat"] == 19.076 and scan["scan_lon"] == 72.8777
    det = client.get(f"/api/v1/scans/{scan['id']}", headers=h).json()
    assert det["scan_lat"] == 19.076 and det["scan_lon"] == 72.8777
    # Out-of-range coordinates are stored as nulls, never persisted raw.
    with open(IMG, "rb") as fh:
        bad = client.post(
            "/api/v1/scans",
            files={"file": ("s.png", fh, "image/png")},
            data={"scan_lat": "999", "scan_lon": "0"},
            headers=h,
        ).json()
    assert bad["scan_lat"] is None and bad["scan_lon"] is None


def test_image_requires_auth():
    r = client.get("/api/v1/scans/anything/image")
    assert r.status_code == 401
