from datetime import date

from app.services.rule_engine import ProductDeclaration, evaluate_compliance


def good() -> ProductDeclaration:
    return ProductDeclaration(
        manufacturer_name="Acme Foods, Plot 1, Mumbai 400001",
        manufacturer_address="Plot 1, Mumbai 400001",
        generic_name="Wheat Biscuits",
        net_quantity_value=500,
        net_quantity_unit="g",
        mrp=120.0,
        mrp_includes_taxes=True,
        mfg_date=date(2025, 1, 1),
        expiry_date=date(2026, 1, 1),
        consumer_care="care@acme.in, 1800-123-456",
        country_of_origin="India",
        min_font_height_mm=3.0,
        min_letter_height_mm=3.0,
        min_width_to_height_ratio=0.5,
    )


def test_compliant_package():
    assert evaluate_compliance(good()).compliant


def test_missing_mrp_and_taxes():
    d = good()
    import dataclasses

    d = dataclasses.replace(d, mrp=None, mrp_includes_taxes=False)
    rep = evaluate_compliance(d)
    assert not rep.compliant
    assert any(r.rule_id == "LMPC-6.1-mrp" and not r.passed for r in rep.results)


def test_bad_dates_and_origin():
    import dataclasses

    d = dataclasses.replace(good(), expiry_date=date(2024, 1, 1), is_imported=True, country_of_origin=None)
    rep = evaluate_compliance(d)
    assert not rep.compliant
    assert any("Expiry" in r.message for r in rep.failures)


def test_font_height_rule():
    import dataclasses

    d = dataclasses.replace(good(), min_font_height_mm=1.0)  # 500g needs 2mm (Table-I)
    rep = evaluate_compliance(d)
    assert any(r.rule_id == "LMPC-7.2-numeral" and not r.passed for r in rep.results)


def test_missing_fields_edge():
    rep = evaluate_compliance(ProductDeclaration())
    assert not rep.compliant
    assert len(rep.failures) >= 5


def test_table1_boundaries():

    from app.services.rule_engine import check_numeral_height

    cases = [
        # (qty, unit, height, embossed, expected_pass)
        (200, "g", 1.0, False, True),  # tier 1 ceiling
        (200, "g", 0.9, False, False),
        (201, "g", 2.0, False, True),  # tier 2 floor
        (201, "g", 1.9, False, False),
        (500, "g", 2.0, False, True),  # tier 2 ceiling
        (501, "g", 4.0, False, True),  # tier 3 floor
        (501, "g", 3.9, False, False),
        (0.3, "kg", 2.0, False, True),  # 300g via kg normalization
        (200, "ml", 2.0, True, True),  # embossed tier 1 needs 2mm
        (200, "ml", 1.9, True, False),
        (600, "g", 6.0, True, True),  # embossed tier 3 needs 6mm
        (600, "g", 5.9, True, False),
    ]
    for qty, unit, height, embossed, expected in cases:
        d = ProductDeclaration(
            net_quantity_value=qty,
            net_quantity_unit=unit,
            min_numeral_height_mm=height,
            is_embossed=embossed,
        )
        r = check_numeral_height(d)
        assert r.passed == expected, f"{qty}{unit} h={height} emb={embossed}: {r.message}"
        assert r.citation_verified and "pp. 8-9" in r.source_ref


def test_table2_panel_area():
    from app.services.rule_engine import check_numeral_height

    d = ProductDeclaration(
        net_quantity_value=10, net_quantity_unit="pcs", panel_area_cm2=600, min_numeral_height_mm=4.0
    )
    assert check_numeral_height(d).passed  # tier 3: 500-2500cm² -> 4mm
    d = ProductDeclaration(
        net_quantity_value=10, net_quantity_unit="pcs", panel_area_cm2=600, min_numeral_height_mm=3.9
    )
    assert not check_numeral_height(d).passed
    # Missing panel area -> NOT_ASSESSABLE (never a silent PASS, never a FAIL)
    d = ProductDeclaration(net_quantity_value=10, net_quantity_unit="m", min_numeral_height_mm=0.1)
    r = check_numeral_height(d)
    assert r.status == "NOT_ASSESSABLE" and r.remedy


