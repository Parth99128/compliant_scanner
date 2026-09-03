"""Hybrid regex (+ optional spaCy) field extraction — CPU-only, no GPU/torch required."""

from __future__ import annotations

import re
from datetime import date, datetime

from app.services.rule_engine import ProductDeclaration

MRP_RE = re.compile(
    r"(?:MRP|M\.?R\.?P\.?)\s*(?:Rs\.?|INR|₹)?\s*[:\-]?\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE
)
INCL_TAXES_RE = re.compile(r"incl\w*\s+o[ft]\s+all\s+tax", re.IGNORECASE)
NET_QTY_RE = re.compile(
    r"net\s*(?:q?t[yl]|quantity|wt|weight|vol|content|o?t?y)[^\d]*([\d.,]+)\s*(kg|g|mg|ml|l|litre?s?|cm|m|nos?|pcs?|pc)\b",
    re.IGNORECASE,
)
NET_QTY_FALLBACK_RE = re.compile(r"\b([\d.,]+)\s*(kg|g\b|mg|ml|l\b|litre?s?)\b", re.IGNORECASE)
MFG_RE = re.compile(
    r"(?:mfg|mtg|manufactured|packed|mfd|pkd|m[fd]d?)[^\d]*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{4}[/\-.]\d{4}|\w+\s+\d{4}|\d{4}[/\-]\d{1,2})",
    re.IGNORECASE,
)
EXP_RE = re.compile(
    r"(?:exp|expr|expiry|best\s*before|use\s*by)[^\d]*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{4}[/\-.]\d{4}|\d+\s*(?:months?|days?|years?))",
    re.IGNORECASE,
)
# Fallback: bare dates with no keyword anchor (common when OCR drops the label word).
BARE_DATE_RE = re.compile(r"\b(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{4}[/\-.]\d{4})\b")
CARE_RE = re.compile(
    r"(?:(?:customer|consumer)\s*[a-z]?are\b|helpline|toll\s*free)[^\n]*?([\w+\-.]+ ?@ ?[a-z\d\-.]+ ?\.[a-z]{2,}|\+?91[\s\-]*\d[\d\s\-]{4,}|1800[\s\-]*\d[\d\s\-]*)",
    re.IGNORECASE,
)
ORIGIN_RE = re.compile(r"(?:country\s*o[ft]\s*origin|made\s*in)\s*[:\-]?\s*([A-Za-z ]{2,30})", re.IGNORECASE)
ADDRESS_HINT_RE = re.compile(r"\b(?:plot|street|road|sector|nagar|mumbai|delhi|india|\d{6})\b", re.IGNORECASE)

DATE_FMTS = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%Y-%m-%d", "%b %Y", "%B %Y", "%m/%Y")


def _parse_date(s: str) -> date | None:
    s = s.strip()
    # Repair OCR-glued dates: "0101/2025" -> "01/01/2025".
    m = re.fullmatch(r"(\d{2})(\d{2})/(\d{4})", s)
    if m:
        s = f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
    for fmt in DATE_FMTS:  # label dates are naive wall-dates by nature (no tz)
        try:
            return datetime.strptime(s, fmt).date()  # noqa: DTZ007
        except ValueError:
            continue
    return None


def _norm_num(s: str) -> float | None:
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def extract_fields(ocr_text: str) -> ProductDeclaration:
    text = ocr_text or ""
    m = MRP_RE.search(text)
    mrp_val = _norm_num(m.group(1)) if m else None
    incl_taxes = bool(INCL_TAXES_RE.search(text))

    m = NET_QTY_RE.search(text) or NET_QTY_FALLBACK_RE.search(text)
    qty_val = _norm_num(m.group(1)) if m else None
    qty_unit = m.group(2).lower().rstrip("s") if m and len(m.groups()) >= 2 else None
    if qty_unit == "litre":
        qty_unit = "l"

    m = MFG_RE.search(text)
    mfg = _parse_date(m.group(1)) if m else None
    m = EXP_RE.search(text)
    exp_raw = m.group(1) if m else None
    exp: date | None = None
    if exp_raw:
        exp = _parse_date(exp_raw)  # relative durations ("12 months") -> left None (needs mfg anchor)
    if mfg is None or exp is None:
        # Keyword anchor OCR-mangled (e.g. "Mtg"/"Expr") or dropped: fall back to
        # bare dates in reading order — first = mfg, second = expiry.
        bare = [_parse_date(b) for b in BARE_DATE_RE.findall(text)]
        bare = [b for b in bare if b is not None]
        if mfg is None and bare:
            mfg = bare[0]
        if exp is None and len(bare) >= 2:
            exp = bare[1]

    m = CARE_RE.search(text)
    care = m.group(0).strip()[:300] if m else None

    m = ORIGIN_RE.search(text)
    origin = m.group(1).strip() if m else None
    imported = origin is not None and origin.lower() not in ("india",)

    # Heuristic: first line with letters = generic name; line with address hint = manufacturer block
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    generic = lines[0][:120] if lines else None
    addr_lines = [ln for ln in lines if ADDRESS_HINT_RE.search(ln)]
    mfr_name = addr_lines[0][:160] if addr_lines else None
    mfr_addr = "; ".join(addr_lines[:2])[:300] if addr_lines else None

    try:
        import spacy  # optional, CPU; never required

        _ = spacy  # placeholder: if installed, NER could refine ORG/GPE here
    except ImportError:
        pass

    return ProductDeclaration(
        manufacturer_name=mfr_name,
        manufacturer_address=mfr_addr,
        generic_name=generic if generic and len(generic) > 2 else None,
        net_quantity_value=qty_val,
        net_quantity_unit=qty_unit,
        mrp=mrp_val,
        mrp_includes_taxes=incl_taxes,
        mfg_date=mfg,
        expiry_date=exp,
        consumer_care=care,
        country_of_origin=origin,
        is_imported=imported,
    )
