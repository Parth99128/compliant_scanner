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
    ap.add_argument(
        "--ppm",
        type=float,
        default=12.0,
        help="Synthetic calibration: PIL renders have no reference card in frame, "
        "so detect_ppm_from_reference_card() returns None. Pass a known PPM to "
        "exercise the font_height_mm path (default 12 px/mm).",
    )
    args = ap.parse_args()
    subprocess.run([sys.executable, "ml/data_pipeline/generate_synthetic_labels.py",
                    "--count", str(args.count), "--out", "data"], cwd=ROOT, check=True)
    # Hermetic Phase-1 baseline: core CPU path only (OpenCV + Tesseract + regex).
    # Optional assists (Florence-2 ~1.5GB/30s, TrOCR, generic VLM, Gemini) are
    # explicitly disabled so a developer's local .env (e.g. FLORENCE_ENABLED=true
    # for experiments) cannot hijack this gate or blow the <5s budget.
    import os

    os.environ["FLORENCE_ENABLED"] = "false"
    os.environ["TROCR_ENABLED"] = "false"
    os.environ["VLM_ENABLED"] = "false"
    os.environ["LLM_PROVIDER"] = "off"
    os.environ["OFF_LOOKUP_ENABLED"] = "false"
    from ml.local_extract import extract_label

    images = sorted((ROOT / "data" / "samples").glob("*.png"))[: args.count]
    if not images:
        print("PHASE1 ACCEPTANCE: FAIL (no sample images generated)")
        return 1
    # Warm-up (untimed): first call pays model/import cold-start
    # (spaCy NER, Tesseract, OpenCV DNN) and must not count toward <5s budget.
    try:
        extract_label(images[0].read_bytes(), ppm=args.ppm)
    except Exception as exc:  # noqa: BLE001 — warmup is best-effort
        print(f"warmup failed (continuing): {exc}")
    ok_all = True
    for img in images:
        t0 = time.perf_counter()
        out = extract_label(img.read_bytes(), ppm=args.ppm)
        dt = time.perf_counter() - t0
        hits = sum(1 for f in FIELDS if out["declaration"].get(f))
        font_mm = out["median_font_height_mm"]
        status = "OK " if hits >= 5 and dt < 5.0 and font_mm is not None else "FAIL"
        if hits < 5 or dt >= 5.0 or font_mm is None:
            ok_all = False
        print(f"[{status}] {img.name}: {hits}/7 fields, {dt:.2f}s, "
              f"font_mm={font_mm}, verdict={out['verdict']}")
        if out["warnings"]:
            print(f"       warnings: {out['warnings']}")
    print("PHASE1 ACCEPTANCE: " + ("PASS" if ok_all else "FAIL"))
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
