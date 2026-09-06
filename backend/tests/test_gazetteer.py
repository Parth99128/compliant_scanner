"""Gazetteer matching: typo repair + missing-maker fill, with all guardrails."""

import time

from app.services.extraction import extract_fields
from app.services.gazetteer import fill_manufacturer, fix_manufacturer, match_name


def test_typo_fix_repairs_brand():
    name, score = fix_manufacturer("Hindustan Uniiever")
    assert name == "Hindustan Unilever" and score >= 93


def test_fix_handles_full_address_line():
    name, score = fix_manufacturer("Hindustan Uniiever Ltd, Plot 1, Mumbai 400001")
    assert name == "Hindustan Unilever" and score >= 93
    name, score = fix_manufacturer("Acme Foods, Plot 5, Mumbai 400001")
    assert name == "Acme Foods" and score == 100.0


def test_fix_picks_right_company_over_similar():
    name, _ = fix_manufacturer("Lotus Daily, Plot 3, Chennai 600001")
    assert name == "Lotus Daily"


def test_fill_finds_maker_in_lines():
    name, score = fill_manufacturer("Instant Noodles\nHindustan Uniiever Ltd\nNet Qty: 60 g")
    assert name == "Hindustan Unilever" and score >= 90


def test_guards_reject_everything_risky():
    assert match_name("Tata") == (None, 0.0)  # too short
    assert match_name("Xyzzy Quux Factory") == (None, 0.0)  # unknown
    assert match_name("Customer Care: care@acme.in 1800-123-456") == (None, 0.0)
    assert match_name("Plot 5, Mumbai 400001") == (None, 0.0)  # address, no brand
    assert match_name("Pack of 9 tablets") == (None, 0.0)
    assert fix_manufacturer(None) == (None, 0.0)
    assert fill_manufacturer("") == (None, 0.0)


def test_extraction_canonicalizes_mangled_maker():
    d = extract_fields("Instant Noodles\nHindustan Uniiever Ltd, Mumbai 400001\nNet Qty: 60 g")
    assert d.manufacturer_name == "Hindustan Unilever"


def test_extraction_never_invents_numbers():
    before = extract_fields("MRP Rs. 99\nNet Qty: 1 kg\nMfg: 02/03/2025")
    assert (before.mrp, before.net_quantity_unit, before.mfg_date is not None) == (99.0, "kg", True)


def test_matcher_is_instant():
    t0 = time.perf_counter()
    for _ in range(20):
        match_name("Hindustan Uniiever Ltd, Plot 1, Mumbai 400001")
    assert (time.perf_counter() - t0) / 20 < 0.05  # ms-scale, CPU-only
