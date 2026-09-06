"""PATCH /scans/{id}/fields: officer correction of OCR-mangled Rule 6 values."""

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def _auth(username: str = "fielduser") -> str:
    body = {"username": username, "password": "fieldpass123"}
    client.post("/api/v1/auth/register", json=body)
    return client.post("/api/v1/auth/login", json=body).json()["access_token"]


def _upload(tok: str) -> dict:
    import io

    from PIL import Image, ImageDraw

    img = Image.new("RGB", (900, 400), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 20), "Voodles with seasoning\nNet Qty: 60 g\nMRP Rs. 14", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    r = client.post(
        "/api/v1/scans",
        files={"file": ("s.png", buf.getvalue(), "image/png")},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_correct_typo_updates_verdict_and_audit():
    tok = _auth()
    h = {"Authorization": f"Bearer {tok}"}
    scan = _upload(tok)
    before = {r["rule_id"]: r for r in scan["results"]}
    # Whatever OCR made of it, it is present but not the officer's correction.
    assert before["LMPC-6.1-generic"]["observed"]
    assert before["LMPC-6.1-generic"]["observed"] != "Instant Noodles with seasoning"
    fixed = client.patch(
        f"/api/v1/scans/{scan['id']}/fields",
        json={"generic_name": "Instant Noodles with seasoning"},
        headers=h,
    )
    assert fixed.status_code == 200, fixed.text
    body = fixed.json()
    assert body["product_name"] == "Instant Noodles with seasoning"
    assert body["corrected_by"] == "fielduser" and body["corrected_at"]
    assert body["declaration"]["generic_name"] == "Instant Noodles with seasoning"
    by_id = {r["rule_id"]: r for r in body["results"]}
    assert by_id["LMPC-6.1-generic"]["observed"] == "Instant Noodles with seasoning"


def test_measurements_survive_correction():
    tok = _auth("fielduser2")
    h = {"Authorization": f"Bearer {tok}"}
    scan = _upload(tok)
    seven_before = {r["rule_id"]: r["status"] for r in scan["results"] if r["rule_id"].startswith("LMPC-7")}
    fixed = client.patch(f"/api/v1/scans/{scan['id']}/fields", json={"generic_name": "Noodles"}, headers=h)
    assert fixed.status_code == 200, fixed.text
    seven_after = {
        r["rule_id"]: r["status"] for r in fixed.json()["results"] if r["rule_id"].startswith("LMPC-7")
    }
    assert seven_after == seven_before  # machine-measured sizes never edited


def test_fields_guards():
    import uuid

    tok = _auth()
    h = {"Authorization": f"Bearer {tok}"}
    scan = _upload(tok)
    # Nothing editable sent (Rule 7 sizes are machine-only).
    r = client.patch(f"/api/v1/scans/{scan['id']}/fields", json={"min_numeral_height_mm": 9.9}, headers=h)
    assert r.status_code == 422
    # Unknown scan / other officer.
    assert client.patch(
        "/api/v1/scans/doesnotexist/fields", json={"generic_name": "x"}, headers=h
    ).status_code in (
        404,
        403,
    )
    other = {"username": f"other{uuid.uuid4().hex[:8]}", "password": "otherpass123"}
    client.post("/api/v1/auth/register", json=other)
    tok2 = client.post("/api/v1/auth/login", json=other).json()["access_token"]
    r = client.patch(
        f"/api/v1/scans/{scan['id']}/fields",
        json={"generic_name": "x"},
        headers={"Authorization": f"Bearer {tok2}"},
    )
    assert r.status_code == 403
