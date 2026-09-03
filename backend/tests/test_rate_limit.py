from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def test_register_rate_limited():
    codes = set()
    for i in range(12):
        r = client.post("/api/v1/auth/register", json={"username": f"rl_{i}", "password": "secret123"})
        codes.add(r.status_code)
    assert 429 in codes  # 10/minute bucket trips on the 11th+ request
