"""Hybrid regex (+ optional spaCy) field extraction — CPU-only, no GPU/torch required."""

from __future__ import annotations

import difflib
import re
from datetime import date, datetime

from app.services.layout import build_lines, find_anchor, rows_below
from app.services.rule_engine import ProductDeclaration

MRP_RE = re.compile(
    r"(?:MRP|M\.?R\.?P\.?|maximum\s*retail\s*price|retail\s*price|max[a-z]{2,5}\s+retail\s+price)"
    r"[\s()\-–—|]{0,8}(?:Rs\.?|INR|₹|%)?[\s()\-–—|]{0,8}:?\s*(?:Rs\.?|INR|₹|%)?\s*"
    r"([\d, ]+(?:\.\d{1,2})?)(?![\dA-Za-z])",
    re.IGNORECASE,
)
INCL_TAXES_RE = re.compile(r"incl.*?o[ft]\W*all\W*tax", re.IGNORECASE)
NET_QTY_RE = re.compile(
    r"(?:net|det|nct)\s*(?:q?t[yl]|quantity|wt|weight|vol|volume|content|o?t?y)[^\d]*([\d.,]+)\s*(kg|g|mg|ml|l|litre?s?|cm|m|nos?|pcs?|pc|units?)\b",
    re.IGNORECASE,
)
NET_QTY_FALLBACK_RE = re.compile(r"\b([\d.,]+)\s*(kg|g\b|mg|ml|l\b|litre?s?|units?)\b", re.IGNORECASE)
MFG_RE = re.compile(
    r"(?:mfg|meg|mtg|manufactur\w*|packed|mfd|pkd|m[fd]d?)[^\d]*?(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{1,2}[/\-.][A-Za-z]{3,9}[/\-.]\d{2,4}|\d{4}[/\-.]\d{4}|[A-Za-z]{3,9}[\s\-/]+\d{2,4}|\d{4}[/\-]\d{1,2}|\d{1,2}[/\-]\d{2,4})",
    re.IGNORECASE,
)
EXP_RE = re.compile(
    r"(?:exp|exf|expr|expiry|best\s*before|use\s*by)[^\d]*?(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{1,2}[/\-.][A-Za-z]{3,9}[/\-.]\d{2,4}|\d{4}[/\-.]\d{4}|[A-Za-z]{3,9}[\s\-/]+\d{2,4}|\d+\s*(?:months?|days?|years?)|\d{1,2}[/\-]\d{2,4})",
    re.IGNORECASE,
)
# Fallback: bare dates with no keyword anchor (common when OCR drops the label word).
# 4-digit years only: nutrition tables ("8/9/10.11") constantly yield fake short
# dates, and anchored patterns already cover MM/YY forms. The \d{4}/\d{4} glued
# form stays ("2309/2025" = "23/09/2025" with one slash dropped by OCR — the
# glued-date repair in _parse_date recovers it); its 19xx/20xx second half
# keeps dotted nutrition runs out. Never matches prices.
BARE_DATE_RE = re.compile(
    r"\b(\d{1,2}[/\-.]\d{1,2}[/\-.](?:19|20)\d{2}|\d{1,2}[/\-](?:19|20)\d{2}" r"|\d{4}[/\-](?:19|20)\d{2})\b"
)
CARE_RE = re.compile(
    r"(?:(?:customer|consumer)\s*(?:care|service|support|[a-z]?are\b)|helpline|toll\s*free)[\s\S]{0,300}?([\w+\-.]+ ?@{1,2} ?[a-z\d\-.]+ ?\.[a-z]{2,}|\+?91[\s\-]*\d[\d\s\-]{4,}|1800[\s\-]*\d[\d\s\-]*)",
    re.IGNORECASE,
)
# Bare-contact fallback: a toll-free number or email is unambiguous — neither
# ever prints spuriously — so accept it even when its heading was mangled
# ("CUSTOMER SERVICE" OCR'd badly, anchor dropped). Tried only after CARE_RE.
# "@@" tolerates the common double-print OCR glitch ("heip@@bortt.com").
_BARE_CONTACT_RE = re.compile(
    r"[\w+\-.]+ ?@{1,2} ?[a-z\d\-.]+ ?\.[a-z]{2,}|1800[\s\-]*\d[\d\s\-]{4,}", re.IGNORECASE
)
ORIGIN_RE = re.compile(
    r"(?:country\s*o[ft]\s*(?:origin|ongin)|made\s*in)\s*[:\-]?\s*([A-Za-z ]{2,30})",
    re.IGNORECASE,
)
# Maker-block anchor ("MANUFACTURED BY: Acme" / "Mfd by ..." / "Regd Office").
# Phase C: anchor-led capture beats keyword skating for multi-line addresses.
_MFR_ANCHOR_RE = re.compile(
    r"\b(manufactured|manufacture|mfd|mktd|marketed|packed)\s*by\b"
    r"|\bmfd\.?\s*for\b"
    r"|\bregd\.?\s*office\b|\bregistered\s*office\b",
    re.IGNORECASE,
)
_MFR_ADDR_START_RE = re.compile(r"^(plot|gat|sr\.?|s\.?|no\.?|address)\b", re.IGNORECASE)
# A bare 6-digit run is usually a barcode, not a pin code: only trust it next
# to a real address word.
_ADDRESS_WORD_RE = re.compile(
    r"\b(plot|street|road|sector|nagar|enclave|colony|vihar|town|city|village|district"
    r"|works|factory|office|park|estate|area|mumbai|delhi|india|chennai|kolkata|pune"
    r"|bengaluru|bangalore|hyderabad|ahmedabad|jaipur|lucknow|kanpur|nagpur|indore"
    r"|bhopal|patna|rohtak|gurugram|gurgaon|noida|kochi|coimbatore|agra|meerut|surat"
    r"|rajkot|amritsar|ranchi|guwahati)\b",
    re.IGNORECASE,
)
_PIN_RE = re.compile(r"\b\d{6}\b")
# Bare declaration headings carry no value ("NET QUANTITY", "MAXIMUM RETAIL
# PRICE" alone on a line) — never the product name.
_LONE_LABEL_RE = re.compile(
    r"^(net\s*(qty|quantity|wt|weight|vol|volume)?|mrp|m\.?r\.?p\.?|maximum\s*retail\s*price"
    r"|mfg|exp|expiry|batch(\s*no\.?)?|lot(\s*no\.?)?|use\s*by|best\s*before"
    r"|month.*year|contents)\s*[:\-]?\s*$",
    re.IGNORECASE,
)
# Brand-licence boilerplate is never the product name ("under brand licence
# from Patanjali Ayurved Ltd").
_GENERIC_SKIP_RE = re.compile(
    r"\b(store|storage|dispose|litter|recycle|recycling|keep|dry place|do not|conserver"
    r"|lot|batch|use\s*by|best\s*before|contents|ingredients|nutritional?"
    r"|brand\s*licen[sc]e|under\s*brand)\b",
    re.IGNORECASE,
)
# Nutrition context: values here are serving facts, never the net quantity or
# pack dates ("6.6g sugar", "Valeurs nutritionnelles pour 100g", "72 mg/serve").
# Roots, not whole words: OCR mangles endings ("nutricondles", "energiçones").
_NUTRITION_RE = re.compile(
    r"sugar|sucr[ao]|protein|proté|prodies|energy|énerg|nutri|valeur|velour|voleur"
    r"|kcal|kaul|lipide|carbo|calciu|colium|per\s*100|pour\s*100|/\s*serve"
    r"|per\s*serve|\bservings?\b|contains|ingredients?|ingrédients?"
    r"|milk|water\b|oil|butter|tomato|onion|flour|\bsalt\b|honey|recipe|\bcook\b"
    r"|\bserve\b|serving|\bcup\b|\btbsp\b|\btsp\b",
    re.IGNORECASE,
)
# Bare rupee amounts ("₹ 120") without an MRP keyword. A lone ₹ glyph is often
# OCR noise (Arabic-script logos misread), so a price cue must sit nearby.
_MRP_RUPEE_RE = re.compile(r"₹\s*([\d,]+(?:\.\d{1,2})?)")
_MRP_RUPEE_CUE_RE = re.compile(r"mrp|price|\brs\b|inclusive", re.IGNORECASE)

