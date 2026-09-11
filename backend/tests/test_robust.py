"""Barcode masking + VLM spacing repair (offline where possible)."""

from app.services.barcode import decode_positioned
from app.services.florence import repair_spacing
from app.services.vision import mask_quads

PACK = "tests/fixtures/ean13_india.png"


def _pack_bytes() -> bytes:
    with open(PACK, "rb") as fh:
        return fh.read()


def test_positions_found_on_real_pack():
    dets = decode_positioned(_pack_bytes())
    assert len(dets) >= 1
    d = dets[0]
    assert len(d["quad"]) == 4
    assert d["size"][0] > 0


def test_mask_whitens_barcode_zone():
    import io

    import numpy as np
    from PIL import Image

    raw = _pack_bytes()
    dets = decode_positioned(raw)
    assert dets
    out = mask_quads(raw, dets)
    assert out != raw
    before = np.asarray(Image.open(io.BytesIO(raw)).convert("RGB")).astype(float)
    after = np.asarray(Image.open(io.BytesIO(out)).convert("RGB")).astype(float)
    assert after.mean() > before.mean()  # white paint lightens the image


def test_mask_noop_without_detections():
    raw = _pack_bytes()
    assert mask_quads(raw, []) == raw
    assert mask_quads(b"junk", [{"quad": None, "size": None}]) == b"junk"


def test_spacing_repair_splits_camel_joints():
    assert repair_spacing("taste great!NUTRITIONAL") == "taste great! NUTRITIONAL"
    assert repair_spacing("Sugar-Free Light") == "Sugar-Free Light"
    assert repair_spacing("140g") == "140g"
    assert repair_spacing("01/09/2025") == "01/09/2025"
