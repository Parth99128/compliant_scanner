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


def test_mrp_parens_form():
    d = extract_fields("MRP (\u20b9): 14.00 (incl. of all taxes)")
    assert d.mrp == 14.0


def test_mrp_spaced_thousands():
    d = extract_fields("MAXIMUM RETAIL PRICE : \u20b9 4 815.00\nMONTH & YEAR MANUFACTURED :")
    assert d.mrp == 4815.0
    # Amount must not bleed into following words.
    d2 = extract_fields("MRP Rs. 12O Inclusive of all taxes")
    assert d2.mrp == 120.0 and d2.mrp_includes_taxes


def test_net_anchor_ocr_variants_and_unit_typos():
    d = extract_fields("DET VOLUME : 500 Mla")
    assert (d.net_quantity_value, d.net_quantity_unit) == (500.0, "ml")
    d2 = extract_fields("Net Quantity: 1Unt")
    assert (d2.net_quantity_value, d2.net_quantity_unit) == (1.0, "unit")


def test_nutrition_table_blocks_bare_values():
    d = extract_fields("NUTRITIONAL INFORMATION\nSaturated Fat\n33g\nNet Qty: 250 ml")
    assert (d.net_quantity_value, d.net_quantity_unit) == (250.0, "ml")
    d2 = extract_fields("NUTRITIONAL INFORMATION\nSaturated Fat\n33g")
    assert d2.net_quantity_value is None


def test_day_month_year_dates():
    d = extract_fields("Pkd:30/AUG/26\nExp:14/OCT/26")
    assert d.mfg_date is not None and (d.mfg_date.year, d.mfg_date.month, d.mfg_date.day) == (2026, 8, 30)
    assert d.expiry_date is not None and (d.expiry_date.year, d.expiry_date.month, d.expiry_date.day) == (
        2026,
        10,
        14,
    )


def test_labeled_generic_and_lone_labels():
    d = extract_fields("Training Modes : Walking\nGeneric Name : Smart Watch\nColour : Gold")
    assert d.generic_name == "Smart Watch"
    d2 = extract_fields("CONTENTS\nNET QUANTITY\nMAXIMUM RETAIL PRICE")
    assert d2.generic_name is None


def test_care_double_at_and_origin_typo():
    d = extract_fields("Telephone Number 022-69089811 Email heip@@bortt.com")
    assert d.consumer_care and "heip" in d.consumer_care
    d2 = extract_fields("Country of Origin inca")
    assert d2.country_of_origin == "India" and not d2.is_imported


def test_mrp_backward_amount_before_keyword():
    d = extract_fields("10/08/26 09/08/27 \u20b950.00:\nMRP Rs. \u20b9(incl. of all taxes)")
    assert d.mrp == 50.0


def test_mrp_multiline_amount_next_line():
    d = extract_fields("MRP Rs.\nRs. 50.00\nUSP Rs. 1.00/g")
    assert d.mrp == 50.0


def test_mrp_multiline_poison_line_never_counts():
    d = extract_fields("MRP Rs.\nUSP Rs. 1.00/g")
    assert d.mrp is None


def test_exp_takes_later_date_on_paired_row():
    d = extract_fields("Mfg. Date, Best Before: 15/05/2024, 15/02/2025")
    assert d.mfg_date is not None and (d.mfg_date.year, d.mfg_date.month) == (2024, 5)
    assert d.expiry_date is not None and (d.expiry_date.year, d.expiry_date.month) == (2025, 2)


def test_genuine_bad_dates_still_detected():
    d = extract_fields("Mfg: 01/01/2025\nExp: 01/01/2024")
    assert d.mfg_date is not None and d.expiry_date is not None
    assert d.expiry_date <= d.mfg_date  # rule engine must still FAIL this


def test_mangled_day_falls_back_to_month():
    d = extract_fields("Packed On: 0/08/2026")
    assert d.mfg_date is not None and (d.mfg_date.year, d.mfg_date.month) == (2026, 8)


def test_generic_skips_lot_line():
    assert extract_fields("Lot No: F OH1").generic_name is None


def test_maker_block_keeps_full_address():
    d = extract_fields(
        "MARKETED BY:\nPatanjali Foods Limited\n"
        "Regd. Office: 616, Tulsiani Chambers, Nariman Point,\n"
        "Mumbai - 400021, Maharashtra\nLic. No.: 10015022004287"
    )
    assert d.manufacturer_name == "Patanjali Foods Limited"
    assert d.manufacturer_address and "400021" in d.manufacturer_address


def test_maker_ignores_as_per_reference():
    d = extract_fields(
        "Address as per Regd. Office, Toll Free No.: 18001804409,\n"
        "MARKETED BY:\nPatanjali Foods Limited\n"
        "Regd. Office: 616, Tulsiani Chambers, Nariman Point,\n"
        "Mumbai - 400021, Maharashtra"
    )
    assert d.manufacturer_name == "Patanjali Foods Limited"
    assert d.manufacturer_address and "400021" in d.manufacturer_address
    assert "Toll Free" not in (d.manufacturer_name or "")


def test_gazetteer_never_rewrites_exact_read():
    d = extract_fields("Mfd by Patanjali Foods Limited, Plot 1, Mumbai 400001")
    assert d.manufacturer_name == "Patanjali Foods Limited, Plot 1, Mumbai 400001"


def test_gazetteer_still_repairs_typos():
    d = extract_fields("Mfd by Hindustan Uniiever, Plot 1, Mumbai 400001")
    assert d.manufacturer_name and "Unilever" in d.manufacturer_name