DATE_FMTS = (
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%d/%m/%y",
    "%d/%b/%Y",
    "%d/%b/%y",
    "%d-%b-%Y",
    "%d-%b-%y",
    "%d.%b.%Y",
    "%Y-%m-%d",
    "%b %Y",
    "%B %Y",
    "%b %y",
    "%B %y",
    "%m/%Y",
    "%m-%Y",
    "%m/%y",
    "%m-%y",
)

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

# Unit-sale-price and lot cues: a standalone amount line carrying these is
# NEVER the MRP (multi-line MRP must skip it).
_MRP_POISON_RE = re.compile(r"\b(usp|unit\s*(sale\s*)?price|per\s*g\b|lot|batch)\b", re.IGNORECASE)
_MRP_LINE_AMT_RE = re.compile(r"^\s*(?:Rs\.?|INR|₹)?\s*([\d, ]+(?:\.\d{1,2})?)\s*(?:/-\s*)?$")
_MRP_KEYWORD_RE = re.compile(r"MRP|M\.?R\.?P\.?|maximum\s*retail\s*price", re.IGNORECASE)


def _multiline_mrp(lines: list[str]) -> float | None:
    """MRP keyword and amount on different lines, either order.

    Forward: "MRP Rs." / "Rs. 50.00". Backward: "₹50.00:" ... "MRP Rs."
    (Suhana-style). Poisoned lines (USP, lot, batch) never count: for the
    backward search only the text before the first poison cue is used.
    """
    for i, ln in enumerate(lines):
        if not _MRP_KEYWORD_RE.search(ln):
            continue
        if re.search(r"[\d,]+\.\d|\b\d{2,}\b", ln):
            continue  # amount already on the keyword line: single-line handles it
        for nxt in lines[i + 1 : i + 3]:
            if not nxt.strip() or _MRP_POISON_RE.search(nxt):
                continue
            m = _MRP_LINE_AMT_RE.match(nxt)
            if m:
                return _norm_num(m.group(1))
        for prv in lines[max(0, i - 2) : i][::-1]:
            left = _MRP_POISON_RE.split(prv)[0]
            if not left.strip():
                continue
            m = re.search(r"(?:Rs\.?|INR|₹)?\s*([\d, ]+(?:\.\d{1,2})?)\s*:?\s*$", left)
            if m and re.search(r"(?:Rs\.?|INR|₹)", left):
                return _norm_num(m.group(1))
    return None


