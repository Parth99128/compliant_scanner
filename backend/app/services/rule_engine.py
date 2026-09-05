"""Rule engine: deterministic checks for Legal Metrology (Packaged Commodities) Rules, 2011.

Safety principle (DELEGATION-ADDENDUM §A): a rule that could not run must NEVER look
like a rule that passed. Unmeasurable rules return NOT_ASSESSABLE (with a remedy
hint); absent declarations return NOT_FOUND. Only PASS/FAIL-style assessed outcomes
decide compliance, and anything unassessed blocks a COMPLIANT verdict.

Rule 7 tables verified verbatim against docs/legal-source/LMPC-Rules-2011_WB-mirror.pdf pp. 8-9.
All other citations transcribed from the problem statement — see docs/rule-mapping.md.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum


class Status(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_FOUND = "NOT_FOUND"  # declaration absent from the label
    NOT_ASSESSABLE = "NOT_ASSESSABLE"  # rule could not run (e.g. uncalibrated image)


BLOCKING = frozenset({Status.FAIL, Status.NOT_FOUND})

# Verified legal source for Rule 7 (official Rules text, mirrored):
# docs/legal-source/LMPC-Rules-2011_WB-mirror.pdf, Rule 7 on pp. 8-9.
RULES_2011_PDF = "docs/legal-source/LMPC-Rules-2011_WB-mirror.pdf"
RULE7_PAGES = "pp. 8-9"

WEIGHT_VOLUME_UNITS = frozenset({"g", "kg", "mg", "ml", "l"})
LENGTH_AREA_NUMBER_UNITS = frozenset({"cm", "m", "nos", "no", "pc", "pcs"})

# Rule 7(2) Table-I: (max base qty in g/ml, normal mm, embossed mm).
TABLE_I: list[tuple[float, float, float]] = [
    (200.0, 1.0, 2.0),
    (500.0, 2.0, 4.0),
    (float("inf"), 4.0, 6.0),
]

# Rule 7(2) Table-II: (max panel area cm², normal mm, embossed mm).
TABLE_II: list[tuple[float, float, float]] = [
    (100.0, 1.0, 2.0),
    (500.0, 2.0, 4.0),
    (2500.0, 4.0, 6.0),
    (float("inf"), 6.0, 6.0),
]

# Rule 7(3): letter heights (mm) and minimum width/height ratio.
LETTER_HEIGHT_MM = 1.0
LETTER_HEIGHT_EMBOSSED_MM = 2.0
MIN_WIDTH_HEIGHT_RATIO = 1.0 / 3.0

CALIBRATION_REMEDY = (
    "Place a credit-card-sized (85.6mm) reference object in frame, or supply "
    "`ppm` (with optional `font_px`/`letter_px`) to measure text height."
)


@dataclass(frozen=True)
class ProductDeclaration:
    manufacturer_name: str | None = None
    manufacturer_address: str | None = None
    generic_name: str | None = None
    net_quantity_value: float | None = None
    net_quantity_unit: str | None = None
    mrp: float | None = None
    mrp_includes_taxes: bool = False
    mfg_date: date | None = None
    expiry_date: date | None = None
    consumer_care: str | None = None
    country_of_origin: str | None = None
    is_imported: bool = False
    # Rule 7 measurements (mm, from spatial engine):
    min_numeral_height_mm: float | None = None
    min_letter_height_mm: float | None = None
    # Legacy alias for min_numeral_height_mm (kept for backward compatibility).
    min_font_height_mm: float | None = None
    is_embossed: bool = False
    panel_area_cm2: float | None = None
    min_width_to_height_ratio: float | None = None


@dataclass(frozen=True)
class CheckResult:
    rule_id: str
    status: Status
    message: str
    field: str = ""
    citation: str = ""
    citation_verified: bool = False
    observed: str | None = None
    expected: str | None = None
    severity: str = "blocking"  # blocking | review | info
    remedy: str | None = None
    source_ref: str = ""

    @property
    def passed(self) -> bool:
        return self.status == Status.PASS


@dataclass(frozen=True)
class ComplianceReport:
    verdict: str  # COMPLIANT | NON_COMPLIANT | INCOMPLETE
    results: list[CheckResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def compliant(self) -> bool:
        return self.verdict == "COMPLIANT"

    @property
    def failures(self) -> list[CheckResult]:
        return [r for r in self.results if r.status in BLOCKING]

    @property
    def unassessed(self) -> list[CheckResult]:
        return [r for r in self.results if r.status == Status.NOT_ASSESSABLE]


MRP_RE = re.compile(r"(?:mrp|m\.r\.p\.?)\s*(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE)


def _cited(
    rule_id: str,
    field: str,
    citation: str,
    status: Status,
    message: str,
    observed: str | None = None,
    expected: str | None = None,
    verified: bool = False,
    source_ref: str = "",
) -> CheckResult:
    severity = "info" if status == Status.PASS else "blocking"
    # Audit rule: the exact captured value must travel with the verdict so a
    # reviewer can see what the OCR saw (never a bare "present"). Cap length
    # for UI/PDF rendering.
    if isinstance(observed, str) and len(observed) > 160:
        observed = observed[:157] + "..."
    return CheckResult(rule_id, status, message, field, citation, verified, observed, expected, severity)


# Rule 6 clauses verified verbatim against docs/legal-source/LMPC-Rules-2011_WB-mirror.pdf.
RULE6_P5 = f"{RULES_2011_PDF} pp. 5-6"
RULE2_MRP = f"{RULES_2011_PDF} p. 3 (Rule 2(m) manner) + pp. 5-6 (Rule 6(1)(e))"


def _rule7(
    rule_id: str,
    citation: str,
    status: Status,
    message: str,
    observed: str | None = None,
    expected: str | None = None,
    remedy: str | None = None,
) -> CheckResult:
    severity = (
        "info" if status == Status.PASS else ("review" if status == Status.NOT_ASSESSABLE else "blocking")
    )
    return CheckResult(
        rule_id,
        status,
        message,
        rule_id.split("-")[-1],
        citation,
        True,
        observed,
        expected,
        severity,
        remedy,
        f"{RULES_2011_PDF} {RULE7_PAGES}",
    )


def check_manufacturer(d: ProductDeclaration) -> CheckResult:
    if not d.manufacturer_name or not d.manufacturer_address:
        return _cited(
            "LMPC-6.1-manufacturer",
            "manufacturer",
            "Rule 6(1)(a)",
            Status.NOT_FOUND,
            "Missing manufacturer name/address (Rule 6(1)(a))",
            observed="absent",
            expected="manufacturer name + address",
            verified=True,
            source_ref=RULE6_P5,
        )
    return _cited(
        "LMPC-6.1-manufacturer",
        "manufacturer",
        "Rule 6(1)(a)",
        Status.PASS,
        "Manufacturer name+address present",
        observed=f"{d.manufacturer_name}; {d.manufacturer_address}",
        expected="manufacturer name + address",
        verified=True,
        source_ref=RULE6_P5,
    )


def check_generic_name(d: ProductDeclaration) -> CheckResult:
    if not d.generic_name:
        return _cited(
            "LMPC-6.1-generic",
            "generic_name",
            "Rule 6(1)(b)",
            Status.NOT_FOUND,
            "Missing generic/common name (Rule 6(1)(b))",
            observed="absent",
            expected="generic/common name",
            verified=True,
            source_ref=RULE6_P5,
        )
    return _cited(
        "LMPC-6.1-generic",
        "generic_name",
        "Rule 6(1)(b)",
        Status.PASS,
        "Generic name present",
        observed=d.generic_name,
        expected="generic/common name",
        verified=True,
        source_ref=RULE6_P5,
    )


def check_net_quantity(d: ProductDeclaration) -> CheckResult:
    if d.net_quantity_value is None or d.net_quantity_value <= 0 or not d.net_quantity_unit:
        return _cited(
            "LMPC-6.1-netqty",
            "net_quantity",
            "Rule 6(1)(c)",
            Status.NOT_FOUND,
            "Missing/invalid net quantity (Rule 6(1)(c))",
            observed="absent",
            expected="net quantity in standard units",
            verified=True,
            source_ref=RULE6_P5,
        )
    if d.net_quantity_unit.lower() not in WEIGHT_VOLUME_UNITS | LENGTH_AREA_NUMBER_UNITS:
        return _cited(
            "LMPC-6.1-netqty",
            "net_quantity",
            "Rule 6(1)(c)",
            Status.FAIL,
            f"Non-standard unit '{d.net_quantity_unit}' (Rule 6, SI units required)",
            observed=d.net_quantity_unit,
            expected="g/kg/mg/ml/l/cm/m/nos/pc",
            verified=True,
            source_ref=RULE6_P5,
        )
    return _cited(
        "LMPC-6.1-netqty",
        "net_quantity",
        "Rule 6(1)(c)",
        Status.PASS,
        "Net quantity present",
        observed=f"{d.net_quantity_value:g} {d.net_quantity_unit}",
        expected="net quantity in standard units",
        verified=True,
        source_ref=RULE6_P5,
    )


def check_mrp(d: ProductDeclaration) -> CheckResult:
    if d.mrp is None or d.mrp <= 0:
        return _cited(
            "LMPC-6.1-mrp",
            "mrp",
            "Rule 6(1)(e)",
            Status.NOT_FOUND,
            "Missing/invalid MRP (Rule 6(1)(e))",
            observed="absent",
            expected="MRP inclusive of all taxes",
            verified=True,
            source_ref=RULE2_MRP,
        )
    if not d.mrp_includes_taxes:
        return _cited(
            "LMPC-6.1-mrp",
            "mrp",
            "Rule 6(1)(e)",
            Status.FAIL,
            "MRP must state 'inclusive of all taxes' (Rule 6(1)(e) + Rule 2(m) manner)",
            observed="tax phrase absent",
            expected="'inclusive of all taxes'",
            verified=True,
            source_ref=RULE2_MRP,
        )
    return _cited(
        "LMPC-6.1-mrp",
        "mrp",
        "Rule 6(1)(e) + Rule 2(m)",
        Status.PASS,
        "MRP with taxes present",
        observed=f"Rs. {d.mrp} (inclusive of all taxes)",
        expected="MRP inclusive of all taxes",
        verified=True,
        source_ref=RULE2_MRP,
    )


def check_dates(d: ProductDeclaration) -> CheckResult:
    if d.mfg_date is None:
        return _cited(
            "LMPC-6.1-dates",
            "dates",
            "Rule 6(1)(d)",
            Status.NOT_FOUND,
            "Missing manufacture/pack date (Rule 6(1)(d))",
            observed="absent",
            expected="month and year of manufacture/pack/import",
            verified=True,
            source_ref=RULE6_P5,
        )
    if d.expiry_date is not None and d.expiry_date <= d.mfg_date:
        return _cited(
            "LMPC-6.1-dates",
            "dates",
            "Rule 6(1)(d)",
            Status.FAIL,
            "Expiry date must be after manufacture date",
            observed=str(d.expiry_date),
            expected=f"after {d.mfg_date}",
            verified=True,
            source_ref=RULE6_P5,
        )
    exp_txt = f", expiry {d.expiry_date}" if d.expiry_date is not None else ", no expiry stated"
    return _cited(
        "LMPC-6.1-dates",
        "dates",
        "Rule 6(1)(d)",
        Status.PASS,
        "Date declarations valid",
        observed=f"mfg/pack {d.mfg_date}{exp_txt}",
        expected="month and year of manufacture/pack/import",
        verified=True,
        source_ref=RULE6_P5,
    )


def check_consumer_care(d: ProductDeclaration) -> CheckResult:
    # NOTE: the consumer-care requirement is absent from the base 2011 text
    # (Rule 6(1)(f) there covers dimensions). It entered via a post-2011
    # amendment, so this stays citation_verified=False until the amended text
    # is sourced.
    if not d.consumer_care:
        return _cited(
            "LMPC-6.1-care",
            "consumer_care",
            "Rule 6(1) consumer-care proviso (post-2011 amendment)",
            Status.NOT_FOUND,
            "Missing customer-care name/address/contact",
            observed="absent",
            expected="customer-care contact",
        )
    return _cited(
        "LMPC-6.1-care",
        "consumer_care",
        "Rule 6(1) consumer-care proviso (post-2011 amendment)",
        Status.PASS,
        "Consumer care details present",
        observed=d.consumer_care,
        expected="customer-care contact",
    )


def check_origin(d: ProductDeclaration) -> CheckResult:
    # Base text (Rule 6(1)(a), p. 5) requires the importer's name/address;
    # the literal "country of origin" wording comes from a later amendment.
    if d.is_imported and not d.country_of_origin:
        return _cited(
            "LMPC-6.1-origin",
            "country_of_origin",
            "Rule 6(1)(a) importer clause (country wording: later amendment)",
            Status.NOT_FOUND,
            "Imported package must declare country of origin",
            observed="absent",
            expected="country of origin",
        )
    origin_txt = d.country_of_origin or "domestic supply (no import claimed)"
    return _cited(
        "LMPC-6.1-origin",
        "country_of_origin",
        "Rule 6(1)(a) importer clause",
        Status.PASS,
        "Origin declaration valid",
        observed=origin_txt,
        expected="country of origin if imported",
        verified=True,
        source_ref=RULE6_P5,
    )


def _to_base_qty(value: float, unit: str) -> float | None:
    """Normalize weight/volume to grams-or-ml for Table-I lookup."""
    u = unit.lower()
    if u == "kg":
        return value * 1000.0
    if u == "mg":
        return value / 1000.0
    if u == "l":
        return value * 1000.0
    if u in ("g", "ml"):
        return value
    return None


def required_numeral_height(
    net_value: float | None, unit: str | None, panel_area_cm2: float | None, embossed: bool
) -> tuple[float | None, str]:
    """Rule 7(2) Table-I/II lookup. Returns (required mm or None, basis description)."""
    if unit is not None and unit.lower() in WEIGHT_VOLUME_UNITS and net_value is not None:
        base = _to_base_qty(net_value, unit)
        if base is None:
            return None, "unconvertible unit"
        tag = "embossed pack" if embossed else "ordinary print"
        for limit, normal, emb in TABLE_I:
            if base <= limit:
                return (emb if embossed else normal), f"Table-I (net {base:g}g/ml, {tag})"
        return TABLE_I[-1][1 if embossed else 0], f"Table-I ({tag})"
    if unit is not None and unit.lower() in LENGTH_AREA_NUMBER_UNITS:
        if panel_area_cm2 is None or panel_area_cm2 <= 0:
            return None, "Table-II needs principal display panel area"
        tag = "embossed pack" if embossed else "ordinary print"
        for limit, normal, emb in TABLE_II:
            if panel_area_cm2 <= limit:
                return (emb if embossed else normal), f"Table-II (panel {panel_area_cm2:g}cm², {tag})"
        return TABLE_II[-1][1 if embossed else 0], f"Table-II ({tag})"
    return None, "unknown unit class"


def check_numeral_height(d: ProductDeclaration) -> CheckResult:
    height = d.min_numeral_height_mm if d.min_numeral_height_mm is not None else d.min_font_height_mm
    required, basis = required_numeral_height(
        d.net_quantity_value, d.net_quantity_unit, d.panel_area_cm2, d.is_embossed
    )
    if height is None:
        need = f"required >= {required}mm" if required is not None else "requirement undetermined"
        return _rule7(
            "LMPC-7.2-numeral",
            "Rule 7(2) Table-I/II",
            Status.NOT_ASSESSABLE,
            f"Numeral height not measured; {need} ({basis}) — cannot assess",
            observed="unmeasured",
            expected=f"{need} ({basis})",
            remedy=CALIBRATION_REMEDY,
        )
    if required is None:
        return _rule7(
            "LMPC-7.2-numeral",
            "Rule 7(2) Table-I/II",
            Status.NOT_ASSESSABLE,
            f"Cannot determine Table tier ({basis}) — cannot assess",
            observed="unknown tier",
            expected="determinable tier",
            remedy=CALIBRATION_REMEDY,
        )
    ok = height >= required
    return _rule7(
        "LMPC-7.2-numeral",
        "Rule 7(2) Table-I/II",
        Status.PASS if ok else Status.FAIL,
        (
            f"Numeral height {height}mm >= {required}mm ({basis})"
            if ok
            else f"Numeral height {height}mm < required {required}mm ({basis})"
        ),
        observed=f"{height}mm",
        expected=f">= {required}mm ({basis})",
    )


def check_letter_height(d: ProductDeclaration) -> CheckResult:
    required = LETTER_HEIGHT_EMBOSSED_MM if d.is_embossed else LETTER_HEIGHT_MM
    tag = "embossed pack" if d.is_embossed else "ordinary print"
    if d.min_letter_height_mm is None:
        return _rule7(
            "LMPC-7.3-letter",
            "Rule 7(3)",
            Status.NOT_ASSESSABLE,
            f"Letter height not measured; required >= {required}mm — cannot assess",
            observed="unmeasured",
            expected=f">= {required}mm",
            remedy=CALIBRATION_REMEDY,
        )
    ok = d.min_letter_height_mm >= required
    return _rule7(
        "LMPC-7.3-letter",
        "Rule 7(3)",
        Status.PASS if ok else Status.FAIL,
        (
            f"Letter height {d.min_letter_height_mm}mm >= {required}mm ({tag})"
            if ok
            else f"Letter height {d.min_letter_height_mm}mm < required {required}mm (Rule 7(3), {tag})"
        ),
        observed=f"{d.min_letter_height_mm}mm",
        expected=f">= {required}mm ({tag})",
    )


def check_width_ratio(d: ProductDeclaration) -> CheckResult:
    if d.min_width_to_height_ratio is None:
        return _rule7(
            "LMPC-7.3-width",
            "Rule 7(3) proviso",
            Status.NOT_ASSESSABLE,
            "Glyph width not measured; required width >= 1/3 height — cannot assess",
            observed="unmeasured",
            expected="width/height >= 1/3",
            remedy=CALIBRATION_REMEDY,
        )
    ok = d.min_width_to_height_ratio >= MIN_WIDTH_HEIGHT_RATIO
    return _rule7(
        "LMPC-7.3-width",
        "Rule 7(3) proviso",
        Status.PASS if ok else Status.FAIL,
        (
            f"Width/height ratio {d.min_width_to_height_ratio:.2f} >= 1/3"
            if ok
            else f"Width/height ratio {d.min_width_to_height_ratio:.2f} < 1/3 "
            "(excludes numeral '1' and letters i/I/l)"
        ),
        observed=f"{d.min_width_to_height_ratio:.2f}",
        expected=">= 0.33",
    )


def evaluate_compliance(d: ProductDeclaration, ocr_confidence: float | None = None) -> ComplianceReport:
    """ocr_confidence MUST be on the raw Tesseract 0–100 scale (see _mean_confidence).

    Regression-pinned by tests/test_confidence_scale.py — do not pass a 0–1 score here.
    """
    if d.min_numeral_height_mm is None and d.min_font_height_mm is not None:
        d = dataclasses.replace(d, min_numeral_height_mm=d.min_font_height_mm)
    results = [
        check_manufacturer(d),
        check_generic_name(d),
        check_net_quantity(d),
        check_mrp(d),
        check_dates(d),
        check_consumer_care(d),
        check_origin(d),
        check_numeral_height(d),
        check_letter_height(d),
        check_width_ratio(d),
    ]
    if any(r.status in BLOCKING for r in results):
        verdict = "NON_COMPLIANT"
    elif any(r.status == Status.NOT_ASSESSABLE for r in results):
        verdict = "INCOMPLETE"
    else:
        verdict = "COMPLIANT"
    warnings: list[str] = []
    if ocr_confidence is not None and ocr_confidence < 60:
        warnings.append(
            f"Low OCR confidence ({ocr_confidence}%) — label may be illegible; "
            "verify declarations on the physical package (legibility warning)"
        )
    return ComplianceReport(verdict=verdict, results=results, warnings=warnings)
