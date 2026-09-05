"""Hybrid regex (+ optional spaCy) field extraction — CPU-only, no GPU/torch required."""

from __future__ import annotations

import difflib
import re
from datetime import date, datetime

from app.services.rule_engine import ProductDeclaration

MRP_RE = re.compile(
    r"(?:MRP|M\.?R\.?P\.?)\s*(?:Rs\.?|INR|₹)?\s*[:\-]?\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE
)
INCL_TAXES_RE = re.compile(r"incl.*?o[ft]\W*all\W*tax", re.IGNORECASE)
NET_QTY_RE = re.compile(
    r"net\s*(?:q?t[yl]|quantity|wt|weight|vol|content|o?t?y)[^\d]*([\d.,]+)\s*(kg|g|mg|ml|l|litre?s?|cm|m|nos?|pcs?|pc)\b",
    re.IGNORECASE,
)
NET_QTY_FALLBACK_RE = re.compile(r"\b([\d.,]+)\s*(kg|g\b|mg|ml|l\b|litre?s?)\b", re.IGNORECASE)
MFG_RE = re.compile(
    r"(?:mfg|meg|mtg|manufactured|packed|mfd|pkd|m[fd]d?)[^\d]*?(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{4}[/\-.]\d{4}|[A-Za-z]{3,9}\s+\d{4}|\d{4}[/\-]\d{1,2})",
    re.IGNORECASE,
)
EXP_RE = re.compile(
    r"(?:exp|exf|expr|expiry|best\s*before|use\s*by)[^\d]*?(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{4}[/\-.]\d{4}|[A-Za-z]{3,9}\s+\d{4}|\d+\s*(?:months?|days?|years?))",
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

_MONTHS_FULL = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

# OCR glyph confusions, applied ONLY inside tightly-anchored contexts
# (amount after MRP, digit runs in dates) — never to free text.
_DIGIT_FIX_TABLE = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1", "S": "5", "s": "5", "B": "8"})
_MRP_AMT_RE = re.compile(
    r"((?:MRP|M\.?R\.?P\.?)\s*(?:Rs\.?|INR|₹)?\s*[:\-]?\s*)([\dOolISsB,.]+(?:\.[\dOolISsB]{1,2})?)",
    re.IGNORECASE,
)
_DATE_TOKEN_RE = re.compile(r"\b([\dIlO]{1,2})[/\-.]([\dIlO]{1,2})[/\-.]([\dIlO]{2,4})\b")
_MONTH_YEAR_RE = re.compile(r"\b([A-Za-z]{3,9})\s+(20\d{2})\b")
_NETQTY_LINE_RE = re.compile(r"net\s*(?:q?t[yl]|quantity|wt|weight|vol|content|o?t?y)", re.IGNORECASE)


def _fix_month_tokens(text: str) -> str:
    """Repair OCR-mangled month names before a year ("JANUARV 2025" -> "January 2025").

    Only fires on close matches (ratio >= 0.8) so real words ("BATCH 2025")
    pass through untouched. Pure function, never raises.
    """

    def _rep(m: re.Match) -> str:
        word, year = m.group(1), m.group(2)
        if any(word.lower() == mth.lower() for mth in _MONTHS_FULL):
            return m.group(0)
        best = difflib.get_close_matches(word.title(), list(_MONTHS_FULL), n=1, cutoff=0.8)
        return f"{best[0]} {year}" if best else m.group(0)

    try:
        return _MONTH_YEAR_RE.sub(_rep, text)
    except Exception:
        return text


def _fix_qty_units(text: str) -> str:
    """Repair unit confusions, but ONLY on net-quantity lines ("500 9" -> "500 g").

    Line-scoped so counts like "Pack of 9" are never touched. Never raises.
    """
    try:
        out = []
        for ln in text.splitlines():
            if _NETQTY_LINE_RE.search(ln):
                ln = re.sub(r"(?<=\d)\s*9\b", " g", ln)
                ln = re.sub(r"(?<=\d)\s*q\b", " g", ln, flags=re.IGNORECASE)
            out.append(ln)
        return "\n".join(out)
    except Exception:
        return text


def _fix_mrp_digits(text: str) -> str:
    """Repair digit confusions inside MRP amounts ("Rs. 12O" -> "Rs. 120").

    Requires at least two real digits in the amount so stray letters never
    fabricate a price. Never raises.
    """
    try:

        def _rep(m: re.Match) -> str:
            raw = m.group(2)
            if sum(c.isdigit() for c in raw) < 2:
                return m.group(0)
            return m.group(1) + raw.translate(_DIGIT_FIX_TABLE)

        return _MRP_AMT_RE.sub(_rep, text)
    except Exception:
        return text


def _fix_date_tokens(text: str) -> str:
    """Repair digit confusions inside date-like runs ("0l/01/2025" -> "01/01/2025").

    Separators are normalized to "/" (a format _parse_date already handles).
    Tokens that are not all-digits after repair are left alone. Never raises.
    """
    try:

        def _rep(m: re.Match) -> str:
            parts = [m.group(1).translate(_DIGIT_FIX_TABLE), m.group(2).translate(_DIGIT_FIX_TABLE)]
            year = m.group(3).translate(_DIGIT_FIX_TABLE)
            if not all(p and all(c.isdigit() for c in p) for p in (*parts, year)):
                return m.group(0)
            return f"{parts[0]}/{parts[1]}/{year}"

        return _DATE_TOKEN_RE.sub(_rep, text)
    except Exception:
        return text


def normalize_ocr_text(text: str) -> str:
    """Conservative OCR-error repair before field extraction. Idempotent, never raises."""
    try:
        text = _fix_month_tokens(text)
        text = _fix_qty_units(text)
        text = _fix_mrp_digits(text)
        text = _fix_date_tokens(text)
        return text
    except Exception:
        return text


def _parse_date(s: str) -> date | None:
    s = s.strip()
    # Repair OCR-glued dates: "0101/2025" -> "01/01/2025".
    m = re.fullmatch(r"(\d{2})(\d{2})/(\d{4})", s)
    if m:
        s = f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
    # Month names print uppercase on packs ("JAN 2025") but strptime %b/%B
    # wants title case — retry normalized.
    for cand in (s, s.title()):
        for fmt in DATE_FMTS:  # label dates are naive wall-dates by nature (no tz)
            try:
                return datetime.strptime(cand, fmt).date()  # noqa: DTZ007
            except ValueError:
                continue
    return None


def _norm_num(s: str) -> float | None:
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


_NER_NLP = None
_NER_TRIED = False


def _ner_model():
    """Cached load of models/lmpc_ner. None when spaCy/model absent — never raises."""
    global _NER_NLP, _NER_TRIED
    if _NER_NLP is not None or _NER_TRIED:
        return _NER_NLP
    _NER_TRIED = True
    try:
        import os
        from pathlib import Path

        import spacy  # type: ignore

        override = os.environ.get("SPACY_NER_PATH")
        candidates = [Path(override)] if override else []
        candidates.append(Path(__file__).resolve().parents[3] / "models" / "lmpc_ner")
        for cand in candidates:
            if cand and (cand / "config.cfg").exists():
                _NER_NLP = spacy.load(str(cand))
                break
    except Exception:
        _NER_NLP = None
    return _NER_NLP


def _ner_refine(text: str, decl: ProductDeclaration) -> ProductDeclaration:
    nlp = _ner_model()
    if nlp is None or not (text or "").strip():
        return decl
    try:
        doc = nlp(text)
    except Exception:
        return decl
    vals: dict[str, str] = {}
    for ent in doc.ents:
        vals.setdefault(ent.label_, ent.text)
    try:
        import dataclasses as _dc

        patch: dict = {}
        if decl.mrp is None and "MRP" in vals:
            m = re.search(r"[\d,]+(?:\.\d{1,2})?", vals["MRP"])
            v = _norm_num(m.group(0)) if m else None
            if v:
                patch["mrp"] = v
        if (decl.net_quantity_value is None or not decl.net_quantity_unit) and "NET_QTY" in vals:
            m = re.search(r"([\d.,]+)\s*(kg|g|mg|ml|l|cm|pcs?|nos?)\b", vals["NET_QTY"], re.IGNORECASE)
            if m:
                v = _norm_num(m.group(1))
                if v:
                    patch["net_quantity_value"] = v
                    patch["net_quantity_unit"] = m.group(2).lower().rstrip("s")
        if decl.mfg_date is None and "MFG_DATE" in vals:
            m = re.search(
                r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\w+\s+\d{4}|\d{4}[/\-]\d{1,2})",
                vals["MFG_DATE"],
            )
            d = _parse_date(m.group(1)) if m else None
            if d:
                patch["mfg_date"] = d
        if decl.expiry_date is None and "EXP_DATE" in vals:
            m = re.search(r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{4}[/\-]\d{1,2})", vals["EXP_DATE"])
            d = _parse_date(m.group(1)) if m else None
            if d:
                patch["expiry_date"] = d
        if decl.manufacturer_name is None and "MANUFACTURER" in vals:
            patch["manufacturer_name"] = vals["MANUFACTURER"][:160]
        if decl.consumer_care is None and "CARE" in vals:
            patch["consumer_care"] = vals["CARE"][:300]
        return _dc.replace(decl, **patch) if patch else decl
    except Exception:
        return decl


def extract_fields(ocr_text: str) -> ProductDeclaration:
    text = normalize_ocr_text(ocr_text or "")
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

    # Heuristic: generic name = first text line with real wording. OCR often
    # leads with page furniture (numbered badges like "1", rules, stray
    # punctuation), so skip lines without at least 3 letters.
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    generic = next((ln[:120] for ln in lines if sum(c.isalpha() for c in ln) >= 3), None)
    addr_lines = [ln for ln in lines if ADDRESS_HINT_RE.search(ln)]
    mfr_name = addr_lines[0][:160] if addr_lines else None
    mfr_addr = "; ".join(addr_lines[:2])[:300] if addr_lines else None

    # Optional spaCy NER refinement (CPU): fills fields the regex missed using
    # models/lmpc_ner trained by ml/train_ner.py. Never overrides a regex hit
    # (regex is precise on standard formats); never raises — regex-only fallback.
    decl = _ner_refine(
        text,
        ProductDeclaration(
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
        ),
    )

    return decl
