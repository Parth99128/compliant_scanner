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


def test_spelled_out_mrp_and_unit_quantity():
    text = (
        "Maximum Retail Price : ₹ 12,499.00 (Inclusive of all taxes)\n"
        "Net Quantity :  1 Unit    Country of Origin : India"
    )
    d = extract_fields(text)
    assert d.mrp == 12499.0 and d.mrp_includes_taxes
    assert (d.net_quantity_value, d.net_quantity_unit) == (1, "unit")
    assert d.country_of_origin == "India" and not d.is_imported


def test_unit_quantity_is_number_class_for_rule7():
    import dataclasses

    from app.services.rule_engine import Status, check_net_quantity, check_numeral_height, evaluate_compliance

    d = extract_fields("Maximum Retail Price : ₹ 12,499.00 (Inclusive of all taxes)\nNet Quantity :  1 Unit")
    assert check_net_quantity(d).passed  # standard unit, no FAIL
    # Number-class needs panel area: honest NOT_ASSESSABLE without it...
    assert check_numeral_height(d).status == Status.NOT_ASSESSABLE
    # ...and a real tier check once measured (600cm² -> Table-II needs 4mm).
    d2 = dataclasses.replace(d, panel_area_cm2=600.0, min_numeral_height_mm=4.0)
    assert check_numeral_height(d2).passed
    rep = evaluate_compliance(d)
    assert not any(r.rule_id in ("LMPC-6.1-mrp", "LMPC-6.1-netqty") and not r.passed for r in rep.results)


def test_month_year_manufacturing_dates():
    assert extract_fields("Mfg: 05/2024").mfg_date is not None
    assert extract_fields("Mfg: 05/2024").mfg_date.month == 5
    assert extract_fields("Mfg Date: May-24").mfg_date is not None
    assert extract_fields("Mfg: JAN/2025").mfg_date.month == 1
    d = extract_fields("Mfg: 05/24 Exp: 06/26")
    assert (d.mfg_date.month, d.mfg_date.year) == (5, 2024)
    assert (d.expiry_date.month, d.expiry_date.year) == (6, 2026)
    # Bare MM/YYYY (anchor OCR-dropped) constrained to real years.
    d2 = extract_fields("Wheat Biscuits\n05/2024\n06/2026")
    assert d2.mfg_date is not None and d2.expiry_date is not None
    # Full dates still win over everything.
    d3 = extract_fields("Mfg: 01/01/2025 Exp: 01/01/2026")
    assert (d3.mfg_date.day, d3.expiry_date.day) == (1, 1)


def test_manufacture_without_d_anchor():
    d = extract_fields("Month and Year of Manufacture : December 2025")
    assert d.mfg_date is not None and (d.mfg_date.month, d.mfg_date.year) == (12, 2025)


def test_percent_misread_rupee_mrp():
    d = extract_fields("Maximum Retail Price : % 12,499.00 (Inclusive of all taxes)")
    assert d.mrp == 12499.0 and d.mrp_includes_taxes


def test_ongin_typo_origin_and_second_chance_mfg():
    d = extract_fields("Country of Ongin : India")
    assert d.country_of_origin == "India" and not d.is_imported
    d2 = extract_fields("Manuiacture : December 2025")
    assert d2.mfg_date is not None and d2.mfg_date.month == 12


def test_ner_care_span_needs_contact(monkeypatch):
    import app.services.extraction as ex
    from app.services.rule_engine import ProductDeclaration

    def _fake_nlp(span):
        class Ent:
            label_ = "CARE"
            text = span

        class Doc:
            def __init__(self):
                self.ents = [Ent()]

        return lambda _text: Doc()

    monkeypatch.setattr(ex, "_ner_model", lambda: _fake_nlp("Customer Care Details The"))
    assert ex._ner_refine("Customer Care Details The", ProductDeclaration()).consumer_care is None
    monkeypatch.setattr(ex, "_ner_model", lambda: _fake_nlp("Customer Care care@x.in 1800-111"))
    got = ex._ner_refine("x", ProductDeclaration()).consumer_care
    assert got == "Customer Care care@x.in 1800-111"


def test_generic_skips_declaration_lines():
    d = extract_fields(
        "Maximum Retail Price : Rs. 12499 Inclusive of all taxes\n"
        "Net Quantity :  1 Unit\n"
        "Smart Watch with Charger"
    )
    assert d.generic_name == "Smart Watch with Charger"


def test_care_contact_on_next_line():
    d = extract_fields("Customer Care Details\ncare@acme.in 1800-123-456")
    assert d.consumer_care is not None and "care@acme.in" in d.consumer_care
    d2 = extract_fields("Toll Free\n1800-123-456")
    assert d2.consumer_care is not None
