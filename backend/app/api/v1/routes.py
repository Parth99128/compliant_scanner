import dataclasses
import json
from datetime import UTC

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger, request_id_ctx
from app.core.rate_limit import limiter
from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.db.session import Base, engine, ensure_columns, get_db
from app.models.tables import ScanImage, ScanRecord, User
from app.schemas.schemas import (
    CheckOut,
    ComplianceOut,
    DeclarationIn,
    ExplainOut,
    FrameOut,
    RegisterIn,
    ReviewIn,
    ScanOut,
    ScanPreviewOut,
    ScanSummaryOut,
    TokenOut,
    WordBoxOut,
)
from app.services.barcode import decode_gtins, decode_positioned, prefix_country
from app.services.extraction import extract_fields
from app.services.llm import LlmError, LlmNotConfigured, build_explain_prompt, explain_with_gemini
from app.services.ocr import run_ocr, word_boxes
from app.services.report import build_report_pdf
from app.services.rule_engine import (
    CheckResult,
    ComplianceReport,
    ProductDeclaration,
    Status,
    evaluate_compliance,
)
from app.services.vision import (
    detect_ppm_from_reference_card,
    detect_rotation_degrees,
    font_height_mm,
    mask_quads,
    preprocess_for_ocr,
    sharpness_score,
    upright_image_bytes,
)

router = APIRouter()
log = get_logger("api")
bearer = HTTPBearer(auto_error=False)

Base.metadata.create_all(bind=engine)
ensure_columns()


def _rid() -> str:
    return request_id_ctx.get()


def _store_image(raw: bytes) -> tuple[bytes | None, str]:
    """Downscaled JPEG capture for the scan viewer (longest side 1200px). None on failure."""
    try:
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(raw)).convert("RGB")
        w, h = img.size
        longest = max(w, h)
        if longest > 1200:
            scale = 1200.0 / longest
            img = img.resize((int(w * scale), int(h * scale)))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=72)
        return buf.getvalue(), "image/jpeg"
    except Exception:
        return None, "image/jpeg"


def _boxes_payload(out: "_PipelineOut") -> tuple[str, int | None, int | None]:
    """Serialized boxes + their coordinate space for storage and the viewer."""
    try:
        payload = json.dumps(
            {
                "w": out.coord_w,
                "h": out.coord_h,
                "boxes": [dataclasses.asdict(b) for b in out.boxes[:500]],
            }
        )
    except Exception:
        payload = '{"w": null, "h": null, "boxes": []}'
    return payload, out.coord_w, out.coord_h


def _stored_boxes(rec: ScanRecord) -> tuple[list[dict], int | None, int | None]:
    try:
        data = json.loads(rec.boxes_json or "{}")
        boxes = data.get("boxes", []) if isinstance(data, dict) else []
        w = rec.ocr_width
        h = rec.ocr_height
        if w is None and isinstance(data, dict):
            w = data.get("w")
        if h is None and isinstance(data, dict):
            h = data.get("h")
        return boxes if isinstance(boxes, list) else [], w, h
    except Exception:
        return [], rec.ocr_width, rec.ocr_height


def _frame_url(scan_id: str, index: int, is_best: bool) -> str:
    if is_best:
        return f"/scans/{scan_id}/image"
    return f"/scans/{scan_id}/image/{index}"


def _valid_gps(lat: float | None, lon: float | None) -> tuple[float | None, float | None]:
    """Keep device GPS only when both halves are in range; else store nulls."""
    try:
        if lat is None or lon is None:
            return None, None
        if not (-90.0 <= float(lat) <= 90.0 and -180.0 <= float(lon) <= 180.0):
            return None, None
        return round(float(lat), 6), round(float(lon), 6)
    except (TypeError, ValueError):
        return None, None


def _choose_measured_index(
    confidences: list[float], numeral_mms: list[float | None], best_i: int
) -> int:
    """Angle Rule 7 sizes are measured on: strongest read AMONG calibrated frames.

    A high-confidence macro with no card/scale in frame must not overrule a
    slightly weaker wide shot that carries the millimetre scale. Falls back to
    the best frame when nothing is calibrated (rules then report NOT_ASSESSABLE).
    Pure function, unit-tested.
    """
    calibrated = [i for i, mm in enumerate(numeral_mms) if mm is not None]
    if not calibrated:
        return best_i
    return max(calibrated, key=lambda i: (confidences[i], i))


def _frame_entry(
    index: int, out: "_PipelineOut", added: int, *, is_best: bool, measured: bool
) -> dict:
    # Keep the full box set (same [:500] cap as the legacy best-frame path):
    # dense panels hold 300+ words and truncating drops overlays off the
    # bottom half (ingredients, origin strip) while text still extracts.
    return {
        "index": index,
        "is_best": is_best,
        "measured": measured,
        "ocr_confidence": out.ocr_confidence,
        "word_count": len(out.boxes),
        "words_added": added,
        "boxes": [dataclasses.asdict(b) for b in out.boxes[:500]],
        "coord_w": out.coord_w,
        "coord_h": out.coord_h,
    }


