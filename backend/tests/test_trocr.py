"""TrOCR repair crew: validated row re-reads, geometry-preserving splice."""

from app.services.ocr import OcrResult, WordBox, _apply_row_repairs
from app.services.trocr import _row_parses, is_enabled, pick_weak_lines


def _boxes(*rows):
    out = []
    y = 10.0
    for words in rows:
        x = 10.0
        for text, conf in words:
            out.append(WordBox(text=text, x=x, y=y, w=50.0, h=16.0, confidence=conf))
            x += 60.0
        y += 30.0
    return out


def test_row_parses_gate():
    assert _row_parses("MRP Rs. 120") is True
    assert _row_parses("Packed On 07/08/26") is True
    assert _row_parses("Net Qty 500 g") is True
    assert _row_parses("hello world") is False
    assert _row_parses("A COOL PLACE") is False
    assert _row_parses("") is False


def test_pick_weak_lines():
    boxes = _boxes([("MRP", 95.0), ("Rs.", 90.0)], [("1O0", 20.0), ("g", 10.0)])
    idx = pick_weak_lines(boxes)
    assert set(idx) == {2, 3}
    assert pick_weak_lines(_boxes([("a", 99.0)])) == []
    assert pick_weak_lines(None) == []
    assert pick_weak_lines("garbage") == []


def test_apply_row_repairs_splice():
    boxes = _boxes([("MRP", 95.0), ("Rs.", 90.0)], [("1O0", 20.0)])
    r = OcrResult(text="MRP Rs.\n1O0", engine="tesseract", confidence=55.0, boxes=boxes)
    union = {"text": "100", "x": 10.0, "y": 40.0, "w": 110.0, "h": 16.0, "confidence": 20.0}
    out = _apply_row_repairs(r, [([2], union, "100")])
    assert out.engine == "tesseract+trocr"
    assert "100" in out.text and "1O0" not in out.text
    assert "\n" in out.text  # line structure preserved
    assert len(out.boxes) == 3  # 2 kept + 1 union
    assert out.confidence == 55.0  # never revised upward silently


def test_apply_row_repairs_mismatch_safe():
    boxes = _boxes([("a", 50.0)])
    r = OcrResult(text="a b c", engine="tesseract", confidence=10.0, boxes=boxes)
    assert _apply_row_repairs(r, [([5], {}, "x")]).text == "a b c"
    assert _apply_row_repairs(r, []).engine == "tesseract"


def test_disabled_by_default(monkeypatch):
    import app.services.trocr as trocr_mod

    monkeypatch.setattr(trocr_mod, "get_settings", lambda: _Off())
    assert is_enabled() is False
    assert trocr_mod.repair_rows(b"junk", []) == []


class _Off:
    trocr_enabled = "false"
    trocr_model = ""
