"""Failure guidance: misses must not look like proven violations.

Every FAIL/NOT_FOUND outcome carries cause/why/next_steps, and a weak read
(<60%) with only NOT_FOUND misses folds to INCOMPLETE — never NON_COMPLIANT.
"""

import dataclasses
from datetime import date

from app.api.v1.routes import _checks, _stored_checks
from app.services.failure_guide import GUIDE, LOW_READ_CONFIDENCE, annotate_failure
from app.services.rule_engine import ProductDeclaration, check_mrp, evaluate_compliance

CAUSES = {"genuine", "likely_genuine", "possible_miss", "unmeasured"}


def good() -> ProductDeclaration:
    return ProductDeclaration(
        manufacturer_name="Acme Foods",
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


def test_weak_read_miss_is_incomplete_not_non_compliant():
    d = dataclasses.replace(good(), mrp=None, mrp_includes_taxes=False)
    rep = evaluate_compliance(d, ocr_confidence=45.0)
    assert rep.verdict == "INCOMPLETE"
    assert not rep.compliant
    mrp = next(r for r in rep.results if r.rule_id == "LMPC-6.1-mrp")
    assert mrp.status == "NOT_FOUND"
    assert mrp.cause == "possible_miss"
    assert mrp.why and "45%" in mrp.why and "%%" not in mrp.why
    assert any("macro" in s for s in mrp.next_steps)
    assert any("physical package" in s for s in mrp.next_steps)
    assert any("NOT non-compliant" in w for w in rep.warnings)


def test_clear_read_absence_stays_non_compliant():
    d = dataclasses.replace(good(), mrp=None, mrp_includes_taxes=False)
    rep = evaluate_compliance(d, ocr_confidence=90.0)
    assert rep.verdict == "NON_COMPLIANT"
    mrp = next(r for r in rep.results if r.rule_id == "LMPC-6.1-mrp")
    assert mrp.cause == "likely_genuine"
    assert mrp.why and mrp.next_steps


def test_genuine_fail_has_genuine_cause_and_why():
    d = dataclasses.replace(good(), expiry_date=date(2024, 1, 1))
    rep = evaluate_compliance(d, ocr_confidence=92.0)
    assert rep.verdict == "NON_COMPLIANT"
    dates = next(r for r in rep.results if r.rule_id == "LMPC-6.1-dates")
    assert dates.status == "FAIL" and dates.cause == "genuine"
    assert "2024" in dates.why
    assert len(dates.next_steps) >= 2


def test_typed_path_keeps_strict_verdict():
    rep = evaluate_compliance(ProductDeclaration())  # /validate: no OCR involved
    assert rep.verdict == "NON_COMPLIANT"
    mrp = next(r for r in rep.results if r.rule_id == "LMPC-6.1-mrp")
    assert mrp.cause == "likely_genuine"
    assert any("re-validate" in s for s in mrp.next_steps)


def test_mixed_genuine_fail_plus_miss_stays_non_compliant():
    d = dataclasses.replace(good(), expiry_date=date(2024, 1, 1), mrp=None, mrp_includes_taxes=False)
    rep = evaluate_compliance(d, ocr_confidence=40.0)
    assert rep.verdict == "NON_COMPLIANT"  # the genuine breach decides
    by_id = {r.rule_id: r for r in rep.results}
    assert by_id["LMPC-6.1-dates"].cause == "likely_genuine"  # weak read, still observed
    assert by_id["LMPC-6.1-mrp"].cause == "possible_miss"  # miss keeps its guidance


def test_all_rules_have_guidance_coverage():
    assert LOW_READ_CONFIDENCE == 60.0  # pinned to the legibility bar
    # Every rule id the engine can emit (except INFO-only GTIN cards) has a guide.
    rep = evaluate_compliance(ProductDeclaration(), ocr_confidence=30.0)
    emitted = {r.rule_id for r in rep.results}
    assert set(GUIDE) >= (emitted - {"LMPC-gtin"})
    for conf in (None, 30.0, 95.0):
        for r in evaluate_compliance(ProductDeclaration(), ocr_confidence=conf).results:
            if r.status == "PASS":  # e.g. domestic origin on an empty declaration
                continue
            assert r.cause in CAUSES, f"{r.rule_id} missing cause"
            assert r.why, f"{r.rule_id} missing why"
            assert "%%" not in r.why, f"{r.rule_id} double-percent"
            assert r.next_steps, f"{r.rule_id} missing next_steps"


def test_rule7_shortfall_explains_scale_doubt():
    d = dataclasses.replace(good(), min_font_height_mm=1.0)  # 500g needs 2mm
    rep = evaluate_compliance(d, ocr_confidence=88.0)
    num = next(r for r in rep.results if r.rule_id == "LMPC-7.2-numeral")
    assert num.status == "FAIL" and num.cause == "genuine"
    assert "reference" in " ".join(num.next_steps).lower()
    assert rep.verdict == "NON_COMPLIANT"


def test_annotate_leaves_pass_and_unknown_rules_untouched():
    rep = evaluate_compliance(good(), ocr_confidence=95.0)
    assert rep.verdict == "COMPLIANT"
    assert all(r.cause == "" and r.why == "" and r.next_steps == () for r in rep.results)
    from app.services.rule_engine import CheckResult, Status

    mystery = CheckResult(rule_id="LMPC-future", status=Status.FAIL, message="x")
    assert annotate_failure(mystery, 10.0) is mystery
    assert annotate_failure(check_mrp(good()), 95.0).cause == ""  # PASS untouched


def test_api_passthrough_and_old_row_back_compat():
    d = dataclasses.replace(good(), mrp=None, mrp_includes_taxes=False)
    rep = evaluate_compliance(d, ocr_confidence=45.0)
    checks = _checks(rep)
    mrp = next(c for c in checks if c.rule_id == "LMPC-6.1-mrp")
    assert mrp.cause == "possible_miss" and mrp.why and len(mrp.next_steps) >= 3
    # Rows stored before this feature lack the keys entirely.
    old = [
        {
            "rule_id": "LMPC-6.1-mrp",
            "status": "NOT_FOUND",
            "message": "m",
            "severity": "blocking",
        }
    ]
    restored = _stored_checks(old)
    assert restored[0].cause == "" and restored[0].why == "" and restored[0].next_steps == []


def test_report_builds_with_guidance():
    from app.services.report import build_report_pdf

    class FakeScan:
        id = "s1"
        request_id = "r1"
        product_name = "p"
        brand_name = "b"
        category = "c"
        ocr_engine = "tesseract"
        ocr_confidence = 45.0
        verdict = "INCOMPLETE"
        status = "pending_review"
        reviewed_by = None
        reviewed_at = None
        created_at = None
        corrected_by = None
        corrected_at = None
        scan_lat = None
        scan_lon = None
        image_blob = None

    d = dataclasses.replace(good(), mrp=None, mrp_includes_taxes=False)
    rep = evaluate_compliance(d, ocr_confidence=45.0)
    results = [dataclasses.asdict(r) for r in rep.results]
    pdf = build_report_pdf(FakeScan(), results, rep.warnings)
    assert isinstance(pdf, bytes) and len(pdf) > 1000