def _boxed_list(raw_boxes: object) -> list[WordBoxOut]:
    """Coerce stored box dicts to WordBoxOut, skipping corrupt rows."""
    out: list[WordBoxOut] = []
    if not isinstance(raw_boxes, list):
        return out
    for b in raw_boxes[:500]:
        if not isinstance(b, dict):
            continue
        try:
            out.append(
                WordBoxOut(
                    text=str(b.get("text", "")),
                    x=int(b.get("x", 0)),
                    y=int(b.get("y", 0)),
                    w=int(b.get("w", 0)),
                    h=int(b.get("h", 0)),
                    confidence=float(b.get("confidence", 0.0)),
                )
            )
        except (TypeError, ValueError):
            continue
    return out


def _frames_out(rec: ScanRecord) -> list[FrameOut]:
    """Gallery entries for every uploaded angle, oldest API shape tolerated."""
    try:
        stored = json.loads(rec.frames_json or "[]")
    except Exception:
        stored = []
    if isinstance(stored, list) and stored:
        out = []
        for f in stored:
            if not isinstance(f, dict):
                continue
            idx = int(f.get("index", 0))
            best = bool(f.get("is_best", False))
            out.append(
                FrameOut(
                    index=idx,
                    is_best=best,
                    measured=bool(f.get("measured", best)),
                    url=_frame_url(rec.id, idx, best),
                    ocr_confidence=float(f.get("ocr_confidence", 0.0)),
                    word_count=int(f.get("word_count", 0)),
                    words_added=int(f.get("words_added", 0)),
                    boxes=_boxed_list(f.get("boxes")),
                    coord_w=f.get("coord_w"),
                    coord_h=f.get("coord_h"),
                )
            )
        return out
    # Pre-feature rows: only the primary capture survives.
    if rec.image_blob:
        return [FrameOut(index=0, is_best=True, measured=True, url=_frame_url(rec.id, 0, True))]
    return []


def _measured_index_out(rec: ScanRecord) -> int | None:
    """Angle index Rule 7 was measured on (flagged at scan time)."""
    try:
        stored = json.loads(rec.frames_json or "[]")
    except Exception:
        stored = []
    if isinstance(stored, list):
        for f in stored:
            if isinstance(f, dict) and f.get("measured"):
                return int(f.get("index", 0))
    if rec.image_blob:
        return 0
    return None


def _clean_dims(clean: bytes) -> tuple[int | None, int | None]:
    """Pixel dims of the preprocessed image = OCR box coordinate space."""
    try:
        import io

        from PIL import Image

        with Image.open(io.BytesIO(clean)) as img:
            return img.width, img.height
    except Exception:
        return None, None


def _checks(report) -> list[CheckOut]:
    return [
        CheckOut(
            rule_id=r.rule_id,
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
            passed=r.passed,
            message=r.message,
            field=r.field,
            citation=r.citation,
            citation_verified=r.citation_verified,
            source_ref=r.source_ref,
            observed=r.observed,
            expected=r.expected,
            severity=r.severity,
            remedy=r.remedy,
        )
        for r in report.results
    ]


def _stored_checks(stored: list[dict]) -> list[CheckOut]:
    out: list[CheckOut] = []
    for r in stored:
        status = str(r.get("status", "PASS"))
        out.append(
            CheckOut(
                rule_id=r["rule_id"],
                status=status,
                passed=status == "PASS",
                message=r.get("message", ""),
                field=r.get("field", ""),
                citation=r.get("citation", ""),
                citation_verified=r.get("citation_verified", False),
                source_ref=r.get("source_ref", ""),
                observed=r.get("observed"),
                expected=r.get("expected"),
                severity=r.get("severity", "info"),
                remedy=r.get("remedy"),
            )
        )
    return out


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    try:
        username, _role = decode_token(creds.credentials)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user


@router.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "request_id": _rid()}


