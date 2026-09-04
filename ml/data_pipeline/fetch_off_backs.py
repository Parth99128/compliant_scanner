"""Fetch packaging/back-panel photos (declaration-bearing) for accuracy benchmarking.

Front photos are brand graphics; ingredients/nutrition panels lack MRP and
dates. The `packaging` image slot on Open Food Facts most often holds the
back/side label where Rule 6 declarations (MRP, net qty, dates, maker, care)
actually print — the only fair real-world test of this pipeline.

    python ml/data_pipeline/fetch_off_backs.py --limit 16

Writes into data/real/backs/ + backs_manifest.json. Open Food Facts (ODbL).
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

UA = {"User-Agent": "LMPC-Scanner-SIH26034/1.0"}
ROOT = Path(__file__).resolve().parents[2]


def product(code: str) -> dict:
    url = (
        f"https://world.openfoodfacts.org/api/v2/product/{code}"
        "?fields=code,product_name,image_packaging_url"
    )
    req = urllib.request.Request(url, headers=UA)
    return json.load(urllib.request.urlopen(req, timeout=40)).get("product", {})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=16)
    ap.add_argument("--outdir", default=str(ROOT / "data" / "real" / "backs"))
    ap.add_argument("--manifest", default=str(ROOT / "data" / "real" / "manifest.json"))
    ap.add_argument("--search-pages", default="2,3",
                    help="extra search result pages to mine for packaging photos")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    _seed = outdir / "backs_manifest.json"
    if _seed.exists():
        manifest = json.loads(_seed.read_text(encoding="utf-8"))
        print(f"seeded {len(manifest)} existing backs", flush=True)

    def grab(code: str, name: str, url: str) -> None:
        full = url.replace(".400.jpg", ".full.jpg")
        fn = outdir / f"off_{code}_pack.jpg"
        if fn.exists():
            return
        req = urllib.request.Request(full, headers=UA)
        data = urllib.request.urlopen(req, timeout=40).read()
        fn.write_bytes(data)
        manifest.append(
            {
                "file": str(fn.relative_to(ROOT)),
                "code": code,
                "product_name": name,
                "image_url": full,
                "source": f"https://world.openfoodfacts.org/product/{code}",
            }
        )
        print(f"saved {fn.name} {len(data)}", flush=True)

    codes = [m["code"] for m in json.loads(Path(args.manifest).read_text(encoding="utf-8"))]
    for code in codes:
        if len(manifest) >= args.limit:
            break
        try:
            p = product(code)
            time.sleep(3)
        except Exception as exc:
            print(f"lookup failed {code} {str(exc)[:80]}", flush=True)
            time.sleep(10)
            continue
        url = p.get("image_packaging_url")
        if not url:
            print(f"no-packaging {code}", flush=True)
            continue
        full = url.replace(".400.jpg", ".full.jpg")
        fn = outdir / f"off_{code}_pack.jpg"
        try:
            grab(code, p.get("product_name"), url)
        except Exception as exc:
            print(f"skip {code} {str(exc)[:80]}", flush=True)
        time.sleep(2)
    # Mine further search pages for new codes carrying packaging photos.
    for page in args.search_pages.split(","):
        if len(manifest) >= args.limit:
            break
        page = page.strip()
        if not page:
            continue
        try:
            q = (
                "https://world.openfoodfacts.org/cgi/search.pl?action=process"
                "&tagtype_0=countries&tag_contains_0=contains&tag_0=india"
                f"&sort_by=unique_scans_n&page_size=30&page={page}&json=1"
                "&fields=code,product_name,image_packaging_url"
            )
            payload = json.load(
                urllib.request.urlopen(urllib.request.Request(q, headers=UA), timeout=40)
            )
        except Exception as exc:
            print(f"search page {page} failed {str(exc)[:80]}", flush=True)
            continue
        for p in payload.get("products", []):
            if len(manifest) >= args.limit:
                break
            url = p.get("image_packaging_url")
            if not url:
                continue
            try:
                grab(str(p.get("code")), p.get("product_name"), url)
            except Exception as exc:
                print(f"skip {p.get('code')} {str(exc)[:80]}", flush=True)
            time.sleep(2)
    (outdir / "backs_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"total backs: {len(manifest)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
