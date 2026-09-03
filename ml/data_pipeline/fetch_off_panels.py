"""Fetch text-dense label panels (ingredients + nutrition photos) for local OCR testing.

Front-of-pack photos are brand graphics — mostly useless for the declaration
extraction pipeline, which targets the back-label/macro close-up (Step 2 of
the capture flow). Ingredients and nutrition panels are dense printed text
and exercise Tesseract + regex/NER realistically.

    python ml/data_pipeline/fetch_off_panels.py --limit 10

Writes into data/real/panels/ and updates data/real/panels_manifest.json.
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
SEARCH = (
    "https://world.openfoodfacts.org/cgi/search.pl?action=process"
    "&tagtype_0=countries&tag_contains_0=contains&tag_0=india"
    "&sort_by=unique_scans_n&page_size=30&json=1"
    "&fields=code,product_name,image_ingredients_url,image_nutrition_url"
)


def full(url: str) -> str:
    return url.replace(".400.jpg", ".full.jpg")


def grab(url: str, dest: Path) -> int:
    req = urllib.request.Request(full(url), headers=UA)
    data = urllib.request.urlopen(req, timeout=40).read()
    dest.write_bytes(data)
    return len(data)


def product_urls(code: str) -> dict:
    url = (
        f"https://world.openfoodfacts.org/api/v2/product/{code}"
        "?fields=code,product_name,image_ingredients_url,image_nutrition_url"
    )
    req = urllib.request.Request(url, headers=UA)
    payload = json.load(urllib.request.urlopen(req, timeout=40))
    return payload.get("product", {})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--outdir", default=str(ROOT / "data" / "real" / "panels"))
    ap.add_argument("--manifest", default=str(ROOT / "data" / "real" / "manifest.json"))
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Prefer per-product lookups for codes we already have (gentler on the
    # API than repeated search queries); fall back to search if needed.
    codes: list[str] = []
    man_path = Path(args.manifest)
    if man_path.exists():
        codes = [m["code"] for m in json.loads(man_path.read_text(encoding="utf-8"))]

    products: list[dict] = []
    for code in codes[: args.limit]:
        try:
            products.append(product_urls(code))
            time.sleep(3)
        except Exception as exc:
            print(f"product-lookup failed {code} {str(exc)[:100]}", flush=True)
            time.sleep(10)
    if not products:
        req = urllib.request.Request(SEARCH, headers=UA)
        payload = json.load(urllib.request.urlopen(req, timeout=40))
        products = payload.get("products", [])
    manifest: list[dict] = []
    for p in products:
        if len(manifest) >= args.limit * 2:
            break
        code = str(p.get("code", "unknown"))
        name = p.get("product_name") or ""
        for kind in ("image_ingredients_url", "image_nutrition_url"):
            url = p.get(kind)
            if not url:
                continue
            panel = "ingredients" if "ingredients" in kind else "nutrition"
            fn = outdir / f"off_{code}_{panel}.jpg"
            try:
                size = grab(url, fn)
                manifest.append(
                    {
                        "file": str(fn.relative_to(ROOT)),
                        "code": code,
                        "product_name": name,
                        "panel": panel,
                        "image_url": full(url),
                        "source": f"https://world.openfoodfacts.org/product/{code}",
                    }
                )
                print(f"saved {fn.name} {size}", flush=True)
                if len(manifest) >= args.limit * 2:
                    break
                time.sleep(2)
            except Exception as exc:
                print(f"skip {code}/{panel} {str(exc)[:100]}", flush=True)
    (outdir / "panels_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"total panels: {len(manifest)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
