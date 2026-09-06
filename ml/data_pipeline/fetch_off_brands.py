"""Collect distinct manufacturer/brand names from Open Food Facts (India) to
extend the curated gazetteer (data/manufacturers.json).

Brands seen on real packs are exactly what OCR mangles, so this is the
highest-value extension source — and it is ODbL-licensed like the images.

    python ml/data_pipeline/fetch_off_brands.py --pages 4 --out data/off_brands.jsonl

Review the output, then merge vetted names into data/manufacturers.json
(keep that file curated: the matcher can only return listed names).
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

UA = {"User-Agent": "LMPC-Scanner-SIH26034/1.0"}
ROOT = Path(__file__).resolve().parents[2]
SEARCH = (
    "https://world.openfoodfacts.org/cgi/search.pl?action=process"
    "&tagtype_0=countries&tag_contains_0=contains&tag_0=india"
    "&sort_by=unique_scans_n&page_size=100&page={page}&json=1"
    "&fields=code,product_name,brands"
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=4)
    ap.add_argument("--out", default=str(ROOT / "data" / "off_brands.jsonl"))
    args = ap.parse_args()

    seen: dict[str, dict] = {}
    for page in range(1, args.pages + 1):
        try:
            req = urllib.request.Request(SEARCH.format(page=page), headers=UA)
            payload = json.load(urllib.request.urlopen(req, timeout=40))
        except Exception as exc:
            print(f"page {page} failed {str(exc)[:80]}", flush=True)
            time.sleep(10)
            continue
        for p in payload.get("products", []):
            for brand in (p.get("brands") or "").split(","):
                brand = " ".join(brand.split())
                if len(brand) >= 3 and brand not in seen:
                    seen[brand] = {
                        "brand": brand,
                        "example": p.get("product_name") or "",
                        "code": str(p.get("code", "")),
                    }
        print(f"page {page}: {len(seen)} distinct brands", flush=True)
        time.sleep(2)
    with open(args.out, "w", encoding="utf-8") as fh:
        for row in sorted(seen.values(), key=lambda r: r["brand"].lower()):
            fh.write(json.dumps(row) + "\n")
    print(f"wrote {len(seen)} brands -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
