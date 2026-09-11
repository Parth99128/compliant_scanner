"""Layout-aware reading order + neighbor zones from OCR word boxes.

Tesseract's line breaks are unreliable on glued, curved or multi-column
labels (whole paragraphs arrive as one "line", or one row splits in two).
This module rebuilds *visual* lines from box geometry (y-band clustering,
x-sorted words) and answers neighbor queries the flat-text extractor cannot:

- amount on the visual row below an MRP keyword (OCR put the break elsewhere)
- date pairs sharing a visual row ("Packed On: A B" even when glued)
- maker block: visual rows below a marketed/manufactured-by anchor

All functions are pure, total (never raise), and dependency-free: boxes are
duck-typed ({text, x, y, w, h, confidence} as attrs or dict keys).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class VLine:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    conf: float  # mean word confidence, 0-100


def _box_tuple(b: object) -> tuple[str, float, float, float, float, float] | None:
    try:
        if isinstance(b, dict):
            t, x, y, w, h = (b.get(k) for k in ("text", "x", "y", "w", "h"))
            c = b.get("confidence", 0.0)
        else:
            t, x, y, w, h = (getattr(b, k) for k in ("text", "x", "y", "w", "h"))
            c = getattr(b, "confidence", 0.0)
        text = str(t or "").strip()
        x, y, w, h, c = (float(v or 0) for v in (x, y, w, h, c))
    except (TypeError, ValueError, AttributeError):
        return None
    if not text or w <= 0 or h <= 0:
        return None
    return text, x, y, w, h, c


def build_lines(boxes: list | None, y_tol_ratio: float = 0.5) -> list[VLine]:
    """Cluster word boxes into visual rows. Never raises."""
    try:
        words = [t for t in (_box_tuple(b) for b in (boxes or [])) if t]
    except Exception:
        return []
    if not words:
        return []
    try:
        med_h = sorted(w[4] for w in words)[len(words) // 2] or 1.0
    except Exception:
        return []
    tol = max(2.0, med_h * y_tol_ratio)
    rows: list[list[tuple]] = []
    for w in sorted(words, key=lambda t: t[2]):
        placed = False
        for row in rows:
            ymid = sum(t[2] + t[4] / 2 for t in row) / len(row)
            if abs((w[2] + w[4] / 2) - ymid) <= tol:
                row.append(w)
                placed = True
                break
        if not placed:
            rows.append([w])
    out: list[VLine] = []
    for row in rows:
        row = sorted(row, key=lambda t: t[1])
        x0 = min(t[1] for t in row)
        y0 = min(t[2] for t in row)
        x1 = max(t[1] + t[3] for t in row)
        y1 = max(t[2] + t[4] for t in row)
        conf = sum(t[5] for t in row) / len(row)
        out.append(VLine(" ".join(t[0] for t in row), x0, y0, x1, y1, conf))
    return sorted(out, key=lambda ln: (ln.y0, ln.x0))


def find_anchor(lines: list[VLine], pattern: str) -> int:
    """Index of the first visual line matching the regex, else -1. Never raises."""
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error:
        return -1
    for i, ln in enumerate(lines):
        try:
            if rx.search(ln.text):
                return i
        except Exception:
            continue
    return -1


def rows_below(lines: list[VLine], index: int, count: int = 3) -> list[VLine]:
    """Visual rows strictly below the anchor row (gap-tolerant, not just adjacent)."""
    if index < 0 or index >= len(lines):
        return []
    try:
        base = lines[index].y1
        below = [ln for ln in lines[index + 1 :] if ln.y0 >= base - 2]
        return below[: max(0, count)]
    except Exception:
        return []


def row_mates(lines: list[VLine], index: int) -> list[VLine]:
    """Rows vertically overlapping the anchor row (multi-column pairs)."""
    if index < 0 or index >= len(lines):
        return []
    try:
        a = lines[index]
        return [ln for j, ln in enumerate(lines) if j != index and ln.y0 <= a.y1 and ln.y1 >= a.y0]
    except Exception:
        return []
