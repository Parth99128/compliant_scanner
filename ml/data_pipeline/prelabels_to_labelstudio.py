"""Pre-labels -> Label Studio import JSON (one click to start annotating real labels).

    python ml/data_pipeline/prelabels_to_labelstudio.py \\
        --in data/prelabels_backs.jsonl --out data/labelstudio_import.json

Reads run_ocr_for_labeling.py rows {"image","text","confidence","declaration"}
and emits tasks matching ml/data_pipeline/label_studio_config.xml
($image -> label image, $text -> OCR text). Import the JSON file in
Label Studio (Project -> Import), fix the entity spans, export JSON, then
convert back with convert_labelstudio_to_bio.py into data/real_train.jsonl.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument(
        "--prefix",
        default="",
        help="Prepended to each image name (run_ocr_for_labeling stores bare "
        "filenames). E.g. --prefix data/real/backs",
    )
    args = ap.parse_args()
    tasks: list[dict] = []
    for line in Path(args.inp).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        name = str(row.get("image", ""))
        if args.prefix and not name.startswith(("http://", "https://", "/")):
            name = f"{args.prefix.rstrip('/')}/{name}"
        tasks.append(
            {
                "data": {
                    "image": name,
                    "text": row.get("text", ""),
                    "ocr_confidence": row.get("confidence", 0.0),
                }
            }
        )
    Path(args.out).write_text(json.dumps(tasks, indent=1), encoding="utf-8")
    print(f"wrote {len(tasks)} Label Studio tasks -> {args.out}")


if __name__ == "__main__":
    main()
