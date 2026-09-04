"""Barcode GTIN stage: real decodes on OFF packaging photos + honesty guards."""

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.barcode import decode_gtins, prefix_country

client = TestClient(create_app())
PACK = "../data/real/backs/off_8902080000227_pack.jpg"
PACK2 = "../data/real/backs/off_6111242100992_pack.jpg"


def _pack_bytes(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def test_decode_real_ean13_india():
    hits = decode_gtins(_pack_bytes(PACK))
    assert ("EAN-13", "8902080000227") in [(h["format"], h["text"]) for h in hits]
    assert prefix_country("8902080000227") == "India"


def test_decode_real_ean13_morocco():
    hits = decode_gtins(_pack_bytes(PACK2))
    assert ("EAN-13", "6111242100992") in [(h["format"], h["text"]) for h in hits]
    assert prefix_country("6111242100992") == "Morocco"


def test_garbage_bytes_yield_nothing():
    assert decode_gtins(b"not-an-image") == []


def test_unknown_prefix():
    assert prefix_country("9999999999999") == "Unknown"


def test_gtin_card_present_but_never_blocks_verdict():
    body = {"username": "barcodeuser", "password": "barcodepass123"}
    client.post("/api/v1/auth/register", json=body)
    tok = client.post("/api/v1/auth/login", json=body).json()["access_token"]
    with open(PACK, "rb") as fh:
        r = client.post(
            "/api/v1/scans",
            files={"file": ("pack.jpg", fh, "image/jpeg")},
            headers={"Authorization": f"Bearer {tok}"},
        )
    assert r.status_code == 200, r.text
    results = r.json()["results"]
    gtin = [x for x in results if x["rule_id"] == "LMPC-gtin"]
    assert len(gtin) == 1
    assert gtin[0]["status"] == "PASS"
    assert gtin[0]["severity"] == "info"
    assert "8902080000227" in (gtin[0]["observed"] or "")
