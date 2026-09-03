"""Phase 4 acceptance: upload -> process -> save -> history -> PDF report."""

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())
IMG = "../data/samples/sample_00.png"


def _auth(username: str, role: str = "officer") -> str:
    body = {"username": username, "password": "secret123", "role": role}
    client.post("/api/v1/auth/register", json=body)
    r = client.post("/api/v1/auth/login", json=body)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _img_bytes() -> bytes:
    try:
        return open(IMG, "rb").read()
    except FileNotFoundError:
        import io

        from PIL import Image, ImageDraw

        img = Image.new("RGB", (900, 400), "white")
        d = ImageDraw.Draw(img)
        d.text((20, 20), "Wheat Biscuits\nNet Qty: 500 g\nMRP Rs. 120 Inclusive of all taxes", fill="black")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


def test_full_round_trip():
    tok = _auth("officer_rt")
    files = {"file": ("label.png", _img_bytes(), "image/png")}
    r = client.post(
        "/api/v1/scans", files=files, data={"ppm": "10"}, headers={"Authorization": f"Bearer {tok}"}
    )
    assert r.status_code == 200, r.text
    scan_id = r.json()["id"]
    assert r.json()["font_height_mm"] is not None  # calibration data flowed into rules

    r = client.get("/api/v1/scans", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200 and any(s["id"] == scan_id for s in r.json())

    r = client.get(f"/api/v1/scans/{scan_id}", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200 and len(r.json()["results"]) == 10
    assert r.json()["status"] == "pending_review"  # human-in-the-loop default
    sevens = [c for c in r.json()["results"] if c["rule_id"].startswith("LMPC-7")]
    assert sevens and all(c["citation_verified"] for c in sevens)

    # Report is gated until review (addendum §F).
    r = client.get(f"/api/v1/scans/{scan_id}/report", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 409
    r = client.post(
        f"/api/v1/scans/{scan_id}/review",
        json={"decision": "confirm", "notes": "verified on screen"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200 and r.json()["status"] == "final"
    assert r.json()["reviewed_by"] == "officer_rt"

    r = client.get(f"/api/v1/scans/{scan_id}/report", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_ownership_and_roles():
    tok_a = _auth("owner_a")
    tok_b = _auth("owner_b")
    files = {"file": ("label.png", _img_bytes(), "image/png")}
    scan_id = client.post("/api/v1/scans", files=files, headers={"Authorization": f"Bearer {tok_a}"}).json()[
        "id"
    ]
    r = client.get(f"/api/v1/scans/{scan_id}", headers={"Authorization": f"Bearer {tok_b}"})
    assert r.status_code == 403
    tok_admin = _auth("admin_x", role="admin")
    r = client.get(f"/api/v1/scans/{scan_id}", headers={"Authorization": f"Bearer {tok_admin}"})
    assert r.status_code == 200


def test_override_requires_admin_and_notes():
    tok = _auth("officer_ov")
    tok_admin = _auth("admin_ov", role="admin")
    files = {"file": ("label.png", _img_bytes(), "image/png")}
    scan_id = client.post("/api/v1/scans", files=files, headers={"Authorization": f"Bearer {tok}"}).json()[
        "id"
    ]
    # Officer cannot override; admin cannot override without notes.
    r = client.post(
        f"/api/v1/scans/{scan_id}/review",
        json={"decision": "override", "notes": "looks fine"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 403
    r = client.post(
        f"/api/v1/scans/{scan_id}/review",
        json={"decision": "override", "notes": ""},
        headers={"Authorization": f"Bearer {tok_admin}"},
    )
    assert r.status_code == 422
    r = client.post(
        f"/api/v1/scans/{scan_id}/review",
        json={"decision": "override", "notes": "re-measured on package: 4mm"},
        headers={"Authorization": f"Bearer {tok_admin}"},
    )
    assert r.status_code == 200 and r.json()["status"] == "final"
    assert r.json()["reviewed_by"] == "admin_ov"
