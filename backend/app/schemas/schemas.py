from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class DeclarationIn(BaseModel):
    manufacturer_name: str | None = None
    manufacturer_address: str | None = None
    generic_name: str | None = None
    net_quantity_value: float | None = Field(default=None, gt=0)
    net_quantity_unit: str | None = None
    mrp: float | None = Field(default=None, gt=0)
    mrp_includes_taxes: bool = False
    mfg_date: date | None = None
    expiry_date: date | None = None
    consumer_care: str | None = None
    country_of_origin: str | None = None
    is_imported: bool = False
    min_font_height_mm: float | None = None  # legacy alias for numeral height
    min_numeral_height_mm: float | None = None
    min_letter_height_mm: float | None = None
    is_embossed: bool = False
    panel_area_cm2: float | None = Field(default=None, gt=0)
    min_width_to_height_ratio: float | None = None


class CheckOut(BaseModel):
    rule_id: str
    status: str = "PASS"  # PASS | FAIL | NOT_FOUND | NOT_ASSESSABLE
    passed: bool = True  # back-compat: status == PASS
    message: str
    field: str = ""
    citation: str = ""
    citation_verified: bool = False
    source_ref: str = ""
    observed: str | None = None
    expected: str | None = None
    severity: str = "info"
    remedy: str | None = None
    manual: bool = False  # officer-attested override of the machine finding
    # Failure guidance: why this outcome happened + exact next steps.
    # cause: "" | genuine | likely_genuine | possible_miss | unmeasured
    cause: str = ""
    why: str = ""
    next_steps: list[str] = []


class ComplianceOut(BaseModel):
    verdict: str = "INCOMPLETE"  # COMPLIANT | NON_COMPLIANT | INCOMPLETE
    compliant: bool = False  # back-compat: verdict == COMPLIANT
    results: list[CheckOut]
    warnings: list[str] = []
    request_id: str


class WordBoxOut(BaseModel):
    text: str
    x: int
    y: int
    w: int
    h: int
    confidence: float


class FrameOut(BaseModel):
    """One uploaded angle: its own OCR analysis + share of the merged text."""

    index: int = 0  # upload order (0-based)
    is_best: bool = True  # default view; text union led by this frame
    measured: bool = True  # Rule 7 sizes were measured on this frame
    url: str = ""  # relative image URL (best -> /scans/{id}/image)
    ocr_confidence: float = 0.0  # this frame's own read, 0-100 scale
    word_count: int = 0  # words this frame read on its own
    words_added: int = 0  # lines only this frame contributed to the union
    boxes: list[WordBoxOut] = []  # this frame's own word boxes (overlay)
    coord_w: int | None = None  # this frame's box coordinate space
    coord_h: int | None = None


class ScanOut(BaseModel):
    id: str
    request_id: str
    status: str = "pending_review"  # pending_review | final
    job_id: str | None = None  # async job that produced this scan (null for old rows)
    ocr_engine: str
    ocr_text: str
    ocr_confidence: float = 0.0
    font_height_mm: float | None = None
    verdict: str = "INCOMPLETE"
    compliant: bool = False
    results: list[CheckOut]
    warnings: list[str] = []
    boxes: list[WordBoxOut] = []
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    has_image: bool = False
    coord_w: int | None = None  # OCR box coordinate space (preprocessed px)
    coord_h: int | None = None
    product_name: str = ""
    brand_name: str = ""
    category: str = ""
    ppm_used: float | None = None
    frames: list[FrameOut] = []  # every uploaded angle + what it contributed
    measured_index: int | None = None  # angle Rule 7 sizes were measured on
    scan_lat: float | None = None  # GPS at upload (null when unavailable)
    scan_lon: float | None = None
    declaration: dict = {}  # evaluated Rule 6 + measurement snapshot (editable copy)
    corrected_by: str | None = None
    corrected_at: str | None = None


class ScanSummaryOut(BaseModel):
    id: str
    verdict: str = "INCOMPLETE"
    compliant: bool
    status: str = "pending_review"
    ocr_engine: str
    created_at: str
    preview: str = ""
    product_name: str = ""
    brand_name: str = ""
    category: str = ""  # first line of OCR text (label excerpt for lists)
    has_image: bool = False


class ReviewIn(BaseModel):
    decision: str = Field(pattern="^(confirm|override)$")
    notes: str = Field(default="", max_length=2000)


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default="officer", pattern="^(officer|admin)$")


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class JobOut(BaseModel):
    """Async analysis job: uploads return this instantly (202), verdict later."""

    job_id: str
    status: str = "queued"  # queued | working | done | failed
    kind: str = "scan"  # scan | merge
    frames_total: int = 1
    scan_id: str | None = None  # set when done
    error: str = ""  # set when failed
    request_id: str


class ErrorOut(BaseModel):
    detail: str
    request_id: str


class ExplainOut(BaseModel):
    explanation: str
    provider: str = "gemini"
    model: str = ""
    request_id: str


class ScanPreviewOut(BaseModel):
    """Lightweight live-camera frame analysis. No DB write, no stored scan."""

    ocr_engine: str
    ocr_text: str = ""
    ocr_confidence: float = 0.0
    word_count: int = 0
    font_height_mm: float | None = None
    ppm_used: float | None = None
    sharpness: float | None = None
    fields_found: dict[str, bool] = {}
    fields_count: int = 0
    fields_total: int = 6
    verdict: str = "INCOMPLETE"
    compliant: bool = False
    ready: bool = False
    ready_reason: str = ""
    boxes: list[WordBoxOut] = []
    coord_w: int | None = None
    coord_h: int | None = None
    request_id: str
