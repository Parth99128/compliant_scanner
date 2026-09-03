from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert "X-Request-ID" in r.headers


def test_validate_endpoint():
    body = {
        "manufacturer_name": "Acme",
        "manufacturer_address": "Mumbai",
        "generic_name": "Biscuits",
        "net_quantity_value": 100,
        "net_quantity_unit": "g",
        "mrp": 50,
        "mrp_includes_taxes": True,
        "mfg_date": "2025-01-01",
        "consumer_care": "care@acme.in",
    }
    r = client.post("/api/v1/validate", json=body)
    assert r.status_code == 200
    assert "compliant" in r.json()


def test_validate_rejects_bad_input():
    r = client.post("/api/v1/validate", json={"net_quantity_value": -5})
    assert r.status_code == 422


def test_scan_requires_auth():
    r = client.post("/api/v1/scans")
    assert r.status_code in (401, 422)


def test_auth_flow_and_scan_validation():
    u = {"username": "tester1", "password": "secret123"}
    client.post("/api/v1/auth/register", json=u)
    tok = client.post("/api/v1/auth/login", json=u).json()["access_token"]
    # unsupported file type rejected
    r = client.post(
        "/api/v1/scans",
        files={"file": ("x.txt", b"hi", "text/plain")},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 415
