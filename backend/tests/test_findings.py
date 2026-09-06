"""PATCH /scans/{id}/findings: per-finding officer attestation (no engine re-run)."""

import io

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.main import create_app

client = TestClient(create_app())


def _auth(username: str = "finduser") -> str:
    body = {"username": username, "password": "findpass123"}
    client.post("/api/v1/auth/register", json=body)
    return client.post("/api/v1/auth/login", json=body).json()["access_token"]


def _upload(tok: str) -> dict:
    img = Image.new("RGB", (900, 400), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 20), "Voodles with seasoning\nNet Qty: 60 g", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    r = client.post(
        "/api/v1/scans",
        files={"file": ("s.png", buf.getvalue(), "image/png")},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_attest_missing_mrp_flips_card_and_verdict():
    tok = _auth()
    h = {"Authorization": f"Bearer {tok}"}
    scan = _upload(tok)
    assert scan["verdict"] == "NON_COMPLIANT"
    before = {r["rule_id"]: r for r in scan["results"]}
    assert before["LMPC-6.1-mrp"]["status"] == "NOT_FOUND"
    r = client.patch(
        f"/api/v1/scans/{scan['id']}/findings",
        json={"rule_id": "LMPC-6.1-mrp", "observed": "Rs. 45 inclusive of all taxes", "present": True},
        headers=h,
    )
    assert r.status_code == 200, r.text
    by_id = {x["rule_id"]: x for x in r.json()["results"]}
    mrp = by_id["LMPC-6.1-mrp"]
    assert mrp["status"] == "PASS" and mrp["manual"] is True
    assert mrp["observed"] == "Rs. 45 inclusive of all taxes"
    assert "[officer-verified]" in mrp["message"]
    assert "inclusive of all taxes" in (mrp["expected"] or "")  # expected untouched
    det = client.get(f"/api/v1/scans/{scan['id']}", headers=h).json()
    assert det["corrected_by"] == "finduser"
    # Machine truth underneath is pristine (still NOT_FOUND in storage).
    import json

    from app.db.session import SessionLocal
    from app.models.tables import ScanRecord

    db = SessionLocal()
    rec = db.query(ScanRecord).filter(ScanRecord.id == scan["id"]).first()
    stored = {x["rule_id"]: x for x in json.loads(rec.results_json)}
    assert stored["LMPC-6.1-mrp"]["status"] == "NOT_FOUND"
    assert stored["LMPC-6.1-mrp"]["manual"] is False  # overlay lives apart, never rewrites machine rows
    db.close()


def test_uncheck_reverts_to_machine_truth():
    tok = _auth("finduser2")
    h = {"Authorization": f"Bearer {tok}"}
    scan = _upload(tok)
    client.patch(
        f"/api/v1/scans/{scan['id']}/findings",
        json={"rule_id": "LMPC-6.1-mrp", "present": True},
        headers=h,
    )
    r = client.patch(
        f"/api/v1/scans/{scan['id']}/findings", json={"rule_id": "LMPC-6.1-mrp", "present": False}, headers=h
    )
    assert r.status_code == 200, r.text
    by_id = {x["rule_id"]: x for x in r.json()["results"]}
    assert by_id["LMPC-6.1-mrp"]["status"] == "NOT_FOUND"
    assert by_id["LMPC-6.1-mrp"]["manual"] is False


def test_dispute_pass_marks_fail_and_guards():
    import uuid

    tok = _auth()
    h = {"Authorization": f"Bearer {tok}"}
    scan = _upload(tok)
    assert {r["rule_id"]: r for r in scan["results"]}["LMPC-6.1-netqty"]["status"] == "PASS"
    r = client.patch(
        f"/api/v1/scans/{scan['id']}/findings",
        json={"rule_id": "LMPC-6.1-netqty", "present": False},
        headers=h,
    )
    assert r.status_code == 200, r.text
    by_id = {x["rule_id"]: x for x in r.json()["results"]}
    assert by_id["LMPC-6.1-netqty"]["status"] == "FAIL"
    assert r.json()["verdict"] == "NON_COMPLIANT"
    # Rule 7 sizes are machine-only.
    r = client.patch(
        f"/api/v1/scans/{scan['id']}/findings",
        json={"rule_id": "LMPC-7.2-numeral", "present": True},
        headers=h,
    )
    assert r.status_code == 422
    r = client.patch(
        f"/api/v1/scans/{scan['id']}/findings", json={"rule_id": "LMPC-nope", "present": True}, headers=h
    )
    assert r.status_code == 422
    other = {"username": f"other{uuid.uuid4().hex[:8]}", "password": "otherpass123"}
    client.post("/api/v1/auth/register", json=other)
    tok2 = client.post("/api/v1/auth/login", json=other).json()["access_token"]
    r = client.patch(
        f"/api/v1/scans/{scan['id']}/findings",
        json={"rule_id": "LMPC-6.1-mrp", "present": True},
        headers={"Authorization": f"Bearer {tok2}"},
    )
    assert r.status_code == 403