# OCR glyph confusions, applied ONLY inside tightly-anchored contexts
# (amount after MRP, digit runs in dates) — never to free text.
_DIGIT_FIX_TABLE = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1", "S": "5", "s": "5", "B": "8"})
_MRP_AMT_RE = re.compile(
    r"((?:MRP|M\.?R\.?P\.?|maximum\s*retail\s*price|retail\s*price|max[a-z]{2,5}\s+retail\s+price)"
    r"[\s()\-–—|]{0,8}(?:Rs\.?|INR|₹|%)?[\s()\-–—|]{0,8}:?\s*(?:Rs\.?|INR|₹|%)?\s*)"
    r"([\dOolISsB,. ]+(?:\.[\dOolISsB]{1,2})?)(?![A-Za-z])",
    re.IGNORECASE,
)
_DATE_TOKEN_RE = re.compile(r"\b([\dIlO]{1,2})[/\-.]([\dIlO]{1,2})[/\-.]([\dIlO]{2,4})\b")
_MONTH_YEAR_RE = re.compile(r"\b([A-Za-z]{3,9})\s+(20\d{2})\b")
_NETQTY_LINE_RE = re.compile(
    r"(?:net|det|nct)\s*(?:q?t[yl]|quantity|wt|weight|vol|volume|content|o?t?y)", re.IGNORECASE
)


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
                ln = re.sub(r"(?<=\d)\s*(unt|unlt|unl|nit)\b", " unit", ln, flags=re.IGNORECASE)
            # Digit-glued unit typos ("250 mie", "500 mle", "500 Mla") occur on any line;
            # the digit adjacency makes the repair safe outside net lines too.
            ln = re.sub(r"(?<=\d)\s*(mla|mle|mie|rnI|m1)\b", " ml", ln, flags=re.IGNORECASE)
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
            parts = [
                m.group(1).translate(_DIGIT_FIX_TABLE),
                m.group(2).translate(_DIGIT_FIX_TABLE),
            ]
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
    # Month names print joined by hyphens/slashes too ("MAY-24", "JAN/2025").
    # Skip when the string is already a full day-month-year ("30/AUG/26"):
    # rewriting its separators would destroy a parseable date.
    if not re.fullmatch(r"\d{1,2}[/\-.][A-Za-z]{3,9}[/\-.]\d{2,4}", s):
        s = re.sub(r"(?<=[A-Za-z])[-/](?=\d)", " ", s)
    # Month names print uppercase on packs ("JAN 2025") but strptime %b/%B
    # wants title case — retry normalized.
    for cand in (s, s.title()):
        for fmt in DATE_FMTS:  # label dates are naive wall-dates by nature (no tz)
            try:
                return datetime.strptime(cand, fmt).date()  # noqa: DTZ007
            except ValueError:
                continue
    # Last resort: certain month+year with a mangled day ("0/08/2026" — OCR
    # dropped a digit). Rule 6(1)(d) needs only month and year: day defaults
    # to the 1st rather than losing the declaration. 2-digit years follow
    # strptime %y (00-68 -> 2000s, 69-99 -> 1900s).
    m = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", s)
    if m:
        try:
            mon, yr = int(m.group(2)), int(m.group(3))
        except ValueError:
            return None
        if yr < 100:
            yr += 2000 if yr <= 68 else 1900
        if 1 <= mon <= 12 and yr >= 1900:
            try:
                return date(yr, mon, 1)
            except ValueError:
                return None
    return None


