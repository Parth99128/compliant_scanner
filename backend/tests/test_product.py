"""Product identity storage, edit, search filters, stats overview."""

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())
IMG = "../data/samples/sample_00001.png"


def _auth() -> str:
    body = {"username": "produser", "password": "prodpass123"}
    client.post("/api/v1/auth/register", json=body)
    return client.post("/api/v1/auth/login", json=body).json()["access_token"]


def _upload(tok: str, **form) -> dict:
    with open(IMG, "rb") as fh:
        files = {"file": ("s.png", fh, "image/png")}
        r = client.post("/api/v1/scans", files=files, data=form, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text
    return r.json()


def _expected_generic() -> str:
    """Ground truth for the pinned fixture (tracks accept_phase1 regeneration)."""
    import json

    with open("../data/labels.jsonl", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if row.get("image") == "samples/sample_00001.png":
                return str(row["truth"]["generic_name"])
    raise AssertionError("fixture row samples/sample_00001.png missing from data/labels.jsonl")


def test_product_autofill_from_extraction():
    tok = _auth()
    scan = _upload(tok)
    assert scan["product_name"] == _expected_generic()
    assert scan["brand_name"]  # auto-filled maker line, never blank on synthetic labels


def test_product_override_at_upload_and_patch():
    tok = _auth()
    scan = _upload(tok, product_name="Custom Name", brand_name="Custom Brand", category="Snacks")
    assert scan["product_name"] == "Custom Name"
    assert scan["category"] == "Snacks"
    r = client.patch(
        f"/api/v1/scans/{scan['id']}/product",
        json={"product_name": "Fixed", "brand_name": "FixedCo", "category": "Biscuits"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["product_name"] == "Fixed"


def test_search_and_filters():
    tok = _auth()
    _upload(tok, product_name="UniqueSearchXYZ")
    h = {"Authorization": f"Bearer {tok}"}
    assert any(
        r["id"] for r in client.get("/api/v1/scans", params={"q": "UniqueSearchXYZ"}, headers=h).json()
    )
    assert client.get("/api/v1/scans", params={"q": "NoSuchThingZZZ"}, headers=h).json() == []
    verdict = client.get("/api/v1/scans", headers=h).json()[0]["verdict"]
    rows = client.get("/api/v1/scans", params={"verdict": verdict}, headers=h).json()
    assert rows and all(r["verdict"] == verdict for r in rows)


def test_stats_overview_shape():
    tok = _auth()
    _upload(tok)
    r = client.get("/api/v1/stats/overview", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 1
    assert isinstance(body["by_verdict"], dict)
    assert isinstance(body["top_failed_rules"], list)
    assert isinstance(body["by_day"], list)
    assert isinstance(body["recent"], list)
