"""Fetch full-resolution Open Food Facts front images for local testing.

Re-downloads each entry in data/real/manifest.json at `.full.jpg`
resolution (the search API only returns `.400.jpg` thumbnails, which are
too small for Tesseract). Updates the manifest in place.

    python ml/data_pipeline/fetch_off_images.py --limit 10

Source data: Open Food Facts (ODbL). Network use only; no API key needed.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

UA = {"User-Agent": "LMPC-Scanner-SIH26034/1.0"}
ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(ROOT / "data" / "real" / "manifest.json"))
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()

    man_path = Path(args.manifest)
    man = json.loads(man_path.read_text(encoding="utf-8"))
    for m in man[: args.limit]:
        full_url = m["image_url"].replace(".400.jpg", ".full.jpg")
        try:
            req = urllib.request.Request(full_url, headers=UA)
            img = urllib.request.urlopen(req, timeout=40).read()
            (ROOT / m["file"]).write_bytes(img)
            m["image_url"] = full_url
            print(f"full {m['file']} {len(img)}", flush=True)
        except Exception as exc:  # keep the thumbnail on any failure
            print(f"keep-thumb {m['file']} {str(exc)[:100]}", flush=True)
        time.sleep(2)
    man_path.write_text(json.dumps(man, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