def _norm_num(s: str) -> float | None:
    try:
        return float(s.replace(",", "").replace(" ", ""))
    except ValueError:
        return None


def _qty_num(raw: str) -> float | None:
    """Parse a quantity number, repairing barcode-glue ("0022250 ml" -> 250).

    Tesseract glues barcode digits onto the true value ("890720 00222" +
    "50 ml"). Genuine prints never carry leading zeros, so strip them; if the
    run is still implausibly long, the true value trails the glued digits.
    """
    s = raw.replace(",", "").replace(" ", "")
    m = re.fullmatch(r"0+(\d+(?:\.\d+)?)", s)
    if m:
        s = m.group(1)
        head, dot, tail = s.partition(".")
        if len(head) > 4:
            head = head[-3:]
        s = head + (dot + tail if dot else "")
    try:
        v = float(s)
    except ValueError:
        return None
    return v if v > 0 else None


def _extract_qty(text: str) -> tuple[float | None, str | None]:
    """Ranked net-quantity candidates. Anchored > e-marked > plain; nutrition
    windows ("6.6g sugar", "per 100g") never count. First-seen wins ties.

    Candidates are scoped to an 80/40-char window around the match: glued OCR
    (missing line breaks) would otherwise let one nutrition word poison a
    genuine "250 ml" sitting far away on the same mega-line. When the text
    carries a nutrition table at all, unanchored candidates additionally need
    an e-mark — bare table values ("33g" saturated fat) are never net quantity.
    """
    table = bool(
        re.search(
            r"nutrition(al)?\s+information|per\s*100\s*g|%\s*RDA|valeurs?\s+nutrition", text, re.IGNORECASE
        )
    )
    cands: list[tuple[int, int, float, str]] = []  # (score, order, value, unit)
    order = 0
    for m in NET_QTY_RE.finditer(text):
        v = _qty_num(m.group(1))
        if v:
            cands.append((3, order, v, m.group(2).lower().rstrip("s")))
            order += 1
    for m in NET_QTY_FALLBACK_RE.finditer(text):
        win = text[max(0, m.start() - 80) : m.end() + 40]
        if _NUTRITION_RE.search(win):
            continue
        if table and not re.search(r"\be\b", win):
            continue
        v = _qty_num(m.group(1))
        if v:
            score = 2 if re.search(r"\be\b", win) else 0
            cands.append((score, order, v, m.group(2).lower().rstrip("s")))
            order += 1
    if not cands:
        return None, None
    cands.sort(key=lambda t: (-t[0], t[1]))
    return cands[0][2], cands[0][3]


def _looks_like_measurement(ln: str) -> bool:
    """Line is basically just a measurement ("250 ml e", "Bo 2 250 ml"): strip
    unit words, digits and punctuation — ≤3 letters left means no product name.
    Keeps real names ("Atta", "Wheat Biscuits") untouched."""
    s = re.sub(
        r"\b(kg|g|mg|ml|l|litre?s?|cm|m|nos?|pcs?|pc|units?|e)\b",
        "",
        ln,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"[\d.,/\-+×%()®™©°\s]", "", s)
    return sum(c.isalpha() for c in s) <= 2


def _dedupe_segments(parts: list[str]) -> list[str]:
    """Drop consecutive duplicate address segments (OCR repeats lines)."""
    out: list[str] = []
    for p in parts:
        if not out or out[-1] != p:
            out.append(p)
    return out


