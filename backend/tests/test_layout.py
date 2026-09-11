"""Layout-aware extraction: visual rows rescue what OCR line-breaks break."""

from app.services.extraction import extract_fields, extract_fields_with_layout
from app.services.layout import build_lines, find_anchor, rows_below


def _box(text, x, y, w=60, h=20, c=80.0):
    return {"text": text, "x": x, "y": y, "w": w, "h": h, "confidence": c}


def test_build_lines_clusters_rows():
    boxes = [
        _box("MRP", 10, 10),
        _box("Rs.", 70, 12),
        _box("50.00", 15, 45),
        _box("other", 200, 12),
    ]
    lines = build_lines(boxes)
    assert [ln.text for ln in lines] == ["MRP Rs. other", "50.00"] or len(lines) == 2
    assert lines[0].y0 <= lines[1].y0


def test_build_lines_never_raises():
    assert build_lines(None) == []
    assert build_lines([{"junk": 1}, None, {"text": "", "x": 0, "y": 0, "w": 0, "h": 0}]) == []
    assert find_anchor([], "x") == -1
    assert rows_below([], 0) == []


def test_mrp_rescued_from_row_below():
    boxes = [_box("MRP", 10, 10), _box("Rs.", 70, 10), _box("50.00", 12, 45)]
    d = extract_fields_with_layout("MRP Rs.\nRs. 50.00", boxes)
    assert d.mrp == 50.0


def test_mrp_poison_row_below_rejected():
    boxes = [_box("MRP", 10, 10), _box("USP", 12, 45), _box("1.00/g", 70, 45)]
    d = extract_fields_with_layout("MRP Rs.\nUSP Rs. 1.00/g", boxes)
    assert d.mrp is None


def test_date_pair_on_shared_row():
    boxes = [
        _box("Packed", 10, 10),
        _box("On:", 80, 10),
        _box("07/08/26", 140, 10),
        _box("09/08/27", 230, 12),
    ]
    d = extract_fields_with_layout("Packed On: 07/08/26 09/08/27", boxes)
    assert d.mfg_date is not None and (d.mfg_date.year, d.mfg_date.month) == (2026, 8)
    assert d.expiry_date is not None and (d.expiry_date.year, d.expiry_date.month) == (2027, 8)


def test_maker_block_in_visual_order():
    boxes = [
        _box("MARKETED", 10, 10),
        _box("BY:", 110, 10),
        _box("Acme", 10, 45),
        _box("Foods", 70, 45),
        _box("Plot", 10, 80),
        _box("5,", 60, 80),
        _box("Pune", 90, 80),
        _box("411026", 150, 80),
    ]
    text = "MARKETED BY:\nAcme Foods\nPlot 5, Pune 411026"
    d = extract_fields_with_layout(text, boxes)
    assert d.manufacturer_name and "Acme" in d.manufacturer_name
    assert d.manufacturer_address and "411026" in d.manufacturer_address


def test_no_boxes_matches_flat():
    text = "MRP Rs. 120 Inclusive of all taxes\nNet Qty: 500 g"
    a = extract_fields(text)
    b = extract_fields_with_layout(text, None)
    assert (a.mrp, a.net_quantity_value) == (b.mrp, b.net_quantity_value) == (120.0, 500.0)
