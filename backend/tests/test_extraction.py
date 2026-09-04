from app.services.extraction import extract_fields
from app.services.vision import estimate_ppm, font_height_mm, preprocess_for_ocr


def test_extract_mrp_netqty_dates():
    text = """Wheat Biscuits
Acme Foods, Plot 5, Mumbai 400001
Net Qty: 500 g
MRP Rs. 120.00 Inclusive of all taxes
Mfg: 01/01/2025 Exp: 01/01/2026
Customer Care: care@acme.in 1800-123-456
Country of Origin: India"""
    d = extract_fields(text)
    assert d.mrp == 120.0 and d.mrp_includes_taxes
    assert d.net_quantity_value == 500 and d.net_quantity_unit == "g"
    assert d.mfg_date is not None and d.consumer_care is not None


def test_extract_empty_and_corrupted():
    d = extract_fields("")
    assert d.mrp is None and d.net_quantity_value is None
    d2 = extract_fields("!!! ### ??? \n\n  ")
    assert d2.generic_name is None or isinstance(d2.generic_name, str)


def test_tax_phrase_tolerates_punctuation():
    d = extract_fields("MRP Rs. 99 (incl. of all taxes)")
    assert d.mrp == 99.0 and d.mrp_includes_taxes
    d2 = extract_fields("MRP Rs. 99 INCLUSIVE OF ALL TAXES")
    assert d2.mrp_includes_taxes


def test_generic_skips_numeric_garbage_first_line():
    d = extract_fields("1\n2\n3\nInstant Noodles with seasoning\nNet Qty: 60 g")
    assert d.generic_name == "Instant Noodles with seasoning"
    d2 = extract_fields("7\n!!\n")
    assert d2.generic_name is None


def test_ppm_math():
    assert estimate_ppm(200, 20) == 10.0
    assert font_height_mm(30, 10.0) == 3.0
    assert estimate_ppm(0, 0) is None
    assert font_height_mm(10, None) is None


def test_preprocess_fallback():
    assert preprocess_for_ocr(b"not-an-image") == b"not-an-image"