def _extract_manufacturer(lines: list[str]) -> tuple[str | None, str | None]:
    """Anchor-led maker block, else address-word lines (pin needs a companion
    word — bare 6-digit runs are barcodes)."""
    stop = re.compile(
        r"customer|consumer|care|helpline|net\s*q|mrp|mfg|exp|batch|fssai|lic\.?\s*no",
        re.IGNORECASE,
    )
    for i, ln in enumerate(lines):
        m = _MFR_ANCHOR_RE.search(ln)
        if not m:
            continue
        if re.search(r"\bas\s+per\s*$", ln[: m.start()], re.IGNORECASE):
            continue  # "Address as per Regd. Office" points elsewhere, not a declaration
        tail = ln[m.end() :].strip(" :-\t")
        pre = ln[: m.start()].strip(" ,:-\t")
        if tail and not _MFR_ADDR_START_RE.search(tail):
            block = ([tail] if tail else []) + [x.strip() for x in lines[i + 1 : i + 5] if x.strip()]
        else:
            # Address starts immediately (or empty tail): the company name may
            # precede the anchor ("TTK PRESTIGE LTD., REGISTERED OFFICE : ...").
            cand = pre if pre and not stop.search(pre) and len(pre) > 3 else ""
            block = ([cand] if cand else []) + ([tail] if tail else [])
            block += [x.strip() for x in lines[i + 1 : i + 5] if x.strip()]
        kept: list[str] = []
        for b in block:
            if kept and stop.search(b):
                break
            kept.append(b)
        if kept and kept[0]:
            name = kept[0][:160]
            addr = "; ".join(b.rstrip(" ,;:-").strip() for b in _dedupe_segments(kept[1:4]))[:300] or None
            return name, addr
    addr_lines = [ln for ln in lines if _ADDRESS_WORD_RE.search(ln)]
    mfr_name = addr_lines[0][:160] if addr_lines else None
    mfr_addr = "; ".join(_dedupe_segments(addr_lines[:2]))[:300] if addr_lines else None
    return mfr_name, mfr_addr


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
            # The NER model fires on bare small numbers ("5 PP" recycling mark):
            # require a price cue inside the entity — or on its line, for forms
            # like "MRP (Rs.): 14.00" where the entity is just the amount.
            # (A lone glyph-noise cue like an OCR-hallucinated Rs. never counts.)
            ent = vals["MRP"]
            m = re.search(r"[\d,]+(?:\.\d{1,2})?", ent)
            v = _norm_num(m.group(0)) if m else None
            line = next((ln for ln in text.splitlines() if ent and ent in ln), "")
            if v and (
                re.search(r"(rs|inr|₹|mrp|price)", ent, re.IGNORECASE)
                or (
                    re.search(r"(mrp|price|\brs\b|inclusive)", line, re.IGNORECASE)
                    and not _MRP_POISON_RE.search(line)
                )
            ):
                patch["mrp"] = v
        if (decl.net_quantity_value is None or not decl.net_quantity_unit) and "NET_QTY" in vals:
            m = re.search(
                r"([\d.,]+)\s*(kg|g|mg|ml|l|cm|pcs?|nos?|units?)\b",
                vals["NET_QTY"],
                re.IGNORECASE,
            )
            if m:
                v = _norm_num(m.group(1))
                if v:
                    patch["net_quantity_value"] = v
                    patch["net_quantity_unit"] = m.group(2).lower().rstrip("s")
        if decl.mfg_date is None and "MFG_DATE" in vals:
            m = re.search(
                r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\w+\s+\d{4}|\d{4}[/\-]\d{1,2}|\d{1,2}[/\-]\d{2,4})",
                vals["MFG_DATE"],
            )
            d = _parse_date(m.group(1)) if m else None
            if d:
                patch["mfg_date"] = d
        if decl.expiry_date is None and "EXP_DATE" in vals:
            m = re.search(
                r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{4}[/\-]\d{1,2}|\d{1,2}[/\-]\d{2,4})",
                vals["EXP_DATE"],
            )
            d = _parse_date(m.group(1)) if m else None
            if d:
                patch["expiry_date"] = d
        if decl.manufacturer_name is None and "MANUFACTURER" in vals:
            # The NER model fires on any capitalized run ("A COOL, MICRENIC AND"):
            # require an address word and sane digit load — trained maker spans
            # are full address lines, so this keeps recall while killing
            # furniture and barcode-digit entities.
            ent = vals["MANUFACTURER"]
            digits = sum(c.isdigit() for c in ent)
            alpha = sum(c.isalpha() for c in ent)
            if _ADDRESS_WORD_RE.search(ent) and digits <= alpha:
                patch["manufacturer_name"] = ent[:160]
        # The rule needs a *contact*, not just the words "customer care":
        # accept the NER span only if it carries email/phone/toll-free
        # evidence, else a heading alone would fake a PASS.
        if (
            decl.consumer_care is None
            and "CARE" in vals
            and re.search(
                r"[\w+\-.]+ ?@{1,2} ?[a-z\d\-.]+ ?\.[a-z]{2,}|\+?91[\s\-]*\d[\d\s\-]{4,}|1800[\s\-]*\d[\d\s\-]*",
                vals["CARE"],
                re.IGNORECASE,
            )
        ):
            patch["consumer_care"] = vals["CARE"][:300]
        return _dc.replace(decl, **patch) if patch else decl
    except Exception:
        return decl