@router.post("/auth/register", response_model=TokenOut, tags=["auth"])
@limiter.limit("10/minute")
def register(request: Request, body: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=409, detail="Username taken")
    user = User(username=body.username, password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    db.commit()
    log.info("user_registered", username=body.username, role=body.role)
    return TokenOut(access_token=create_access_token(body.username, body.role))


@router.post("/auth/login", response_model=TokenOut, tags=["auth"])
@limiter.limit("20/minute")
def login(request: Request, body: RegisterIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenOut(access_token=create_access_token(user.username, user.role))


@router.post("/validate", response_model=ComplianceOut, tags=["scans"])
def validate_declaration(body: DeclarationIn):
    decl = ProductDeclaration(**body.model_dump())
    report = evaluate_compliance(decl)
    log.info("validate", compliant=report.compliant)
    return ComplianceOut(
        verdict=report.verdict,
        compliant=report.compliant,
        results=_checks(report),
        warnings=report.warnings,
        request_id=_rid(),
    )


def _preview_fields(decl: ProductDeclaration) -> dict[str, bool]:
    """Mandatory live checklist: 6 declarations the auto-shutter waits for."""
    return {
        "generic": bool(decl.generic_name),
        "manufacturer": bool(decl.manufacturer_name and decl.manufacturer_address),
        "net_qty": bool(decl.net_quantity_value and decl.net_quantity_unit),
        "mrp": bool(decl.mrp),
        "mfg_date": bool(decl.mfg_date),
        "care": bool(decl.consumer_care),
    }


@router.post("/scans/preview", response_model=ScanPreviewOut, tags=["scans"])
@limiter.limit("30/minute")
async def scan_preview(
    request: Request,
    file: UploadFile = File(...),
    ppm: float | None = Form(default=None),
    panel_area_cm2: float | None = Form(default=None),
    is_embossed: bool = Form(default=False),
    user: User = Depends(current_user),
):
    """Live-camera frame analysis: OCR text + size calc, no DB write.

    The frontend samples a downscaled viewfinder frame every ~2s and polls
    this endpoint. It returns the extracted-field checklist, measured font
    height in mm (pixels / PPM), focus sharpness, and a `ready` flag the UI
    uses to auto-capture a full-resolution frame once all text is detected.
    """
    settings = get_settings()
    if file.content_type not in settings.allowed_content_type_list:
        raise HTTPException(status_code=415, detail=f"Unsupported type {file.content_type}")
    raw = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(raw) > max_bytes:
        raise HTTPException(status_code=413, detail="File too large")
    try:
        out = _run_pipeline(raw, ppm, None, None, panel_area_cm2, is_embossed)
    except Exception as exc:
        log.error("preview_failed", error=str(exc))
        raise HTTPException(status_code=502, detail="OCR processing failed")
    fields = _preview_fields(out.decl)
    found = sum(1 for v in fields.values() if v)
    sharp = sharpness_score(raw)
    reasons: list[str] = []
    if found < 6:
        missing = sorted(k for k, v in fields.items() if not v)
        reasons.append(f"missing {', '.join(missing)}")
    if out.ocr_confidence < 60:
        reasons.append(f"low confidence {out.ocr_confidence}% (<60%)")
    if out.font_mm is None:
        reasons.append("size unmeasured (no card/ppm in frame)")
    if sharp is not None and sharp < 50:
        reasons.append(f"blurry (sharpness {sharp})")
    ready = not reasons
    return ScanPreviewOut(
        ocr_engine=out.ocr_engine,
        ocr_text=out.ocr_text[:1000],
        ocr_confidence=out.ocr_confidence,
        word_count=len(out.boxes),
        font_height_mm=out.font_mm,
        ppm_used=out.resolved_ppm,
        sharpness=sharp,
        fields_found=fields,
        fields_count=found,
        fields_total=6,
        verdict=out.report.verdict,
        compliant=out.report.compliant,
        ready=ready,
        ready_reason="ready to capture" if ready else "; ".join(reasons),
        boxes=[WordBoxOut(**dataclasses.asdict(b)) for b in out.boxes[:100]],
        coord_w=out.coord_w,
        coord_h=out.coord_h,
        request_id=_rid(),
    )


@dataclasses.dataclass
class _PipelineOut:
    ocr_text: str
    ocr_engine: str
    ocr_confidence: float
    boxes: list
    font_mm: float | None
    decl: ProductDeclaration
    report: ComplianceReport
    coord_w: int | None = None  # preprocessed-image dims = box coordinate space
    coord_h: int | None = None
    resolved_ppm: float | None = None


def _run_pipeline(
    raw: bytes,
    ppm: float | None,
    font_px: float | None,
    letter_px: float | None,
    panel_area_cm2: float | None,
    is_embossed: bool,
) -> _PipelineOut:
    """OCR -> extract -> calibrate -> rule-evaluate for one image. Never returns None."""
    clean = preprocess_for_ocr(raw)
    ocr = run_ocr(clean)
    boxes = word_boxes(clean, ocr.config)
    # Orientation second pass: a sideways/upside-down capture reads weak.
    # Rotate ONLY then (a strong read is already upright — rotating it could
    # only hurt, e.g. labels mixing horizontal panels with a vertical strip).
    # Keep whichever read is stronger. Clean scans pay one cheap OSD call.
    if ocr.confidence < 60:
        try:
            angle = detect_rotation_degrees(clean)
        except Exception:
            angle = 0
        if angle:
            try:
                upright = upright_image_bytes(clean)
            except Exception:
                upright = clean
            if upright != clean:
                try:
                    ocr_r = run_ocr(upright)
                except Exception:
                    ocr_r = None
                if ocr_r and ocr_r.text.strip() and ocr_r.confidence > ocr.confidence:
                    ocr, boxes, clean = ocr_r, word_boxes(upright, ocr_r.config), upright
    # Robustness second pass: when the first read is weak and a barcode is
    # present, mask the bars (VLM/OCR hallucinate digit soup on them) and
    # re-read; keep whichever read is stronger. Clean scans pay nothing.
    if ocr.confidence < 60:
        try:
            dets = decode_positioned(raw)
        except Exception:
            dets = []
        if dets:
            try:
                masked = mask_quads(raw, dets)
            except Exception:
                masked = raw
            if masked != raw:
                try:
                    clean2 = preprocess_for_ocr(masked)
                    ocr2 = run_ocr(clean2)
                except Exception:
                    ocr2 = None
                if ocr2 and ocr2.text.strip() and ocr2.confidence > ocr.confidence:
                    ocr, boxes, clean = ocr2, word_boxes(clean2, ocr2.config), clean2
    decl = extract_fields(ocr.text)
    # Spatial calibration: explicit ppm wins, else auto-detect reference card.
    resolved_ppm = ppm if (ppm and ppm > 0) else detect_ppm_from_reference_card(raw)
    px = font_px
    if px is None and boxes:
        hs = sorted(b.h for b in boxes)
        px = float(hs[len(hs) // 2])
    font_mm = font_height_mm(px, resolved_ppm) if px and resolved_ppm else None
    # Letter height defaults to the same median glyph measurement (approximation);
    # width ratio uses the median box w/h across OCR words.
    lpx = letter_px
    if lpx is None and boxes:
        hs = sorted(b.h for b in boxes)
        lpx = float(hs[len(hs) // 2])
    letter_mm = font_height_mm(lpx, resolved_ppm) if lpx and resolved_ppm else None
    ratio = None
    if boxes:
        ratios = sorted(b.w / b.h for b in boxes if b.h > 0)
        ratio = round(ratios[len(ratios) // 2], 3) if ratios else None
    if font_mm is not None or letter_mm is not None or ratio is not None:
        decl = dataclasses.replace(
            decl,
            min_numeral_height_mm=font_mm,
            min_letter_height_mm=letter_mm,
            min_width_to_height_ratio=ratio,
            is_embossed=is_embossed,
            panel_area_cm2=panel_area_cm2,
        )
    report = evaluate_compliance(decl, ocr_confidence=ocr.confidence or None)
    # Barcode identity cross-check (INFO only): GTIN + GS1 prefix country.
    # Never changes the verdict — barcodes don't encode declarations.
    try:
        gtins = decode_gtins(raw)
    except Exception:
        gtins = []
    if gtins:
        cards = list(report.results)
        for g in gtins:
            country = prefix_country(g["text"])
            cards.append(
                CheckResult(
                    rule_id="LMPC-gtin",
                    status=Status.PASS,
                    message=f"Barcode {g['format']} {g['text']} (GS1 prefix: {country})",
                    field="gtin",
                    citation="GS1 prefix (voluntary identity cross-check)",
                    citation_verified=False,
                    observed=g["text"],
                    expected="consistent with declared origin",
                    severity="info",
                )
            )
        report = dataclasses.replace(report, results=cards)
    coord_w, coord_h = _clean_dims(clean)
    return _PipelineOut(
        ocr_text=ocr.text,
        ocr_engine=ocr.engine,
        ocr_confidence=ocr.confidence,
        boxes=boxes,
        font_mm=font_mm,
        decl=decl,
        report=report,
        coord_w=coord_w,
        coord_h=coord_h,
        resolved_ppm=resolved_ppm,
    )


@router.post("/scans", response_model=ScanOut, tags=["scans"])
@limiter.limit("20/minute")
async def scan_image(
    request: Request,
    file: UploadFile = File(...),
    ppm: float | None = Form(default=None),
    font_px: float | None = Form(default=None),
    letter_px: float | None = Form(default=None),
    panel_area_cm2: float | None = Form(default=None),
    is_embossed: bool = Form(default=False),
    product_name: str | None = Form(default=None),
    brand_name: str | None = Form(default=None),
    category: str | None = Form(default=None),
    scan_lat: float | None = Form(default=None),
    scan_lon: float | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    settings = get_settings()
    if file.content_type not in settings.allowed_content_type_list:
        raise HTTPException(status_code=415, detail=f"Unsupported type {file.content_type}")
    raw = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(raw) > max_bytes:
        raise HTTPException(status_code=413, detail="File too large")
    try:
        out = _run_pipeline(raw, ppm, font_px, letter_px, panel_area_cm2, is_embossed)
    except Exception as exc:
        log.error("ocr_failed", error=str(exc))
        raise HTTPException(status_code=502, detail="OCR processing failed")
    report = out.report
    img_blob, img_type = _store_image(raw)
    boxes_json, coord_w, coord_h = _boxes_payload(out)
    pname, bname, cat = _product_fields(out.decl, product_name, brand_name, category)
    lat, lon = _valid_gps(scan_lat, scan_lon)
    frames = [_frame_entry(0, out, len(out.boxes), is_best=True, measured=True)]
    rec = ScanRecord(
        owner_id=user.id,
        request_id=_rid(),
        ocr_text=out.ocr_text[:8000],
        ocr_engine=out.ocr_engine,
        ocr_confidence=out.ocr_confidence,
        font_height_mm=out.font_mm,
        compliant=report.compliant,
        verdict=report.verdict,
        results_json=json.dumps([dataclasses.asdict(r) for r in report.results]),
        image_blob=img_blob,
        image_content_type=img_type,
        boxes_json=boxes_json,
        ocr_width=coord_w,
        ocr_height=coord_h,
        product_name=pname,
        brand_name=bname,
        category=cat,
        ppm_used=out.resolved_ppm,
        scan_lat=lat,
        scan_lon=lon,
        frames_json=json.dumps(frames),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    log.info("scan_done", scan_id=rec.id, compliant=report.compliant, engine=out.ocr_engine)
    return ScanOut(
        id=rec.id,
        request_id=rec.request_id,
        status=rec.status,
        ocr_engine=out.ocr_engine,
        ocr_text=out.ocr_text[:2000],
        ocr_confidence=out.ocr_confidence,
        font_height_mm=out.font_mm,
        verdict=report.verdict,
        compliant=report.compliant,
        results=_checks(report),
        warnings=report.warnings,
        boxes=[WordBoxOut(**dataclasses.asdict(b)) for b in out.boxes[:500]],
        has_image=rec.image_blob is not None,
        coord_w=coord_w,
        coord_h=coord_h,
        product_name=rec.product_name,
        brand_name=rec.brand_name,
        category=rec.category,
        ppm_used=rec.ppm_used,
        frames=_frames_out(rec),
        measured_index=_measured_index_out(rec),
        scan_lat=rec.scan_lat,
        scan_lon=rec.scan_lon,
    )


def _merge_ocr_lines(per_image: list[tuple[int, float, str]]) -> tuple[str, dict[int, int]]:
    """Union of OCR lines across captures, best-confidence image first, de-duplicated.

    Multi-angle shots of one label overlap heavily; the union recovers words
    any single angle lost to glare/curve/blur, without double counting.
    Returns (merged text, {frame index: lines only that frame contributed}).
    """
    seen: set[str] = set()
    merged: list[str] = []
    added: dict[int, int] = {}
    for idx, _conf, text in sorted(per_image, key=lambda t: -t[1]):
        for line in (text or "").splitlines():
            norm = " ".join(line.split())
            if len(norm) >= 2 and norm.lower() not in seen:
                seen.add(norm.lower())
                merged.append(norm)
                added[idx] = added.get(idx, 0) + 1
    return "\n".join(merged), added


@router.post("/scans/merge", response_model=ScanOut, tags=["scans"])
@limiter.limit("10/minute")
async def merge_scans(
    request: Request,
    files: list[UploadFile] = File(...),
    ppm: float | None = Form(default=None),
    font_px: float | None = Form(default=None),
    letter_px: float | None = Form(default=None),
    panel_area_cm2: float | None = Form(default=None),
    is_embossed: bool = Form(default=False),
    product_name: str | None = Form(default=None),
    brand_name: str | None = Form(default=None),
    category: str | None = Form(default=None),
    scan_lat: float | None = Form(default=None),
    scan_lon: float | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Multi-angle capture: 2-5 shots of one label merged into a single verdict.

    Each image runs the full pipeline; OCR lines are unioned by confidence and
    the merged text is extracted + evaluated once. Measurements (font height,
    boxes) come from the highest-confidence capture. Stored as ONE scan record
    so history and audit stay clean.
    """
    settings = get_settings()
    if not 2 <= len(files) <= 5:
        raise HTTPException(status_code=422, detail="Send 2-5 images of the same label")
    raws: list[bytes] = []
    max_bytes = settings.max_upload_mb * 1024 * 1024
    for f in files:
        if f.content_type not in settings.allowed_content_type_list:
            raise HTTPException(status_code=415, detail=f"Unsupported type {f.content_type}")
        raw = await f.read()
        if len(raw) == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        if len(raw) > max_bytes:
            raise HTTPException(status_code=413, detail="File too large")
        raws.append(raw)
    try:
        outs = [_run_pipeline(raw, ppm, font_px, letter_px, panel_area_cm2, is_embossed) for raw in raws]
    except Exception as exc:
        log.error("ocr_failed", error=str(exc))
        raise HTTPException(status_code=502, detail="OCR processing failed")
    best_i = max(range(len(outs)), key=lambda i: (outs[i].ocr_confidence, len(outs[i].ocr_text)))
    best = outs[best_i]
    merged_text, added = _merge_ocr_lines([(i, o.ocr_confidence, o.ocr_text) for i, o in enumerate(outs)])
    merged_decl = extract_fields(merged_text)
    # Measure on the strongest CALIBRATED frame (scale + words), not blindly
    # the best read — a sharp macro with no card must not overrule a wide
    # shot carrying the millimetre scale.
    m_i = _choose_measured_index(
        [o.ocr_confidence for o in outs],
        [o.font_mm if o.boxes else None for o in outs],
        best_i,
    )
    measure = outs[m_i]
    # Text fields come from the union; measurements stay with the measured frame.
    decl = dataclasses.replace(
        merged_decl,
        min_numeral_height_mm=measure.decl.min_numeral_height_mm,
        min_letter_height_mm=measure.decl.min_letter_height_mm,
        min_width_to_height_ratio=measure.decl.min_width_to_height_ratio,
        is_embossed=is_embossed,
        panel_area_cm2=panel_area_cm2,
    )
    report = evaluate_compliance(decl, ocr_confidence=best.ocr_confidence or None)
    # Carry over barcode identity cards from the best frame (INFO only).
    carried = [r for r in best.report.results if r.rule_id == "LMPC-gtin"]
    if carried:
        report = dataclasses.replace(report, results=[*report.results, *carried])
    warnings = list(report.warnings)
    warnings.append(
        f"Merged {len(raws)} captures (best single-frame confidence "
        f"{best.ocr_confidence}%); text combined by confidence, evaluated once."
    )
    if m_i != best_i:
        warnings.append(
            f"Type size measured on angle {m_i + 1} (it carries the mm scale); "
            f"text led by angle {best_i + 1}."
        )
    engine = f"{best.ocr_engine}+merge{len(raws)}"
    img_blob, img_type = _store_image(raws[best_i])
    boxes_json, coord_w, coord_h = _boxes_payload(best)
    pname, bname, cat = _product_fields(decl, product_name, brand_name, category)
    lat, lon = _valid_gps(scan_lat, scan_lon)
    frames = [_frame_entry(i, o, added.get(i, 0), is_best=(i == best_i), measured=(i == m_i)) for i, o in enumerate(outs)]
    rec = ScanRecord(
        owner_id=user.id,
        request_id=_rid(),
        ocr_text=merged_text[:8000],
        ocr_engine=engine,
        ocr_confidence=best.ocr_confidence,
        font_height_mm=measure.font_mm,
        compliant=report.compliant,
        verdict=report.verdict,
        results_json=json.dumps([dataclasses.asdict(r) for r in report.results]),
        image_blob=img_blob,
        image_content_type=img_type,
        boxes_json=boxes_json,
        ocr_width=coord_w,
        ocr_height=coord_h,
        product_name=pname,
        brand_name=bname,
        category=cat,
        ppm_used=measure.resolved_ppm,
        scan_lat=lat,
        scan_lon=lon,
        frames_json=json.dumps(frames),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    # Keep every non-best angle so the viewer can show the full gallery.
    # The best frame stays on ScanRecord.image_blob (legacy primary).
    for i, raw in enumerate(raws):
        if i == best_i:
            continue
        blob, ctype = _store_image(raw)
        if blob is not None:
            db.add(ScanImage(scan_id=rec.id, frame_index=i, image_blob=blob, image_content_type=ctype))
    db.commit()
    log.info("scan_merged", scan_id=rec.id, compliant=report.compliant, frames=len(raws))
    return ScanOut(
        id=rec.id,
        request_id=rec.request_id,
        status=rec.status,
        ocr_engine=engine,
        ocr_text=merged_text[:2000],
        ocr_confidence=best.ocr_confidence,
        font_height_mm=measure.font_mm,
        verdict=report.verdict,
        compliant=report.compliant,
        results=_checks(report),
        warnings=warnings,
        boxes=[WordBoxOut(**dataclasses.asdict(b)) for b in best.boxes[:500]],
        has_image=rec.image_blob is not None,
        coord_w=coord_w,
        coord_h=coord_h,
        product_name=rec.product_name,
        brand_name=rec.brand_name,
        category=rec.category,
        ppm_used=rec.ppm_used,
        frames=_frames_out(rec),
        measured_index=_measured_index_out(rec),
        scan_lat=rec.scan_lat,
        scan_lon=rec.scan_lon,
    )


def _get_scan(scan_id: str, user: User, db: Session) -> ScanRecord:
    rec = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Scan not found")
    if user.role != "admin" and rec.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not your scan")
    return rec


@router.get("/scans", response_model=list[ScanSummaryOut], tags=["scans"])
def list_scans(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    q: str | None = None,
    verdict: str | None = None,
    status: str | None = None,
):
    """Scan repository: server-side search (id/product/brand/OCR text) + verdict/status filters."""
    query = db.query(ScanRecord)
    if user.role != "admin":
        query = query.filter(ScanRecord.owner_id == user.id)
    if verdict in ("COMPLIANT", "NON_COMPLIANT", "INCOMPLETE"):
        query = query.filter(ScanRecord.verdict == verdict)
    if status in ("pending_review", "final"):
        query = query.filter(ScanRecord.status == status)
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            ScanRecord.id.like(like)
            | ScanRecord.product_name.like(like)
            | ScanRecord.brand_name.like(like)
            | ScanRecord.ocr_text.like(like)
        )
    query = query.order_by(ScanRecord.created_at.desc()).limit(100)
    return [
        ScanSummaryOut(
            id=r.id,
            verdict=r.verdict,
            compliant=r.compliant,
            status=r.status,
            ocr_engine=r.ocr_engine,
            created_at=r.created_at.isoformat(),
            preview=(r.ocr_text or "").strip().splitlines()[0][:80] if (r.ocr_text or "").strip() else "",
            product_name=r.product_name or "",
            brand_name=r.brand_name or "",
            category=r.category or "",
            has_image=r.image_blob is not None,
        )
        for r in query.all()
    ]


class ProductIn(BaseModel):
    product_name: str = Field(default="", max_length=160)
    brand_name: str = Field(default="", max_length=160)
    category: str = Field(default="", max_length=80)


def _product_fields(
    decl: ProductDeclaration,
    product_name: str | None,
    brand_name: str | None,
    category: str | None,
) -> tuple[str, str, str]:
    """Officer-supplied labels win; otherwise auto-fill from extraction."""
    return (
        (product_name or "").strip()[:160] or (decl.generic_name or "")[:160],
        (brand_name or "").strip()[:160] or (decl.manufacturer_name or "")[:160],
        (category or "").strip()[:80],
    )


@router.patch("/scans/{scan_id}/product", response_model=ScanOut, tags=["scans"])
def update_product(
    scan_id: str,
    body: ProductIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Correct/label a scan's product identity after the fact (audit: review notes stay separate)."""
    rec = _get_scan(scan_id, user, db)
    rec.product_name = body.product_name.strip()[:160]
    rec.brand_name = body.brand_name.strip()[:160]
    rec.category = body.category.strip()[:80]
    db.commit()
    db.refresh(rec)
    log.info("scan_product_updated", scan_id=rec.id, by=user.username)
    return _scan_out(rec)


@router.get("/stats/overview", tags=["meta"])
def stats_overview(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Officer dashboard aggregates: counts, top failing rules, daily volume, recent scans."""
    from collections import Counter
    from datetime import datetime

    query = db.query(ScanRecord)
    if user.role != "admin":
        query = query.filter(ScanRecord.owner_id == user.id)
    rows = query.order_by(ScanRecord.created_at.desc()).limit(500).all()
    by_verdict: Counter[str] = Counter()
    failed_rules: Counter[str] = Counter()
    by_day: Counter[str] = Counter()
    for r in rows:
        by_verdict[r.verdict] += 1
        day = r.created_at.isoformat()[:10] if isinstance(r.created_at, datetime) else str(r.created_at)[:10]
        by_day[day] += 1
        try:
            stored = json.loads(r.results_json or "[]")
        except Exception:
            stored = []
        for res in stored:
            if (
                isinstance(res, dict)
                and res.get("status") in ("FAIL", "NOT_FOUND")
                and res.get("severity") != "info"
            ):
                failed_rules[res.get("rule_id", "unknown")] += 1
    recent = [
        {
            "id": r.id,
            "verdict": r.verdict,
            "status": r.status,
            "product_name": r.product_name or "",
            "preview": (r.ocr_text or "").strip().splitlines()[0][:80] if (r.ocr_text or "").strip() else "",
            "created_at": (
                r.created_at.isoformat() if isinstance(r.created_at, datetime) else str(r.created_at)
            ),
        }
        for r in rows[:8]
    ]
    return {
        "total": len(rows),
        "by_verdict": dict(by_verdict),
        "top_failed_rules": failed_rules.most_common(8),
        "by_day": sorted(by_day.items())[-14:],
        "recent": recent,
        "request_id": _rid(),
    }


def _scan_out(rec: ScanRecord) -> ScanOut:
    stored = json.loads(rec.results_json or "[]")
    boxes, coord_w, coord_h = _stored_boxes(rec)
    return ScanOut(
        id=rec.id,
        request_id=rec.request_id,
        status=rec.status,
        ocr_engine=rec.ocr_engine,
        ocr_text=rec.ocr_text[:2000],
        ocr_confidence=rec.ocr_confidence,
        font_height_mm=rec.font_height_mm,
        verdict=rec.verdict,
        compliant=rec.compliant,
        results=_stored_checks(stored),
        warnings=[],
        reviewed_by=rec.reviewed_by or None,
        reviewed_at=rec.reviewed_at.isoformat() if rec.reviewed_at else None,
        has_image=rec.image_blob is not None,
        coord_w=coord_w,
        coord_h=coord_h,
        product_name=rec.product_name or "",
        brand_name=rec.brand_name or "",
        category=rec.category or "",
        ppm_used=rec.ppm_used,
        frames=_frames_out(rec),
        measured_index=_measured_index_out(rec),
        scan_lat=rec.scan_lat,
        scan_lon=rec.scan_lon,
        boxes=[
            WordBoxOut(
                text=str(b.get("text", "")),
                x=int(b.get("x", 0)),
                y=int(b.get("y", 0)),
                w=int(b.get("w", 0)),
                h=int(b.get("h", 0)),
                confidence=float(b.get("confidence", 0.0)),
            )
            for b in boxes[:500]
            if isinstance(b, dict)
        ],
    )


@router.get("/scans/{scan_id}/image", tags=["scans"])
def scan_image_file(scan_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Original capture for the scan viewer (downscaled JPEG). 404 when absent."""
    rec = _get_scan(scan_id, user, db)
    if not rec.image_blob:
        raise HTTPException(status_code=404, detail="No stored image for this scan")
    return Response(
        content=bytes(rec.image_blob),
        media_type=rec.image_content_type or "image/jpeg",
    )


@router.get("/scans/{scan_id}/images", response_model=list[FrameOut], tags=["scans"])
def scan_images(scan_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Gallery: every uploaded angle with its own analysis summary (upload order)."""
    return _frames_out(_get_scan(scan_id, user, db))


@router.get("/scans/{scan_id}/image/{frame_index}", tags=["scans"])
def scan_frame_image(
    scan_id: str, frame_index: int, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    """One non-best merge angle (the best frame lives at /scans/{id}/image)."""
    _get_scan(scan_id, user, db)
    row = (
        db.query(ScanImage)
        .filter(ScanImage.scan_id == scan_id, ScanImage.frame_index == frame_index)
        .first()
    )
    if not row or not row.image_blob:
        raise HTTPException(status_code=404, detail="No stored image for this frame")
    return Response(
        content=bytes(row.image_blob),
        media_type=row.image_content_type or "image/jpeg",
    )


@router.get("/scans/{scan_id}", response_model=ScanOut, tags=["scans"])
def get_scan(scan_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return _scan_out(_get_scan(scan_id, user, db))


@router.post("/scans/{scan_id}/review", response_model=ScanOut, tags=["scans"])
@limiter.limit("30/minute")
def review_scan(
    request: Request,
    scan_id: str,
    body: ReviewIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Human-in-the-loop gate: confirm findings as-is, or admin-override to final."""
    from datetime import datetime

    rec = _get_scan(scan_id, user, db)
    if rec.status == "final":
        raise HTTPException(status_code=409, detail="Scan already finalized")
    if body.decision == "override" and user.role != "admin":
        raise HTTPException(status_code=403, detail="Override requires admin role")
    stored = json.loads(rec.results_json or "[]")
    if body.decision == "override":
        if not body.notes.strip():
            raise HTTPException(status_code=422, detail="Override requires review notes")
        overridden = [r["rule_id"] for r in stored if r.get("status") in ("FAIL", "NOT_FOUND")]
        rec.overrides_json = json.dumps(overridden)
        rec.verdict = "COMPLIANT"
        rec.compliant = True
    rec.status = "final"
    rec.reviewed_by = user.username
    rec.reviewed_at = datetime.now(UTC)
    rec.review_notes = body.notes[:2000]
    db.commit()
    db.refresh(rec)
    log.info("scan_reviewed", scan_id=rec.id, by=user.username, decision=body.decision)
    return _scan_out(rec)


@router.post("/scans/{scan_id}/explain", response_model=ExplainOut, tags=["scans"])
@limiter.limit("10/minute")
def explain_scan(
    request: Request, scan_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    """Optional Gemini explanation of a scan (off by default; needs LLM_PROVIDER=gemini + key)."""
    rec = _get_scan(scan_id, user, db)
    stored = json.loads(rec.results_json or "[]")
    prompt = build_explain_prompt(rec.verdict, stored, [], rec.ocr_confidence)
    try:
        text, model = explain_with_gemini(prompt)
    except LlmNotConfigured as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except LlmError as exc:
        log.error("llm_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=str(exc))
    log.info("scan_explained", scan_id=rec.id, by=user.username, model=model)
    return ExplainOut(
        explanation=text,
        provider=get_settings().llm_provider.lower(),
        model=model,
        request_id=_rid(),
    )


@router.get("/scans/{scan_id}/report", tags=["scans"])
def scan_report(scan_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    rec = _get_scan(scan_id, user, db)
    if rec.status != "final":
        raise HTTPException(
            status_code=409,
            detail="Report not final: an officer/admin must review this scan first "
            "(POST /scans/{id}/review)",
        )
    stored = json.loads(rec.results_json or "[]")
    warnings = []
    if rec.overrides_json and rec.overrides_json != "[]":
        warnings.append(f"Officer override by {rec.reviewed_by}: {rec.review_notes}")
    boxes, coord_w, coord_h = _stored_boxes(rec)
    pdf = build_report_pdf(rec, stored, warnings, boxes, coord_w, coord_h)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="scan-{scan_id}.pdf"'},
    )
