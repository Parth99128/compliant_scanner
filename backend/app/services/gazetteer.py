"""Gazetteer entity matching: canonicalize OCR-mangled maker/brand names.

Why not an LLM here: the matcher can only return names from the versioned
data/manufacturers.json list, so it is structurally incapable of inventing a
company — the dangerous failure mode for enforcement tooling. Deterministic,
microsecond-fast, offline, CPU-only (RapidFuzz, MIT).

Guardrails (all enforced, all unit-tested):
- manufacturer/brand/generic-name text ONLY. Never numbers, dates, MRP.
- Queries shorter than 5 letters are skipped (Levenshtein over-matches them).
- Missing name: fill from best OCR line at score >= 90.
- Present name: typo-fix at score >= 93 (stricter — never silently swap a
  confident read).
- The raw OCR text always stays on the scan record; the rule's `observed`
  field shows the canonical value. Nothing is hidden.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

FILL_CUTOFF = 90.0
FIX_CUTOFF = 93.0
MIN_QUERY_LEN = 5

_GAZETTEER_ENV = "GAZETTEER_PATH"


def _default_paths() -> list[Path]:
    root = Path(__file__).resolve().parents[3]  # backend/app/services -> repo root
    paths = [root / "data" / "manufacturers.json"]
    override = os.environ.get(_GAZETTEER_ENV)
    if override:
        paths.insert(0, Path(override))
    extra = root / "data" / "off_brands.jsonl"
    if extra.exists():
        paths.append(extra)
    return paths


@lru_cache(maxsize=1)
def _names() -> tuple[str, ...]:
    """All gazetteer names, deduplicated case-insensitively. Cached; never raises."""
    seen: set[str] = set()
    out: list[str] = []
    try:
        for path in _default_paths():
            if not path.exists():
                continue
            if path.suffix == ".jsonl":
                for line in path.read_text(encoding="utf-8").splitlines():
                    try:
                        name = str(json.loads(line).get("brand", "")).strip()
                    except (ValueError, AttributeError):
                        continue
                    if name and name.lower() not in seen:
                        seen.add(name.lower())
                        out.append(name)
            else:
                try:
                    names = json.loads(path.read_text(encoding="utf-8")).get("names", [])
                except ValueError:
                    continue
                for name in names:
                    name = str(name).strip()
                    if name and name.lower() not in seen:
                        seen.add(name.lower())
                        out.append(name)
    except Exception:  # noqa: S110 — corrupt list file means "no gazetteer", not a crash
        pass
    return tuple(out)


def reload_gazetteer() -> None:
    """Drop the cache (tests / admin refresh after editing the list)."""
    _names.cache_clear()


def match_name(query: str, cutoff: float = FILL_CUTOFF) -> tuple[str | None, float]:
    """Best gazetteer hit for a query: (canonical or None, score 0-100). Never raises.

    partial_ratio: OCR lines contain the name plus address noise
    ("Acme Foods, Plot 5, ..."), so containment scoring beats whole-string
    scoring (WRatio penalizes the extra words and misses exact hits).
    """
    try:
        from rapidfuzz import fuzz, process
    except ImportError:
        return None, 0.0
    try:
        q = " ".join((query or "").split())
        if len(q) < MIN_QUERY_LEN:
            return None, 0.0
        names = _names()
        if not names:
            return None, 0.0
        hit = process.extractOne(q, names, scorer=fuzz.partial_ratio, score_cutoff=cutoff)
        if not hit:
            return None, 0.0
        return str(hit[0]), round(float(hit[1]), 1)
    except Exception:
        return None, 0.0


def fill_manufacturer(ocr_text: str) -> tuple[str | None, float]:
    """Find a maker name in raw OCR lines (used when extraction found none)."""
    best: tuple[str | None, float] = (None, 0.0)
    try:
        for line in (ocr_text or "").splitlines():
            if len(" ".join(line.split())) < MIN_QUERY_LEN:
                continue
            name, score = match_name(line, FILL_CUTOFF)
            if score > best[1]:
                best = (name, score)
    except Exception:  # noqa: S110 — fall back to "maker not found"
        pass
    return best


def fix_manufacturer(name: str | None) -> tuple[str | None, float]:
    """Typo-fix an extracted name against the gazetteer (strict cutoff)."""
    if not name:
        return None, 0.0
    return match_name(name, FIX_CUTOFF)