def extract_fields(ocr_text: str) -> ProductDeclaration:
    text = normalize_ocr_text(ocr_text or "")
    m = MRP_RE.search(text)
    mrp_val = _norm_num(m.group(1)) if m else None
    if mrp_val is None:
        mrp_val = _multiline_mrp(text.splitlines())
    if mrp_val is None:
        for mr in _MRP_RUPEE_RE.finditer(text):
            win = text[max(0, mr.start() - 40) : mr.end() + 10]
            if _MRP_RUPEE_CUE_RE.search(win):
                mrp_val = _norm_num(mr.group(1))
                break
    incl_taxes = bool(INCL_TAXES_RE.search(text))

    qty_val, qty_unit = _extract_qty(text)
    if qty_unit == "litre":
        qty_unit = "l"

    m = MFG_RE.search(text)
    mfg = _parse_date(m.group(1)) if m else None
    m = EXP_RE.search(text)
    exp_raw = m.group(1) if m else None
    exp: date | None = None
    if exp_raw:
        exp = _parse_date(exp_raw)  # relative durations ("12 months") -> left None (needs mfg anchor)
    if exp is not None and mfg is not None and exp <= mfg and m:
        # The anchor grabbed the mfg date on a paired row ("Mfg X, Exp Y"):
        # take a later date from the SAME line as the true expiry.
        ln = text.splitlines()[text.count("\n", 0, m.start())]
        for cand in re.findall(
            r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|[A-Za-z]{3,9}[\s\-/]+\d{2,4}|\d{1,2}[/\-]\d{2,4}", ln
        ):
            d = _parse_date(cand)
            if d is not None and d > mfg:
                exp = d
                break
    if mfg is None or exp is None:
        # Keyword anchor OCR-mangled (e.g. "Mtg"/"Expr") or dropped: fall back to
        # bare 4-digit-year dates in reading order — first = mfg, second = expiry.
        # Nutrition lines are skipped (their dotted tables fake short dates).
        bare: list[date] = []
        for ln in text.splitlines():
            if _NUTRITION_RE.search(ln):
                continue
            bare.extend(b for b in (_parse_date(x) for x in BARE_DATE_RE.findall(ln)) if b)
        if mfg is None and bare:
            mfg = bare[0]
        if exp is None and len(bare) >= 2:
            exp = bare[1]
    if mfg is None:
        # Second chance: month-year token on a line mentioning a
        # manufacture-ish word whose anchor itself got mangled
        # ("Manuiacture : December 2025"). Same-line only, strict match.
        for ln in text.splitlines():
            words = re.findall(r"[A-Za-z]{4,}", ln)
            if not any(
                difflib.get_close_matches(
                    w.title(),
                    [
                        "Manufacture",
                        "Manufactured",
                        "Manufacturing",
                        "Packing",
                        "Packed",
                        "Mfg",
                    ],
                    n=1,
                    cutoff=0.85,
                )
                for w in words
            ):
                continue
            m = re.search(r"([A-Za-z]{3,9}[\s\-/]+\d{2,4}|\d{1,2}[/\-]\d{2,4})", ln)
            if m:
                cand = _parse_date(m.group(1))
                if cand:
                    mfg = cand
                    break

    m = CARE_RE.search(text)
    care = m.group(0).strip()[:300] if m else None
    if care is None:
        bm = _BARE_CONTACT_RE.search(text)
        care = bm.group(0).strip()[:300] if bm else None

    m = ORIGIN_RE.search(text)
    origin = m.group(1).strip() if m else None
    if origin and re.fullmatch(r"in[cd][iae]a?", origin, re.IGNORECASE):
        origin = "India"  # OCR drops the 'd' ("inca", "indla") — still India
    imported = origin is not None and origin.lower() not in ("india",)

    # Heuristic: generic name = first text line with real wording that is NOT
    # itself a declaration (MRP / net qty / dates / care / origin / tax note).
    # OCR often leads with page furniture (numbered badges like "1", rules, stray
    # punctuation), so skip lines without at least 3 letters.
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    def _is_declaration_line(ln: str) -> bool:
        return bool(
            MRP_RE.search(ln)
            or NET_QTY_RE.search(ln)
            or MFG_RE.search(ln)
            or EXP_RE.search(ln)
            or CARE_RE.search(ln)
            or ORIGIN_RE.search(ln)
            or INCL_TAXES_RE.search(ln)
            or _MFR_ANCHOR_RE.search(ln)
            or re.search(r"\b(model(\s*(no|name))?|part\s*code|colou?r)\b", ln, re.IGNORECASE)
        )

    generic_labeled: str | None = None
    for i, ln in enumerate(lines):
        m = re.search(r"(?:generic|common)\s*name\s*[:\-]\s*(.+)", ln, re.IGNORECASE)
        if m and m.group(1).strip():
            generic_labeled = m.group(1).strip()[:120]
            break
        m = re.match(r"^\s*contents\s*:\s*(.+?)\s*$", ln, re.IGNORECASE)
        if m and m.group(1).strip():
            val = m.group(1).strip()
            if not (_is_declaration_line(val) or _looks_like_measurement(val) or _LONE_LABEL_RE.match(val)):
                generic_labeled = val[:120]
                break
    candidates = [
        ln[:120]
        for ln in lines
        if sum(c.isalpha() for c in ln) >= 3
        and len(ln) <= 160  # glued OCR mega-lines are never a product name
        and any(len(t) >= 3 for t in re.findall(r"[A-Za-z]+", ln))  # real word, not shards
        and not _is_declaration_line(ln)
        and not _GENERIC_SKIP_RE.search(ln)
        and not _LONE_LABEL_RE.match(ln.strip())
        and not _looks_like_measurement(ln)
    ]
    # Labeled generic wins ("Generic Name : Smart Watch"); else the first
    # substantial line ("Wee!" shards and brand shouts sit above the real
    # name); fall back to the first candidate ("Atta", "Tea").
    generic = generic_labeled
    if generic is None:
        generic = next((ln for ln in candidates if sum(c.isalpha() for c in ln) >= 8), None)
    if generic is None and candidates:
        generic = candidates[0]
    mfr_name, mfr_addr = _extract_manufacturer(lines)

    # Provenance (Phase D): regex hits are "read" straight off the text.
    # Optional spaCy NER refinement (CPU) fills the gaps below and is marked
    # "inferred": models/lmpc_ner trained by ml/train_ner.py. Never overrides
    # a regex hit (regex is precise on standard formats); never raises.
    _TRACKED = (
        "manufacturer_name",
        "manufacturer_address",
        "generic_name",
        "net_quantity_value",
        "net_quantity_unit",
        "mrp",
        "mfg_date",
        "expiry_date",
        "consumer_care",
        "country_of_origin",
    )
    _regex_vals = {
        "manufacturer_name": mfr_name,
        "manufacturer_address": mfr_addr,
        "generic_name": generic if generic and len(generic) > 2 else None,
        "net_quantity_value": qty_val,
        "net_quantity_unit": qty_unit,
        "mrp": mrp_val,
        "mfg_date": mfg,
        "expiry_date": exp,
        "consumer_care": care,
        "country_of_origin": origin,
    }
    sources: dict[str, str] = {k: "read" for k, v in _regex_vals.items() if v is not None}
    if incl_taxes:
        sources["mrp_includes_taxes"] = "read"
    if imported:
        sources["is_imported"] = "read"
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
    for _k in _TRACKED:
        if getattr(decl, _k) is not None and _k not in sources:
            sources[_k] = "inferred"  # spaCy NER filled a regex gap

    # Gazetteer canonicalization (deterministic, offline): repair a mangled
    # maker name ("Hindustan Uniiever" -> "Hindustan Unilever") or fill a
    # missing one from OCR lines. Names only — never numbers/dates/MRP.
    # Fidelity guard: never rewrite an exact read — if the extracted name
    # already contains the canonical hit ("Patanjali Foods Limited" contains
    # "Patanjali Foods"), the OCR was right and the gazetteer stays out.
    # Never raises; the raw OCR text stays on the scan for audit.
    try:
        import dataclasses as _dc

        from app.services.gazetteer import fill_manufacturer, fix_manufacturer

        if decl.manufacturer_name:
            fixed, _score = fix_manufacturer(decl.manufacturer_name)
            if fixed and fixed.lower() not in decl.manufacturer_name.lower():
                decl = _dc.replace(decl, manufacturer_name=fixed)
                sources["manufacturer_name"] = "inferred"
        else:
            found, _score = fill_manufacturer(text)
            if found:
                decl = _dc.replace(decl, manufacturer_name=found[:160])
                sources["manufacturer_name"] = "inferred"
    except Exception:  # noqa: S110 — gazetteer is advisory; regex result always survives
        pass

    import dataclasses as _dc2

    return _dc2.replace(decl, field_sources=sources)


