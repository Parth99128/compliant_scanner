"""Phase 1 acceptance (DELEGATION.md): 5/7 fields on sample images + font height mm, <5s/image CPU.

    python ml/accept_phase1.py [--count 5]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FIELDS = ["manufacturer_name", "manufacturer_address", "generic_name",
          "net_quantity_value", "mrp", "mfg_date", "consumer_care"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=5)
    args = ap.parse_args()
    subprocess.run([sys.executable, "ml/data_pipeline/generate_synthetic_labels.py",
                    "--count", str(args.count), "--out", "data"], cwd=ROOT, check=True)
    from ml.local_extract import extract_label

    ok_all = True
    for img in sorted((ROOT / "data" / "samples").glob("*.png"))[: args.count]:
        t0 = time.perf_counter()
        out = extract_label(img.read_bytes())
        dt = time.perf_counter() - t0
        hits = sum(1 for f in FIELDS if out["declaration"].get(f))
        status = "OK " if hits >= 5 and dt < 5.0 else "FAIL"
        if hits < 5 or dt >= 5.0:
            ok_all = False
        print(f"[{status}] {img.name}: {hits}/7 fields, {dt:.2f}s, "
              f"font_mm={out['median_font_height_mm']}, verdict={out['verdict']}")
        if out["warnings"]:
            print(f"       warnings: {out['warnings']}")
    print("PHASE1 ACCEPTANCE: " + ("PASS" if ok_all else "FAIL"))
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
