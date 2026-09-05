"""OCR post-fix accuracy: mangled months, units, MRP digits, date runs — plus guards."""

from app.services.extraction import extract_fields, normalize_ocr_text


def test_month_repair_feeds_date_parse():
    d = extract_fields("Wheat Biscuits\nMfg: JANUARV 2025\nExp: FEBRUARV 2026")
    assert d.mfg_date is not None and (d.mfg_date.year, d.mfg_date.month) == (2025, 1)
    assert d.expiry_date is not None and (d.expiry_date.year, d.expiry_date.month) == (2026, 2)


def test_month_guard_leaves_real_words_alone():
    assert "BATCH 2025" in normalize_ocr_text("BATCH 2025")
    d = extract_fields("BATCH 2025\nMfg: March 2025")
    assert d.mfg_date is not None and d.mfg_date.month == 3


def test_qty_unit_repair_only_on_netqty_lines():
    d = extract_fields("Wheat Biscuits\nNet Qty: 500 9")
    assert (d.net_quantity_value, d.net_quantity_unit) == (500, "g")
    d2 = extract_fields("Pack of 9 tablets\nNet Qty: 100 g")
    assert (d2.net_quantity_value, d2.net_quantity_unit) == (100, "g")
    assert "Pack of g" not in normalize_ocr_text("Pack of 9 tablets")


def test_mrp_digit_repair():
    d = extract_fields("MRP Rs. 12O Inclusive of all taxes")
    assert d.mrp == 120.0 and d.mrp_includes_taxes
    # Too few digits -> must not fabricate a price.
    d2 = extract_fields("MRP I Inclusive of all taxes")
    assert d2.mrp is None


def test_date_token_repair():
    d = extract_fields("Mfg: 0l/01/2025 Exp: 0l/01/2026")
    assert d.mfg_date is not None and (d.mfg_date.day, d.mfg_date.month) == (1, 1)
    assert d.expiry_date is not None and d.expiry_date.year == 2026


def test_anchor_typos_meg_exf():
    d = extract_fields("MEG: 01/01/2025\nEXF: 01/01/2026")
    assert d.mfg_date is not None and d.expiry_date is not None


def test_normalize_idempotent_and_safe():
    raw = "MRP Rs. 99 Inclusive of all taxes\nNet Qty: 1 kg\nMfg: 02/03/2025"
    assert normalize_ocr_text(normalize_ocr_text(raw)) == normalize_ocr_text(raw)
    assert normalize_ocr_text("") == ""
    d = extract_fields(raw)
    assert d.mrp == 99.0 and d.net_quantity_unit == "kg" and d.mfg_date is not None