def apply_confidence_sources(decl: ProductDeclaration, ocr_confidence: float | None) -> ProductDeclaration:
    """Downgrade "read" to "uncertain" on weak reads (<60% OCR confidence).

    A regex hit on a garbled read deserves a verify badge, not a read badge.
    Inferred/AI/attested marks are left alone. Pure function, never raises.
    """
    try:
        import dataclasses as _dc

        if ocr_confidence is None or float(ocr_confidence) >= 60:
            return decl
        downgraded = {k: ("uncertain" if v == "read" else v) for k, v in (decl.field_sources or {}).items()}
        return _dc.replace(decl, field_sources=downgraded)
    except Exception:
        return decl


_DATE_SHAPE_RE = re.compile(
    r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{4}[/\-]\d{1,2}|\d{1,2}[/\-]\d{2,4}"
    r"|[A-Za-z]{3,9}[\s\-/]+\d{2,4}|\d{4}[/\-](?:19|20)\d{2}"
)
_MFG_ANCHOR_LINE_RE = re.compile(r"mfg|manufactur\w*|mfd|pkd|packed", re.IGNORECASE)
_EXP_ANCHOR_LINE_RE = re.compile(r"exp|expiry|best\s*before|use\s*by", re.IGNORECASE)
_MRP_ANCHOR_LINE_RE = re.compile(r"MRP|M\.?R\.?P\.?|maximum\s*retail\s*price", re.IGNORECASE)


