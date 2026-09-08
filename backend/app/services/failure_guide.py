"""Failure guidance: why a check failed and the exact next steps.

Safety principle (DELEGATION-ADDENDUM section A, extended): a detection miss
must never look like a proven violation. A FAIL/NOT_FOUND outcome therefore
carries, beyond message/observed/expected:

- cause: "genuine" (we read the offending value) | "likely_genuine"
  (clear read, declaration absent — still verify) | "possible_miss" (weak
  read — the declaration may exist but our OCR could not see it) |
  "unmeasured" (NOT_ASSESSABLE — carries its remedy as the next step)
- why: one plain-language sentence joining what we saw with the caveat
- next_steps: ordered, checkable actions ending in physical verification
  plus the officer review action (confirm / correct / override)

This module is deliberately dependency-free (duck-typed on the result) so
rule_engine can import it without a cycle.
"""

from __future__ import annotations

import dataclasses

LOW_READ_CONFIDENCE = 60.0  # same bar as the legibility warning (0-100 scale)

_REVIEW_STEP = (
    "In Review: Confirm the finding if the package truly fails; if the declaration "
    "IS on the package, correct the value (Rule 6 findings) or Override with a note (admin)."
)
_VERIFY_STEP = "Verify on the physical package with your own eyes — the photo is evidence, you decide."


def _retake(panel: str) -> str:
    return f"Retake a close-up (macro) photo of the {panel} so the text fills the frame."


def _search_ocr(keyword: str) -> str:
    return (
        f"Open the scan's OCR text panel and search for {keyword} — "
        "if you can read it there, our extractor missed it, not the packer."
    )