def test_letter_and_width_rules():
    import dataclasses

    d = dataclasses.replace(good(), min_letter_height_mm=0.5)
    rep = evaluate_compliance(d)
    assert any(r.rule_id == "LMPC-7.3-letter" and not r.passed for r in rep.results)
    d = dataclasses.replace(good(), min_letter_height_mm=1.0, min_width_to_height_ratio=0.2)
    rep = evaluate_compliance(d)
    assert any(r.rule_id == "LMPC-7.3-width" and not r.passed for r in rep.results)
    d = dataclasses.replace(good(), min_letter_height_mm=1.0, min_width_to_height_ratio=0.5)
    rep = evaluate_compliance(d)
    assert rep.compliant


def test_rule7_citations_verified():
    rep = evaluate_compliance(good())
    sevens = [r for r in rep.results if r.rule_id.startswith("LMPC-7")]
    assert len(sevens) == 3
    assert all(r.citation_verified for r in sevens)
    assert all("legal-source" in r.source_ref for r in sevens)


def test_not_assessable_never_looks_like_pass():
    """Addendum §A: unmeasurable rules are structurally distinct from PASS."""
    import dataclasses

    d = dataclasses.replace(
        good(),
        min_font_height_mm=None,
        min_numeral_height_mm=None,
        min_letter_height_mm=None,
        min_width_to_height_ratio=None,
    )
    rep = evaluate_compliance(d)
    sevens = {r.rule_id: r for r in rep.results if r.rule_id.startswith("LMPC-7")}
    assert all(r.status == "NOT_ASSESSABLE" for r in sevens.values())
    assert all(not r.passed for r in sevens.values())
    assert all(r.remedy for r in sevens.values())  # every gap carries a remedy hint
    assert rep.verdict == "INCOMPLETE"
    assert not rep.compliant  # dangerous direction: never COMPLIANT when unassessed


def test_not_found_status_and_citation_honesty():
    rep = evaluate_compliance(ProductDeclaration())
    by_id = {r.rule_id: r for r in rep.results}
    assert by_id["LMPC-6.1-manufacturer"].status == "NOT_FOUND"
    assert by_id["LMPC-6.1-mrp"].status == "NOT_FOUND"
    # Verified against the in-repo PDF: (a)-(e) + Rule 7. Care/origin wording
    # is post-2011 amendment: honestly unverified.
    verified = {r.rule_id for r in rep.results if r.citation_verified}
    assert {
        "LMPC-6.1-manufacturer",
        "LMPC-6.1-generic",
        "LMPC-6.1-netqty",
        "LMPC-6.1-mrp",
        "LMPC-6.1-dates",
        "LMPC-6.1-origin",
    } <= verified
    # Domestic-origin PASS rests on the verified importer clause; the import
    # branch and care wording are post-2011: honestly unverified.
    assert not by_id["LMPC-6.1-care"].citation_verified
    assert "amendment" in by_id["LMPC-6.1-care"].citation
    by_imp = {
        r.rule_id: r
        for r in evaluate_compliance(ProductDeclaration(is_imported=True, country_of_origin=None)).results
    }
    assert by_imp["LMPC-6.1-origin"].status == "NOT_FOUND"
    assert not by_imp["LMPC-6.1-origin"].citation_verified
    assert rep.verdict == "NON_COMPLIANT"


def test_observed_values_travel_with_verdict():
    """Legal audit: every finding carries the exact captured value (never bare 'present')."""
    rep = evaluate_compliance(good())
    for r in rep.results:
        assert r.observed and r.expected, f"{r.rule_id} missing captured value"
    by_id = {r.rule_id: r for r in rep.results}
    assert "Acme Foods" in (by_id["LMPC-6.1-manufacturer"].observed or "")
    assert "Wheat Biscuits" in (by_id["LMPC-6.1-generic"].observed or "")
    assert "500" in (by_id["LMPC-6.1-netqty"].observed or "")
    assert "120" in (by_id["LMPC-6.1-mrp"].observed or "")
    assert "2025" in (by_id["LMPC-6.1-dates"].observed or "")
    # Missing declarations still show what was (not) seen.
    empty = {r.rule_id: r for r in evaluate_compliance(ProductDeclaration()).results}
    assert empty["LMPC-6.1-mrp"].observed == "absent"
