import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ScanRecord(Base):
    __tablename__ = "scans"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex[:16])
    owner_id: Mapped[str] = mapped_column(String(32), default="")
    request_id: Mapped[str] = mapped_column(String(32), default="")
    ocr_text: Mapped[str] = mapped_column(Text, default="")
    ocr_engine: Mapped[str] = mapped_column(String(64), default="none")
    ocr_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    font_height_mm: Mapped[float] = mapped_column(Float, nullable=True, default=None)
    compliant: Mapped[bool] = mapped_column(Boolean, default=False)
    verdict: Mapped[str] = mapped_column(String(16), default="INCOMPLETE")
    status: Mapped[str] = mapped_column(String(16), default="pending_review")
    reviewed_by: Mapped[str] = mapped_column(String(64), default="")
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, default=None)
    review_notes: Mapped[str] = mapped_column(Text, default="")
    overrides_json: Mapped[str] = mapped_column(Text, default="[]")
    results_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Downscaled original capture for the scan viewer (nullable: pre-feature rows).
    image_blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=True, default=None)
    image_content_type: Mapped[str] = mapped_column(String(32), default="image/jpeg")
    # Product identity: auto-filled from extraction at scan time, editable by
    # officers afterwards (review/label correction workflow).
    product_name: Mapped[str] = mapped_column(String(160), default="")
    brand_name: Mapped[str] = mapped_column(String(160), default="")
    category: Mapped[str] = mapped_column(String(80), default="")
    # Calibration actually used (explicit PPM or auto-detected card). Null =
    # uncalibrated scan; shown in the UI so officers trust the Rule 7 outcome.
    ppm_used: Mapped[float] = mapped_column(Float, nullable=True, default=None)
    # OCR word boxes in preprocessed-image pixel space + that space's dims,
    # so the viewer overlay aligns at any display size (SVG viewBox).
    boxes_json: Mapped[str] = mapped_column(Text, default="[]")
    ocr_width: Mapped[int] = mapped_column(nullable=True, default=None)
    ocr_height: Mapped[int] = mapped_column(nullable=True, default=None)
    # Per-frame analysis summary for multi-angle merges:
    # [{index, is_best, ocr_confidence, word_count, words_added}].
    # Single captures store one entry. Pre-feature rows use "[]".
    frames_json: Mapped[str] = mapped_column(Text, default="[]")


class ScanImage(Base):
    """Extra angle captures of a merge (frame 0/best lives on ScanRecord.image_blob).

    Only non-best merge frames are stored here, in upload order. Single
    captures and pre-feature merges have no rows — the viewer falls back to
    the primary image. Created by create_all (new table, no ALTER needed).
    """

    __tablename__ = "scan_images"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex[:16])
    scan_id: Mapped[str] = mapped_column(String(32), index=True, default="")
    frame_index: Mapped[int] = mapped_column(default=0)
    image_blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=True, default=None)
    image_content_type: Mapped[str] = mapped_column(String(32), default="image/jpeg")


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex[:16])
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(16), default="officer")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
