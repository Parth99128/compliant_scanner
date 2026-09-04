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


class ScanOut(BaseModel):
    id: str
    request_id: str
    status: str = "pending_review"  # pending_review | final
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


class ErrorOut(BaseModel):
    detail: str
    request_id: str


class ExplainOut(BaseModel):
    explanation: str
    provider: str = "gemini"
    model: str = ""
    request_id: str
