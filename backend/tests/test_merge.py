"""POST /scans/merge: multi-angle captures merged into one verdict."""

import io

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.api.v1.routes import _choose_measured_index, _frame_entry
from app.main import create_app

client = TestClient(create_app())


def _png_bytes(text="MRP Rs. 99 Inclusive of all taxes"):
    img = Image.new("RGB", (900, 300), "white")
    ImageDraw.Draw(img).text((20, 20), text, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _auth() -> str:
    body = {"username": "mergeuser", "password": "mergepass123"}
    client.post("/api/v1/auth/register", json=body)
    r = client.post("/api/v1/auth/login", json=body)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _files(n, texts=None):
    texts = texts or ["MRP Rs. 99 Inclusive of all taxes"] * n
    return [("files", (f"m{i}.png", _png_bytes(texts[i % len(texts)]), "image/png")) for i in range(n)]


def test_merge_two_images_ok():
    tok = _auth()
    r = client.post("/api/v1/scans/merge", files=_files(2), headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "+merge2" in body["ocr_engine"]
    assert any("Merged 2 captures" in w for w in body["warnings"])
    assert len(body["results"]) == 10


def test_merge_rejects_single_image():
    tok = _auth()
    r = client.post("/api/v1/scans/merge", files=_files(1), headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 422


def test_merge_rejects_six_images():
    tok = _auth()
    r = client.post("/api/v1/scans/merge", files=_files(6), headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 422


def test_merge_requires_auth():
    r = client.post("/api/v1/scans/merge", files=_files(2))
    assert r.status_code == 401


def test_merged_scan_appears_in_dashboard_list():
    """Phase 5 acceptance: a mobile-style 2-frame upload shows up live in /scans."""
    tok = _auth()
    up = client.post("/api/v1/scans/merge", files=_files(2), headers={"Authorization": f"Bearer {tok}"})
    assert up.status_code == 200, up.text
    scan_id = up.json()["id"]
    rows = client.get("/api/v1/scans", headers={"Authorization": f"Bearer {tok}"}).json()
    match = [r for r in rows if r["id"] == scan_id]
    assert len(match) == 1
    assert match[0]["verdict"] == up.json()["verdict"]
    assert "+merge2" in match[0]["ocr_engine"]


def test_merge_gallery_keeps_every_angle():
    """All uploaded angles persisted + per-frame analysis exposed (no silent drops)."""
    tok = _auth()
    h = {"Authorization": f"Bearer {tok}"}
    up = client.post("/api/v1/scans/merge", files=_files(3), headers=h)
    assert up.status_code == 200, up.text
    body = up.json()
    frames = body["frames"]
    assert len(frames) == 3
    assert sorted(f["index"] for f in frames) == [0, 1, 2]
    assert sum(1 for f in frames if f["is_best"]) == 1
    # Every frame ran the pipeline: each carries its own read stats.
    assert all(f["word_count"] > 0 for f in frames)
    assert sum(f["words_added"] for f in frames) > 0
    scan_id = body["id"]
    gallery = client.get(f"/api/v1/scans/{scan_id}/images", headers=h).json()
    assert len(gallery) == 3
    best = next(f for f in gallery if f["is_best"])
    assert best["url"].endswith(f"/scans/{scan_id}/image")
    for f in gallery:
        if f["is_best"]:
            continue
        assert f["url"].endswith(f"/scans/{scan_id}/image/{f['index']}")
        r = client.get(f"/api/v1/scans/{scan_id}/image/{f['index']}", headers=h)
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "image/jpeg"
        assert r.content[:2] == b"\xff\xd8"
    # Detail view carries the same gallery.
    det = client.get(f"/api/v1/scans/{scan_id}", headers=h).json()
    assert len(det["frames"]) == 3


def test_single_scan_gallery_has_one_best_frame():
    tok = _auth()
    h = {"Authorization": f"Bearer {tok}"}
    up = client.post("/api/v1/scans", files={"file": ("s.png", _png_bytes(), "image/png")}, headers=h)
    assert up.status_code == 200, up.text
    frames = up.json()["frames"]
    assert len(frames) == 1 and frames[0]["is_best"] is True and frames[0]["index"] == 0
    gallery = client.get(f"/api/v1/scans/{up.json()['id']}/images", headers=h).json()
    assert len(gallery) == 1


def test_frame_image_unknown_index_404():
    tok = _auth()
    h = {"Authorization": f"Bearer {tok}"}
    up = client.post("/api/v1/scans/merge", files=_files(2), headers=h)
    assert up.status_code == 200, up.text
    r = client.get(f"/api/v1/scans/{up.json()['id']}/image/9", headers=h)
    assert r.status_code == 404


def test_measured_index_prefers_calibrated_frame():
    # Sharp macro (conf 90) with no scale must not overrule a weaker wide
    # shot (conf 70) carrying millimetre measurements.
    assert _choose_measured_index([70.0, 90.0], [2.5, None], 1) == 0
    assert _choose_measured_index([70.0, 90.0], [2.5, 3.0], 1) == 1  # both scaled: best wins
    assert _choose_measured_index([70.0, 90.0], [None, None], 1) == 1  # none: fall back


def test_frames_carry_own_boxes_and_measured_flag():
    tok = _auth()
    h = {"Authorization": f"Bearer {tok}"}
    up = client.post("/api/v1/scans/merge", files=_files(2), headers=h)
    assert up.status_code == 200, up.text
    body = up.json()
    assert body["measured_index"] in (0, 1)
    assert sum(1 for f in body["frames"] if f["measured"]) == 1
    assert all(len(f["boxes"]) > 0 and f["coord_w"] for f in body["frames"])
    det = client.get(f"/api/v1/scans/{body['id']}", headers=h).json()
    assert det["measured_index"] == body["measured_index"]
    assert [len(f["boxes"]) for f in det["frames"]] == [len(f["boxes"]) for f in body["frames"]]


def test_frame_entry_keeps_dense_panels_whole():
    """Regression: 300-word dense panels (ingredients + origin strip at the
    bottom) must keep every box — a low cap silently drops overlays while the
    text still extracts, looking exactly like 'OCR missed it'."""
    from types import SimpleNamespace

    from app.services.ocr import WordBox

    boxes = [WordBox(text=f"w{i}", x=i, y=i, w=10, h=8, confidence=90.0) for i in range(300)]
    out = SimpleNamespace(ocr_confidence=80.0, boxes=boxes, coord_w=900, coord_h=1200)
    entry = _frame_entry(0, out, 300, is_best=True, measured=True)
    assert len(entry["boxes"]) == 300
    assert entry["word_count"] == 300


def test_report_embeds_every_angle():
    """Merged PDF carries one annotated photo per uploaded angle."""
    from types import SimpleNamespace

    from app.api.v1.routes import _report_frames

    rec = SimpleNamespace(
        id="abc123",
        image_blob=b"bestbytes",
        boxes_json='{"w": 10, "h": 10, "boxes": []}',
        ocr_width=10,
        ocr_height=10,
        frames_json='[{"index": 0, "is_best": true}, {"index": 1, "is_best": false}]',
    )
    rows = [SimpleNamespace(frame_index=1, image_blob=b"angle2bytes")]
    frames = _report_frames(rec, rows)
    assert [f["label"] for f in frames] == ["Angle 1 (Best)", "Angle 2"]
    assert [f["blob"] for f in frames] == [b"bestbytes", b"angle2bytes"]

    tok = _auth()
    h = {"Authorization": f"Bearer {tok}"}
    up = client.post(
        "/api/v1/scans/merge",
        files=_files(2, ["MRP Rs. 99 Inclusive of all taxes", "Net Qty: 500 g"]),
        headers=h,
    )
    assert up.status_code == 200, up.text
    scan_id = up.json()["id"]
    client.patch(
        f"/api/v1/scans/{scan_id}/product",
        json={"product_name": "ReportProd", "brand_name": "ReportBrand", "category": "Snacks"},
        headers=h,
    )
    client.post(f"/api/v1/scans/{scan_id}/review", json={"decision": "confirm", "notes": "ok"}, headers=h)
    r = client.get(f"/api/v1/scans/{scan_id}/report", headers=h)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    # One embedded image XObject per uploaded angle (dedup only merges
    # byte-identical captures, so the angles differ like real photos).
    assert r.content.count(b"/Subtype /Image") >= 2


def _report_rec():
    from types import SimpleNamespace

    return SimpleNamespace(
        id="rpt1",
        request_id="q",
        ocr_engine="tesseract",
        ocr_confidence=90.0,
        verdict="COMPLIANT",
        status="final",
        reviewed_by="tester",
        reviewed_at=None,
        created_at=None,
        scan_lat=None,
        scan_lon=None,
        product_name="P",
        brand_name="B",
        category="C",
        image_blob=None,
    )


def test_report_fits_tall_portrait_angles():
    """Regression: tall phone portraits must shrink to the page — a fixed
    150mm width overruns the frame and crashes the build (LayoutError→500)."""
    import io

    from PIL import Image, ImageDraw

    from app.services.report import build_report_pdf

    img = Image.new("RGB", (900, 2000), "white")
    ImageDraw.Draw(img).text((40, 60), "MRP Rs. 99 Inclusive of all taxes", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=72)
    blob = buf.getvalue()
    img2 = Image.new("RGB", (900, 2000), "white")
    ImageDraw.Draw(img2).text((40, 900), "Net Qty: 500 g", fill="black")
    buf2 = io.BytesIO()
    img2.save(buf2, format="JPEG", quality=72)
    blob2 = buf2.getvalue()
    boxes = [{"text": "MRP", "x": 40, "y": 60, "w": 120, "h": 40, "confidence": 95.0}]
    pdf = build_report_pdf(
        _report_rec(),
        [],
        [],
        [
            {"label": "Angle 1 (Best)", "blob": blob, "boxes": boxes, "cw": 900, "ch": 2000},
            {"label": "Angle 2", "blob": blob2, "boxes": boxes, "cw": 900, "ch": 2000},
        ],
    )
    assert pdf[:4] == b"%PDF"
    assert pdf.count(b"/Subtype /Image") >= 2