GUIDE: dict[str, dict[str, object]] = {
    "LMPC-6.1-manufacturer": {
        "label": "maker/packer name and address",
        "why_typed": "No maker/packer name and address was provided — Rule 6(1)(a) requires it.",
        "why_low": (
            "We could not find the maker/packer name and address in a weak read "
            "({conf}) — it may be printed but unreadable (small, curved or glossy "
            "surface), or it may truly be absent."
        ),
        "why_clear": (
            "On a clear read ({conf}) we found no maker/packer name and address — "
            "likely a real violation, but confirm: it can sit on a side flap or the "
            "bottom that was never photographed."
        ),
        "panel": "name-and-address panel (usually back or bottom, include side flaps)",
        "keyword": "'Mfd', 'Mfg', 'Mktd' or 'Marketed by'",
        "steps_typed": [
            "Add the maker/packer name and address and re-validate.",
            "If it is on the pack but unreadable, upload a scan photo instead of typing.",
        ],
    },
    "LMPC-6.1-generic": {
        "label": "generic/common name",
        "why_typed": "No generic/common product name was provided — Rule 6(1)(b) requires it.",
        "why_low": (
            "We could not find the generic product name in a weak read ({conf}) — "
            "fancy brand lettering is often unreadable to OCR, or the name may truly be absent."
        ),
        "why_clear": (
            "On a clear read ({conf}) we found no generic product name (e.g. 'Wheat "
            "Biscuits' under the brand) — likely a real violation; confirm on the pack."
        ),
        "panel": "front display panel under the brand name",
        "keyword": "the product name itself",
        "steps_typed": [
            "Add the generic/common product name and re-validate.",
            "If it is on the pack but unreadable, upload a scan photo instead of typing.",
        ],
    },
    "LMPC-6.1-netqty": {
        "label": "net quantity",
        "why_typed": "No usable net quantity was provided — Rule 6(1)(c) requires amount + standard unit.",
        "why_low": (
            "We could not find the net quantity in a weak read ({conf}) — it is small "
            "print and easily missed, or it may truly be absent."
        ),
        "why_clear": (
            "On a clear read ({conf}) we found no net quantity — likely a real violation; "
            "confirm on the pack, usually near the MRP."
        ),
        "why_invalid": (
            "We read the unit '{observed}', which is not a standard unit — usually a genuine "
            "breach, but single letters are also the commonest OCR misreads (e.g. '9' for 'g')."
        ),
        "panel": "net-quantity declaration (front, usually near the MRP)",
        "keyword": "'Net Qty', 'Net Wt', 'Net Content' or the e-mark",
        "steps_typed": [
            "Add the net quantity with a standard unit (g/kg/mg/ml/l/cm/m/nos/pc) and re-validate.",
        ],
        "steps_invalid": [
            _search_ocr("the unit letters"),
            "If the unit is misread, correct it via the finding correction and re-review.",
            "If that unit is truly printed, the pack breaches the standard-units rule.",
        ],
    },
    "LMPC-6.1-mrp": {
        "label": "MRP",
        "why_typed": "No MRP was provided — Rule 6(1)(e) requires it with 'inclusive of all taxes'.",
        "why_low": (
            "We could not find the MRP in a weak read ({conf}) — price stickers and "
            "ink-jet MRPs are often unreadable, or it may truly be absent."
        ),
        "why_clear": (
            "On a clear read ({conf}) we found no MRP — likely a real violation; "
            "confirm on the pack, including stickers."
        ),
        "why_invalid": (
            "We found an MRP but not the words 'inclusive of all taxes' — usually a genuine "
            "breach, but the tax line is small print and often missed (observed: '{observed}')."
        ),
        "panel": "price/MRP panel, including any sticker",
        "keyword": "'MRP', 'M.R.P.', 'Rs' or the tax words",
        "steps_typed": [
            "Add the MRP (tick 'inclusive of all taxes' only if those words are printed) and re-validate.",
        ],
        "steps_invalid": [
            _retake("price/MRP panel, including any sticker"),
            _search_ocr("'tax' or 'inclusive'"),
            "If the tax words ARE printed, correct the finding and re-review; if truly absent, it is a genuine breach.",
        ],
    },
    "LMPC-6.1-dates": {
        "label": "manufacture/expiry dates",
        "why_typed": "No manufacture/pack date was provided — Rule 6(1)(d) requires month and year.",
        "why_low": (
            "We could not find the dates in a weak read ({conf}) — date stamps are usually "
            "embossed or ink-jetted and are the single most-missed field, or they may truly be absent."
        ),
        "why_clear": (
            "On a clear read ({conf}) we found no manufacture/pack date — likely a real "
            "violation; confirm on crimps, caps and stickers, not just the main label."
        ),
        "why_invalid": (
            "We read an expiry ({observed}) that is not after manufacture ({expected}) — this is "
            "usually a misread year (6 vs 8) or swapped fields, rarely a real pack error."
        ),
        "panel": "date stamp area (crimp, cap, sticker) using angled light for embossing",
        "keyword": "'Mfg', 'Exp', 'Pkd' or 'Best before'",
        "steps_typed": [
            "Add the manufacture month/year (and expiry, if printed) and re-validate.",
        ],
        "steps_invalid": [
            "Read the stamp on the physical pack yourself — compare each digit with what we read.",
            "If we misread it, correct the dates via the finding correction and re-review.",
            "If the pack truly shows expiry on/before manufacture, it is a genuine breach.",
        ],
    },
    "LMPC-6.1-care": {
        "label": "customer-care contact",
        "why_typed": "No customer-care name/address/contact was provided — required by the post-2011 proviso.",
        "why_low": (
            "We could not find customer-care details in a weak read ({conf}) — they sit in "
            "small print and are easily missed, or they may truly be absent."
        ),
        "why_clear": (
            "On a clear read ({conf}) we found no customer-care contact — likely a real "
            "violation; confirm on the back panel."
        ),
        "panel": "customer-care panel (usually back, small print)",
        "keyword": "'care', 'helpline', 'toll' or 'complaint'",
        "steps_typed": [
            "Add the customer-care name, address and phone/email, then re-validate.",
        ],
    },
    "LMPC-6.1-origin": {
        "label": "country of origin",
        "why_typed": "The pack is marked imported but no country of origin was provided.",
        "why_low": (
            "We could not find the country of origin in a weak read ({conf}) for a pack "
            "marked imported — it may be printed but unreadable, or truly absent."
        ),
        "why_clear": (
            "On a clear read ({conf}) an imported pack shows no country of origin — "
            "likely a real violation; confirm on the importer panel."
        ),
        "panel": "importer panel ('Imported by …')",
        "keyword": "'Imported by' or a country name",
        "steps_typed": [
            "Add the country of origin, or unmark 'imported' if the pack is domestic, then re-validate.",
        ],
    },
    "LMPC-7.2-numeral": {
        "label": "numeral height",
        "why_invalid": (
            "We measured {observed} against a required {expected} — either the print is "
            "truly too small, or our scale was off (no reference card, wrong "
            "embossed/printed setting, or wrong panel area for count packs)."
        ),
        "steps_invalid": [
            "Re-capture WITH a credit-card-size reference object in frame.",
            "Confirm the embossed toggle matches the pack (embossed/moulded vs plain print).",
            "For count/length packs, confirm the principal display panel area you entered.",
            "If it still measures short, the pack genuinely breaches Rule 7(2).",
        ],
    },
    "LMPC-7.3-letter": {
        "label": "letter height",
        "why_invalid": (
            "We measured {observed} against a required {expected} — either the letters are "
            "truly under 1mm (2mm embossed), or our scale was off (no reference card, "
            "wrong embossed/printed setting)."
        ),
        "steps_invalid": [
            "Re-capture WITH a credit-card-size reference object in frame.",
            "Confirm the embossed toggle matches the pack (embossed/moulded vs plain print).",
            "If it still measures short, the pack genuinely breaches Rule 7(3).",
        ],
    },
    "LMPC-7.3-width": {
        "label": "letter/numeral width",
        "why_invalid": (
            "We measured a width/height ratio of {observed} against {expected} — either the "
            "typeface is truly too narrow, or blur/low resolution thinned the strokes."
        ),
        "steps_invalid": [
            "Retake a sharp close-up of the smallest text (hold steady, good light).",
            "Re-capture WITH a reference object so the scale is exact.",
            "If it still measures narrow, the pack genuinely breaches the Rule 7(3) proviso.",
        ],
    },
}


