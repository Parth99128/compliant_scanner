"""Real-photo field accuracy: extraction vs human ground truth.

Reads data/real/eval_labels.jsonl rows:
  {"image": <path>, "truth": {field: expected...}, "absent": [fields confirmed
   not visible], "notes": str}

truth keys: generic_sub (substring), net_quantity_value + net_quantity_unit,
mrp (number), mfg / exp (true = a date must be found), manufacturer_sub
(substring of name or address), consumer_care (true = contact must be found).
Fields in "absent" must NOT be extracted (specificity: no hallucinations).

    python ml/eval_real.py [--labels data/real/eval_labels.jsonl]

Prints per-photo results + per-field totals. Exit 0 always (benchmark).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.local_extract import extract_label

FIELDS = ("generic", "net_quantity", "mrp", "mfg", "exp", "manufacturer", "care")


def _norm_unit(u: str | None) -> str | None:
    return (u or "").lower().rstrip("s") or None


def score_row(decl: dict, truth: dict, absent: list[str]) -> dict[str, tuple[bool, str]]:
    """Per field -> (hit, detail)."""
    out: dict[str, tuple[bool, str]] = {}
    g = decl.get("generic_name") or ""
    if "generic_sub" in truth:
        want = str(truth["generic_sub"]).lower()
        out["generic"] = (want in g.lower(), f"got {g[:40]!r}")
    elif "generic" in absent:
        out["generic"] = (not g, f"got {g[:40]!r}" if g else "clean")

    if "net_quantity_value" in truth:
        ok = decl.get("net_quantity_value") == truth["net_quantity_value"] and _norm_unit(
            decl.get("net_quantity_unit")
        ) == _norm_unit(truth.get("net_quantity_unit"))
        out["net_quantity"] = (
            ok,
            f"got {decl.get('net_quantity_value')} {decl.get('net_quantity_unit')}",
        )
    elif "net_quantity" in absent:
        got = decl.get("net_quantity_value") is not None
        out["net_quantity"] = (
            not got,
            (f"FALSE+ {decl.get('net_quantity_value')} {decl.get('net_quantity_unit')}" if got else "clean"),
        )

    if "mrp" in truth:
        out["mrp"] = (decl.get("mrp") == truth["mrp"], f"got {decl.get('mrp')}")
    elif "mrp" in absent:
        out["mrp"] = (
            decl.get("mrp") is None,
            f"FALSE+ {decl.get('mrp')}" if decl.get("mrp") is not None else "clean",
        )

    for key, dkey in (("mfg", "mfg_date"), ("exp", "expiry_date")):
        if truth.get(key) is True:
            out[key] = (decl.get(dkey) is not None, f"got {decl.get(dkey)}")
        elif key in absent:
            out[key] = (
                decl.get(dkey) is None,
                f"FALSE+ {decl.get(dkey)}" if decl.get(dkey) else "clean",
            )

    if "manufacturer_sub" in truth:
        want = str(truth["manufacturer_sub"]).lower()
        blob = f"{decl.get('manufacturer_name') or ''} {decl.get('manufacturer_address') or ''}".lower()
        out["manufacturer"] = (
            want in blob,
            f"got {(decl.get('manufacturer_name') or '')[:50]!r}",
        )
    elif "manufacturer" in absent:
        got = bool(decl.get("manufacturer_name"))
        out["manufacturer"] = (
            not got,
            (f"FALSE+ {(decl.get('manufacturer_name') or '')[:40]!r}" if got else "clean"),
        )

    if truth.get("consumer_care") is True:
        out["care"] = (
            decl.get("consumer_care") is not None,
            f"got {(decl.get('consumer_care') or '')[:40]!r}",
        )
    elif "care" in absent:
        got = decl.get("consumer_care") is not None
        out["care"] = (
            not got,
            f"FALSE+ {(decl.get('consumer_care') or '')[:40]!r}" if got else "clean",
        )
    return out


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default=str(ROOT / "data" / "real" / "eval_labels.jsonl"))
    args = ap.parse_args()
    rows = [
        json.loads(line)
        for line in Path(args.labels).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    totals = {f: [0, 0] for f in FIELDS}
    print(f"== real-photo field accuracy: n={len(rows)} ==")
    for row in rows:
        img = ROOT / row["image"]
        if not img.exists():
            print(f"  MISSING {row['image']}")
            continue
        out = extract_label(img.read_bytes())
        res = score_row(out["declaration"], row.get("truth", {}), row.get("absent", []))
        marks = " ".join(f"{f}={'OK' if hit else 'MISS'}" for f, (hit, _) in res.items())
        print(f"  {img.name} conf={out['confidence']}% verdict={out['verdict']}\n    {marks}")
        for f, (hit, detail) in res.items():
            if not hit:
                print(f"      {f}: {detail}")
            totals[f][1] += 1
            totals[f][0] += bool(hit)
    print("== totals ==")
    th = tt = 0
    for f in FIELDS:
        h, t = totals[f]
        th += h
        tt += t
        if t:
            print(f"  {f:14s} {h}/{t} ({100 * h / t:.0f}%)")
    print(f"  OVERALL: {th}/{tt} ({100 * th / max(tt, 1):.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
