"""Barcode decoding (GTIN identity cross-check) — local, no network, optional stage.

What a barcode gives you (honest scope): the GTIN (product identity) and the
GS1 prefix country (e.g. 890 = India). It does NOT encode MRP, net quantity,
dates or care details — so a decoded barcode appears as an INFO-level rule
card (`LMPC-gtin`), never a PASS/FAIL on a declaration, and never changes
the verdict. Its value: identity confirmation + origin consistency (a pack
claiming import with a 890-prefixed GTIN deserves a second look).

Engine: `zxing-cpp` (MIT, prebuilt wheels, no system libs — unlike pyzbar,
which needs libzbar). Lazy import: missing lib -> [] and the pipeline is
unaffected.
"""

from __future__ import annotations

# GS1 prefix -> country (common origins for the Indian market; extend freely).
GS1_PREFIX_COUNTRY = {
    "890": "India",
    "690": "China",
    "691": "China",
    "692": "China",
    "693": "China",
    "694": "China",
    "695": "China",
    "000": "United States",
    "001": "United States",
    "030": "United States",
    "300": "France",
    "400": "Germany",
    "450": "Japan",
    "490": "Japan",
    "500": "United Kingdom",
    "600": "South Africa",
    "601": "South Africa",
    "608": "Bahrain",
    "609": "Mauritius",
    "611": "Morocco",
    "613": "Algeria",
    "619": "Tunisia",
    "621": "Syria",
    "622": "Egypt",
    "625": "Jordan",
    "626": "Iran",
    "627": "Kuwait",
    "628": "Saudi Arabia",
    "629": "UAE",
    "640": "Finland",
    "700": "Norway",
    "730": "Sweden",
    "740": "Guatemala",
    "750": "Mexico",
    "759": "Venezuela",
    "760": "Switzerland",
    "770": "Colombia",
    "773": "Uruguay",
    "775": "Peru",
    "777": "Bolivia",
    "779": "Argentina",
    "780": "Chile",
    "784": "Paraguay",
    "786": "Ecuador",
    "789": "Brazil",
    "800": "Italy",
    "840": "Spain",
    "850": "Cuba",
    "858": "Slovakia",
    "859": "Czechia",
    "860": "Serbia",
    "865": "Mongolia",
    "867": "North Korea",
    "868": "Turkey",
    "869": "Turkey",
    "870": "Netherlands",
    "880": "South Korea",
    "885": "Thailand",
    "888": "Singapore",
    "893": "Vietnam",
    "896": "Pakistan",
    "899": "Indonesia",
    "900": "Austria",
    "930": "Australia",
    "940": "New Zealand",
    "955": "Malaysia",
    "958": "Macau",
}


def prefix_country(gtin: str) -> str:
    """GS1 prefix country for a digit string, 'Unknown' when unmapped."""
    digits = "".join(c for c in gtin if c.isdigit())
    return GS1_PREFIX_COUNTRY.get(digits[:3], "Unknown")


def decode_gtins(image_bytes: bytes) -> list[dict]:
    """Decode 1D/2D barcodes -> [{'format': str, 'text': str}]. Never raises."""
    return [{"format": d["format"], "text": d["text"]} for d in decode_positioned(image_bytes)]


def decode_positioned(image_bytes: bytes) -> list[dict]:
    """Decode + localize: [{'format','text','quad': [(x,y) x4], 'size': (w,h)}].

    Quad corners are ordered top_left, top_right, bottom_right, bottom_left in
    the (capped-1200px) decode image's pixels. Powers barcode-zone masking.
    Never raises.
    """
    try:
        import io

        import zxingcpp
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        # Full-resolution phone shots decode worse and slower; 1200px cap.
        if img.width > 1200:
            img = img.resize((1200, int(1200 * img.size[1] / img.size[0])))
        import numpy as np

        results = zxingcpp.read_barcodes(np.asarray(img))
    except Exception:
        return []
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    try:
        for r in results or []:
            try:
                fmt = str(r.format).split(".")[-1]
                text = (r.text or "").strip()
                pos = r.position
                quad = [
                    (float(pos.top_left.x), float(pos.top_left.y)),
                    (float(pos.top_right.x), float(pos.top_right.y)),
                    (float(pos.bottom_right.x), float(pos.bottom_right.y)),
                    (float(pos.bottom_left.x), float(pos.bottom_left.y)),
                ]
            except Exception:
                continue
            if text and (fmt, text) not in seen:
                seen.add((fmt, text))
                out.append({"format": fmt, "text": text, "quad": quad, "size": img.size})
    except Exception:
        return []
    return out