def extract_fields_with_layout(ocr_text: str, boxes: list | None = None) -> ProductDeclaration:
    """extract_fields + visual-geometry rescue for fields the flat text missed.

    Rebuilt visual rows fix what OCR line-breaks break: amounts sitting below
    their keyword, date pairs glued onto one row, maker blocks in visual order.
    Only fills gaps (never overrides a flat-text hit, except the paired-date
    correction which mirrors the same-line rule). Never raises.
    """
    import dataclasses as _dc

    decl = extract_fields(ocr_text)
    try:
        lines = build_lines(boxes)
    except Exception:
        return decl
    if not lines:
        return decl
    try:
        patch: dict = {}
        if decl.mrp is None:
            i = find_anchor(lines, r"MRP|M\.?R\.?P\.?|maximum\s*retail\s*price")
            for ln in rows_below(lines, i, 2):
                if _MRP_POISON_RE.search(ln.text) or _NUTRITION_RE.search(ln.text):
                    continue
                m = _MRP_LINE_AMT_RE.match(ln.text.strip())
                if m:
                    v = _norm_num(m.group(1))
                    if v:
                        patch["mrp"] = v
                        break
        if decl.mfg_date is None or decl.expiry_date is None:
            cand_rows: list[str] = []
            for pat in (_MFG_ANCHOR_LINE_RE, _EXP_ANCHOR_LINE_RE):
                idx = -1
                for j, ln in enumerate(lines):
                    if pat.search(ln.text):
                        idx = j
                        break
                if idx >= 0:
                    cand_rows.append(lines[idx].text)
                    cand_rows.extend(ln.text for ln in rows_below(lines, idx, 1))
            seen: set[str] = set()
            parsed: list = []
            for row in cand_rows:
                if _NUTRITION_RE.search(row):
                    continue
                for tok in _DATE_SHAPE_RE.findall(row):
                    if tok in seen:
                        continue
                    seen.add(tok)
                    d = _parse_date(tok)
                    if d is not None:
                        parsed.append(d)
            mfg = decl.mfg_date
            if mfg is None and parsed:
                mfg = parsed[0]
                patch["mfg_date"] = mfg
            if decl.expiry_date is None and mfg is not None:
                for d in parsed:
                    if d > mfg:
                        patch["expiry_date"] = d
                        break
        if decl.manufacturer_name is None:
            visual = "\n".join(ln.text for ln in lines)
            name, addr = _extract_manufacturer(visual.splitlines())
            if name:
                patch["manufacturer_name"] = name
                if decl.manufacturer_address is None and addr:
                    patch["manufacturer_address"] = addr
        if not patch:
            return decl
        sources = dict(decl.field_sources or {})
        for _k in patch:
            sources.setdefault(_k, "inferred")  # layout rescued a flat-text gap
        return _dc.replace(decl, **patch, field_sources=sources)
    except Exception:
        return decl