def _status_of(result) -> str:
    status = getattr(result, "status", "")
    return status.value if hasattr(status, "value") else str(status)


def _conf_txt(ocr_confidence: float | None) -> str:
    return f"{ocr_confidence:g}%" if ocr_confidence is not None else "unknown"


def _str_list(guide: dict[str, object], key: str) -> list[str]:
    value = guide.get(key, [])
    return [str(s) for s in value] if isinstance(value, list) else []


def annotate_failure(result, ocr_confidence: float | None = None):
    """Attach cause/why/next_steps to one non-PASS CheckResult (pure)."""
    status = _status_of(result)
    if status == "PASS":
        return result
    guide = GUIDE.get(str(getattr(result, "rule_id", "")))
    if guide is None:
        return result  # e.g. INFO-only GTIN cards or future rules: leave untouched
    observed = getattr(result, "observed", None) or "—"
    expected = getattr(result, "expected", None) or "—"
    low_read = ocr_confidence is not None and ocr_confidence < LOW_READ_CONFIDENCE

    if status == "NOT_ASSESSABLE":
        remedy = getattr(result, "remedy", None)
        return dataclasses.replace(
            result,
            cause="unmeasured",
            why=str(getattr(result, "message", "")),
            next_steps=tuple([remedy] if remedy else []),
        )
    if status == "NOT_FOUND":
        if ocr_confidence is None:
            cause = "likely_genuine"
            why = str(guide.get("why_typed", result.message))
            steps = _str_list(guide, "steps_typed") + [_VERIFY_STEP, _REVIEW_STEP]
        elif low_read:
            cause = "possible_miss"
            why = str(guide["why_low"]).format(conf=_conf_txt(ocr_confidence))
            steps = [
                _retake(str(guide["panel"])),
                _search_ocr(str(guide["keyword"])),
                _VERIFY_STEP,
                _REVIEW_STEP,
            ]
        else:
            cause = "likely_genuine"
            why = str(guide["why_clear"]).format(conf=_conf_txt(ocr_confidence))
            steps = [
                _retake(str(guide["panel"])),
                _VERIFY_STEP,
                _REVIEW_STEP,
            ]
        return dataclasses.replace(result, cause=cause, why=why, next_steps=tuple(steps))

    # FAIL — we read an offending value, so the breach is genuine unless the
    # read itself was weak, in which case flag the doubt explicitly.
    why_t = str(guide.get("why_invalid", result.message))
    try:
        why = why_t.format(observed=observed, expected=expected)
    except (IndexError, KeyError):
        why = why_t
    steps = _str_list(guide, "steps_invalid") or [_VERIFY_STEP]
    if low_read:
        why += f" Note: the read was weak ({ocr_confidence:g}%), so double-check what we read before acting."
        steps = [_search_ocr(str(guide.get("keyword", "the value")))] + steps
    steps = steps + [_VERIFY_STEP, _REVIEW_STEP] if _VERIFY_STEP not in steps else steps + [_REVIEW_STEP]
    cause = "genuine" if not low_read else "likely_genuine"
    return dataclasses.replace(result, cause=cause, why=why, next_steps=tuple(steps))
