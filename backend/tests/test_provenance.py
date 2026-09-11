"""Phase D provenance: every field value knows how it was obtained."""

from app.services.extraction import (
    apply_confidence_sources,
    extract_fields,
)
from app.services.rule_engine import ProductDeclaration


def test_regex_hits_marked_read():
    d = extract_fields(
        "Acme Foods, Plot 1, Mumbai 400001\n"
        "Atta\n"
        "Net Qty: 500 g\n"
        "MRP Rs. 120 Inclusive of all taxes\n"
        "Mfg: 01/01/2025\n"
        "care@acme.in 1800-111-222"
    )
    assert d.field_sources.get("mrp") == "read"
    assert d.field_sources.get("net_quantity_value") == "read"
    assert d.field_sources.get("mfg_date") == "read"
    assert d.field_sources.get("consumer_care") == "read"
    assert d.field_sources.get("manufacturer_name") == "read"


def test_gazetteer_typo_marked_inferred():
    d = extract_fields("Mfd by Hindustan Uniiever, Plot 1, Mumbai 400001")
    assert d.manufacturer_name and "Unilever" in d.manufacturer_name
    assert d.field_sources.get("manufacturer_name") == "inferred"


def test_layout_fill_marked_inferred(monkeypatch):
    import app.services.extraction as E
    from app.services.layout import VLine

    rows = [
        VLine("MRP Rs.", 0, 0, 10, 10, 90.0),
        VLine("Rs. 50.00", 0, 20, 10, 30, 90.0),
    ]
    monkeypatch.setattr(E, "build_lines", lambda boxes: rows)
    boxes = [{"text": "x", "x": 0, "y": 0, "w": 1, "h": 1, "confidence": 90}]
    d = E.extract_fields_with_layout("MRP Rs.\nSee below", boxes)
    assert d.mrp == 50.0
    assert d.field_sources.get("mrp") == "inferred"


def test_confidence_downgrade():
    d = extract_fields("MRP Rs. 120\nNet Qty: 500 g")
    assert d.field_sources.get("mrp") == "read"
    weak = apply_confidence_sources(d, 45.0)
    assert weak.field_sources.get("mrp") == "uncertain"
    assert weak.field_sources.get("net_quantity_value") == "uncertain"
    assert apply_confidence_sources(d, 90.0).field_sources.get("mrp") == "read"
    assert apply_confidence_sources(d, None).field_sources.get("mrp") == "read"


def test_llm_fill_gap_only_and_marked():
    from app.api.v1.routes import _apply_llm_fill

    base = ProductDeclaration(mrp=120.0, field_sources={"mrp": "read"})
    out, filled = _apply_llm_fill(
        base,
        {"mrp": 999.0, "consumer_care": "care@x.in 1800-111-222", "generic_name": "For Consumer Pack"},
        "CARE care@x.in 1800-111-222",
    )
    assert out.mrp == 120.0  # local hit wins, never overwritten
    assert out.consumer_care == "care@x.in 1800-111-222"
    assert out.field_sources.get("consumer_care") == "ai_assist"
    assert "generic_name" not in filled  # heading rejected
    assert filled == ["consumer_care"]


def test_llm_fill_rejects_ungrounded_money():
    from app.api.v1.routes import _apply_llm_fill

    base = ProductDeclaration()
    out, filled = _apply_llm_fill(base, {"mrp": 96.0}, "MRP Rs 95")
    assert out.mrp is None and filled == []


def test_snapshot_round_trip_preserves_sources():
    from app.api.v1.routes import _decl_from_snapshot, _decl_snapshot

    d = extract_fields("MRP Rs. 120\nNet Qty: 500 g")
    back = _decl_from_snapshot(_decl_snapshot(d))
    assert back.field_sources == d.field_sources
    assert back.mrp == 120.0
