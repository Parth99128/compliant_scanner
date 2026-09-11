"""OFF cross-check: public-record second opinion over barcode scans."""

from app.services import off_lookup
from app.services.off_lookup import cross_check_warning, lookup_by_barcode


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        import json

        return json.dumps(self._payload).encode()


def test_lookup_success(monkeypatch):
    monkeypatch.setattr(
        off_lookup.urllib.request,
        "urlopen",
        lambda req, timeout=8.0: _Resp({"product": {"product_name": "Sting", "quantity": "250 ml"}}),
    )
    rec = lookup_by_barcode("8902080000227")
    assert rec == {"code": "8902080000227", "name": "Sting", "quantity": "250 ml"}


def test_lookup_failure_is_none(monkeypatch):
    def boom(req, timeout=8.0):
        raise OSError("no network")

    monkeypatch.setattr(off_lookup.urllib.request, "urlopen", boom)
    assert lookup_by_barcode("8902080000227") is None
    assert lookup_by_barcode("123") is None  # too short: not even attempted
    assert lookup_by_barcode("") is None


def test_cross_check_warning():
    rec = {"code": "8902080000227", "name": "Sting", "quantity": "250 ml"}
    w = cross_check_warning(rec, "Sting Energy", "250 ml")
    assert w and "matches" in w and "8902080000227" in w
    w2 = cross_check_warning(rec, "Cola", "500 ml")
    assert w2 and "DIFFERS" in w2
    assert cross_check_warning(None, "x", "y") is None
    assert cross_check_warning({"code": "1", "name": None, "quantity": None}, None, None) is None
