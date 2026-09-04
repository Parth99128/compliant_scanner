"""Accuracy benchmark: extraction + rules vs known truth, OCR robustness on real photos.

1. Synthetic (full ground truth): field-level extraction accuracy + verdict
   correctness, including violation-injected labels (missing MRP / tax phrase /
   care / dates / net qty -> must be NON_COMPLIANT, never COMPLIANT).
2. Real OFF photos (no ground truth): OCR robustness — share readable
   (confidence >= 60%) and mean confidence, split by photo type.

    python ml/eval_accuracy.py

Prints a summary table. Exit 0 always (benchmark, not gate).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.local_extract import extract_label  # noqa: E402

FIELDS = ("generic_name", "net_quantity", "mrp", "mfg", "exp", "care", "manufacturer")


def score_synthetic(rows: list[dict], imgdir: Path) -> dict:
    per_field = {f: [0, 0] for f in FIELDS}  # [hits, total]
    verdict_ok = 0
    for row in rows:
        img = imgdir / Path(row["image"]).name
        if not img.exists():
            continue
        out = extract_label(img.read_bytes())
        truth = row.get("truth", {})
        decl = out["declaration"]
        checks = {
            "generic_name": bool(decl.get("generic_name")) == bool(truth.get("generic_name"))
            and (not truth.get("generic_name") or truth["generic_name"] in (decl.get("generic_name") or "")),
            "net_quantity": (decl.get("net_quantity_value") == truth.get("net_quantity_value"))
            and (decl.get("net_quantity_unit") == truth.get("net_quantity_unit")),
            "mrp": (decl.get("mrp") == truth.get("mrp")),
            "mfg": (decl.get("mfg_date") is not None) == ("mfg" in truth),
            "exp": (decl.get("expiry_date") is not None) == ("exp" in truth),
            "care": (decl.get("consumer_care") is not None),
            "manufacturer": (decl.get("manufacturer_name") is not None),
        }
        for f, hit in checks.items():
            per_field[f][1] += 1
            per_field[f][0] += bool(hit)
        # Verdict logic: violation -> NON_COMPLIANT; clean flat render without
        # calibration -> INCOMPLETE (Rule 7 unmeasured, never a pass).
        expected = "NON_COMPLIANT" if truth.get("violation") else "INCOMPLETE"
        verdict_ok += out["verdict"] == expected
    return {"per_field": per_field, "verdict_ok": verdict_ok, "n": len(rows)}


def ocr_stats(paths: list[Path]) -> dict:
    confs, readable, empty = [], 0, 0
    for p in paths:
        out = extract_label(p.read_bytes())
        confs.append(out["confidence"] or 0.0)
        readable += (out["confidence"] or 0.0) >= 60
        empty += not (out["text"] or "").strip()
    return {
        "n": len(paths),
        "readable_60": readable,
        "empty": empty,
        "mean_conf": round(sum(confs) / len(confs), 1) if confs else 0.0,
    }


def main() -> int:
    data = ROOT / "data"
    print("== synthetic extraction + verdict accuracy (ground truth known) ==")
    total_fields = [0, 0]
    total_verdict = [0, 0]
    for name in ("labels.jsonl", "eval/labels.jsonl"):
        jf = data / name
        if not jf.exists():
            print(f"  {name}: missing, skipped")
            continue
        rows = [json.loads(line) for line in jf.read_text(encoding="utf-8").splitlines()]
        imgdir = data / "samples" if name == "labels.jsonl" else data / "eval" / "samples"
        res = score_synthetic(rows, imgdir)
        print(f"  {name}: n={res['n']} verdict {res['verdict_ok']}/{res['n']}")
        for f, (hit, tot) in res["per_field"].items():
            total_fields[0] += hit
            total_fields[1] += tot
            print(f"    {f:14s} {hit}/{tot} ({100 * hit / tot:.0f}%)")
        total_verdict[0] += res["verdict_ok"]
        total_verdict[1] += res["n"]
    print(
        f"  FIELD ACCURACY: {total_fields[0]}/{total_fields[1]} "
        f"({100 * total_fields[0] / max(total_fields[1], 1):.1f}%)"
    )
    print(
        f"  VERDICT ACCURACY: {total_verdict[0]}/{total_verdict[1]} "
        f"({100 * total_verdict[0] / max(total_verdict[1], 1):.1f}%)"
    )
    print("== real-photo OCR robustness (no ground truth; conf>=60 counts) ==")
    for sub in ("samples", "real/panels", "real/backs", "real"):
        paths = sorted((data / sub).glob("*.jpg")) + sorted((data / sub).glob("*.png"))
        if sub == "real":
            paths = [p for p in paths if p.is_file()]
        if not paths:
            continue
        s = ocr_stats(paths)
        print(
            f"  {sub:12s} n={s['n']:3d} readable={s['readable_60']:3d} "
            f"({100 * s['readable_60'] / max(s['n'], 1):.0f}%) empty={s['empty']:3d} mean_conf={s['mean_conf']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
