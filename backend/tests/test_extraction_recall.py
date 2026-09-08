"""Extraction recall + specificity on real-world OCR shapes (Phase B/C).

Pure text in/out (no OCR): nutrition tables, glued barcode digits, mangled
anchors, bare contacts, storage fragments. Guards the eval_real.py gains.
"""

from app.services.extraction import extract_fields


def test_qty_prefers_standalone_over_nutrition():
    d = extract_fields("QUANTITY OF SUGAR ADDED 6.6g 100g\n72 mg/serve\nNET QUANTITY: 250 ml")
    assert (d.net_quantity_value, d.net_quantity_unit) == (250.0, "ml")


def test_qty_barcode_glue_repair():
    d = extract_fields("MANUFACTURE8 90720 0022250 ml")
    assert (d.net_quantity_value, d.net_quantity_unit) == (250.0, "ml")


def test_qty_nutrition_table_ignored():
    d = extract_fields("Valeurs nutritionnelles pour 100g\nEnergie 97 kcal")
    assert d.net_quantity_value is None


def test_qty_unit_typo_mie():
    d = extract_fields("Bo 2 250 mie")
    assert (d.net_quantity_value, d.net_quantity_unit) == (250.0, "ml")


def test_mfg_glued_date_recovered():
    d = extract_fields("Mita: 2309/2025 Expr 14042026")
    assert d.mfg_date is not None and (d.mfg_date.year, d.mfg_date.month) == (2025, 9)


def test_bare_short_dates_rejected():
    d = extract_fields("values 8/9/10.11\nratio 3.4.4,5.6")
    assert d.mfg_date is None and d.expiry_date is None


def test_barcode_digits_not_manufacturer():
    d = extract_fields("STORE IN A COOL, DRY PLACE 8901719 134845\nDo not LITTER")
    assert d.manufacturer_name is None


def test_manufacturer_anchor_block():
    d = extract_fields(
        "MANUFACTURED BY: Acme Foods\nPlot 5, MIDC Enclave, Pune 411026\nCustomer Care: care@acme.in"
    )
    assert d.manufacturer_name == "Acme Foods"
    assert d.manufacturer_address and "Enclave" in d.manufacturer_address


def test_generic_skips_storage_line():
    d = extract_fields("STORE IN A COOL, DRY PLACE\nDo not LITTER")
    assert d.generic_name is None


def test_generic_skips_measurement_line():
    d = extract_fields("Bo 2 250 ml")
    assert d.generic_name is None


def test_care_bare_tollfree():
    d = extract_fields("Call 1800 22 4020 for help")
    assert d.consumer_care and "1800" in d.consumer_care


def test_care_service_anchor():
    d = extract_fields("CONTACT CUSTOMER SERVICE MANAGER AT P.O. BOX 27\ncare@acme.in")
    assert d.consumer_care and "care@acme.in" in d.consumer_care


def test_rupee_needs_price_cue():
    assert extract_fields("Fromage sucré \u20b9100 pour").mrp is None
    d = extract_fields("MRP \u20b9 120 inclusive of all taxes")
    assert d.mrp == 120.0 and d.mrp_includes_taxes
