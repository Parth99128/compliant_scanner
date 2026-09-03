"""Batch OCR over an image folder -> JSONL pre-labels for Label Studio.

    python ml/data_pipeline/run_ocr_for_labeling.py --indir data/samples --out data/prelabels.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.local_extract import extract_label  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    paths = sorted(Path(args.indir).glob("*.png")) + sorted(Path(args.indir).glob("*.jpg"))
    with open(args.out, "w", encoding="utf-8") as fh:
        for p in paths:
            out = extract_label(p.read_bytes())
            fh.write(json.dumps({"image": p.name, "text": out["text"],
                                 "confidence": out["confidence"],
                                 "declaration": out["declaration"]}) + "\n")
    print(f"pre-labeled {len(paths)} images -> {args.out}")


if __name__ == "__main__":
    main()
