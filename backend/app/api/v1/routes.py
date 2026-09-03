import dataclasses
import json
from datetime import UTC

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger, request_id_ctx
from app.core.rate_limit import limiter
from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.db.session import Base, engine, get_db
from app.models.tables import ScanRecord, User
from app.schemas.schemas import (
    CheckOut,
    ComplianceOut,
    DeclarationIn,
    ExplainOut,
    RegisterIn,
    ReviewIn,
    ScanOut,
    ScanSummaryOut,
    TokenOut,
    WordBoxOut,
)
from app.services.extraction import extract_fields
from app.services.llm import LlmError, LlmNotConfigured, build_explain_prompt, explain_with_gemini
from app.services.ocr import run_ocr, word_boxes
from app.services.report import build_report_pdf
from app.services.rule_engine import ProductDeclaration, evaluate_compliance
from app.services.vision import (
    detect_ppm_from_reference_card,
    font_height_mm,
    preprocess_for_ocr,
)

router = APIRouter()
log = get_logger("api")
bearer = HTTPBearer(auto_error=False)

Base.metadata.create_all(bind=engine)


def _rid() -> str:
    return request_id_ctx.get()


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
        clean = preprocess_for_ocr(raw)
        ocr = run_ocr(clean)
        boxes = word_boxes(clean)
    except Exception as exc:
        log.error("ocr_failed", error=str(exc))
        raise HTTPException(status_code=502, detail="OCR processing failed")
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
    rec = ScanRecord(
        owner_id=user.id,
        request_id=_rid(),
        ocr_text=ocr.text[:8000],
        ocr_engine=ocr.engine,
        ocr_confidence=ocr.confidence,
        font_height_mm=font_mm,
        compliant=report.compliant,
        verdict=report.verdict,
        results_json=json.dumps([dataclasses.asdict(r) for r in report.results]),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    log.info("scan_done", scan_id=rec.id, compliant=report.compliant, engine=ocr.engine)
    return ScanOut(
        id=rec.id,
        request_id=rec.request_id,
        status=rec.status,
        ocr_engine=ocr.engine,
        ocr_text=ocr.text[:2000],
        ocr_confidence=ocr.confidence,
        font_height_mm=font_mm,
        verdict=report.verdict,
        compliant=report.compliant,
        results=_checks(report),
        warnings=report.warnings,
        boxes=[WordBoxOut(**dataclasses.asdict(b)) for b in boxes[:500]],
    )


def _get_scan(scan_id: str, user: User, db: Session) -> ScanRecord:
    rec = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Scan not found")
    if user.role != "admin" and rec.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not your scan")
    return rec


@router.get("/scans", response_model=list[ScanSummaryOut], tags=["scans"])
def list_scans(db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = db.query(ScanRecord)
    if user.role != "admin":
        q = q.filter(ScanRecord.owner_id == user.id)
    q = q.order_by(ScanRecord.created_at.desc()).limit(100)
    return [
        ScanSummaryOut(
            id=r.id,
            verdict=r.verdict,
            compliant=r.compliant,
            status=r.status,
            ocr_engine=r.ocr_engine,
            created_at=r.created_at.isoformat(),
        )
        for r in q.all()
    ]


def _scan_out(rec: ScanRecord) -> ScanOut:
    stored = json.loads(rec.results_json or "[]")
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
    pdf = build_report_pdf(rec, stored, warnings)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="scan-{scan_id}.pdf"'},
    )
