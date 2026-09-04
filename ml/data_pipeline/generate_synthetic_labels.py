"""Generate synthetic packaged-commodity label images + JSONL ground truth (CPU, PIL-only).

    python ml/data_pipeline/generate_synthetic_labels.py --count 5 --out data
    # Volume run for NER training (addendum §E: 20k-50k, positives + violations):
    python ml/data_pipeline/generate_synthetic_labels.py --count 20000 --out data/train \\
        --violation-rate 0.3 --no-images
"""

from __future__ import annotations

import argparse
import calendar
import json
import random
from pathlib import Path

random.seed(42)

PRODUCTS = ["Wheat Biscuits", "Detergent Powder", "Mustard Oil", "Instant Noodles", "Tea Powder"]
BRANDS = ["Acme Foods", "Shakti Home", "Ganga Mills", "Lotus Daily", "Kisan Gold"]
CITIES = ["Mumbai 400001", "Delhi 110001", "Chennai 600001", "Kolkata 700001"]
UNITS = ["g", "ml", "kg", "pcs", "cm"]
VIOLATIONS = ["missing_mrp", "missing_tax_phrase", "missing_care", "missing_dates", "missing_netqty"]


def make_label(i: int, violation: str | None = None) -> tuple[list[str], dict]:
    brand = random.choice(BRANDS)
    product = random.choice(PRODUCTS)
    city = random.choice(CITIES)
    qty = random.choice([50, 100, 200, 500, 1000])
    unit = random.choice(UNITS)
    mrp = round(random.uniform(40, 500), 2)
    mfg_day, mfg_mon = random.randint(1, 28), random.randint(1, 12)
    exp_day, exp_mon = random.randint(1, 28), random.randint(1, 12)
    # Date style mix: numeric (common), ABBR YEAR / Month Year (printed packs).
    style = random.random()
    if style < 0.6:
        mfg = f"{mfg_day:02d}/{mfg_mon:02d}/2025"
        exp = f"{exp_day:02d}/{exp_mon:02d}/2026"
    elif style < 0.8:
        mfg = f"{calendar.month_abbr[mfg_mon].upper()} 2025"
        exp = f"{calendar.month_abbr[exp_mon].upper()} 2026"
    else:
        mfg = f"{calendar.month_name[mfg_mon]} 2025"
        exp = f"{calendar.month_name[exp_mon]} 2026"
    tax_phrase = "Inclusive of all taxes" if violation != "missing_tax_phrase" else ""
    lines = [product, f"{brand}, Plot {i + 1}, {city}"]
    truth: dict = {"generic_name": product, "violation": violation}
    if violation != "missing_netqty":
        lines.append(f"Net Qty: {qty} {unit}")
        truth.update({"net_quantity_value": qty, "net_quantity_unit": unit})
    if violation != "missing_mrp":
        lines.append(f"MRP Rs. {mrp:.2f} {tax_phrase}".strip())
        truth["mrp"] = mrp
    if violation != "missing_dates":
        lines.append(f"Mfg: {mfg} Exp: {exp}")
        truth.update({"mfg": mfg, "exp": exp})
    if violation != "missing_care":
        lines.append(f"Customer Care: care{i}@example.in 1800-100-{i % 1000:03d}")
    lines.append("Country of Origin: India")
    return lines, truth


def render(lines: list[str], path: Path) -> None:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1000, 480), "white")
    d = ImageDraw.Draw(img)
    y = 24
    for ln in lines:
        d.text((24, y), ln, fill="black")
        y += 60
    img.save(path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--out", type=str, default="data")
    ap.add_argument("--violation-rate", type=float, default=0.0,
                    help="fraction of samples with a missing-field violation")
    ap.add_argument("--no-images", action="store_true",
                    help="JSONL ground truth only (fast volume runs for NER training)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    random.seed(args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if not args.no_images:
        sdir = out / "samples"
        sdir.mkdir(parents=True, exist_ok=True)
        for stale in list(sdir.glob("sample_*.png")):  # drop stale naming/content
            stale.unlink()
    n_viol = 0
    with open(out / "labels.jsonl", "w", encoding="utf-8") as fh:
        for i in range(args.count):
            violation = None
            if random.random() < args.violation_rate:
                violation = random.choice(VIOLATIONS)
                n_viol += 1
            lines, truth = make_label(i, violation)
            name = f"sample_{i:05d}.png"
            if not args.no_images:
                render(lines, out / "samples" / name)
                truth_row = {"image": f"samples/{name}", "lines": lines, "truth": truth}
            else:
                truth_row = {"image": None, "lines": lines, "truth": truth}
            fh.write(json.dumps(truth_row) + "\n")
    print(f"wrote {args.count} samples ({n_viol} violations) to {out}")


if __name__ == "__main__":
    main()
