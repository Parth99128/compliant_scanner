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
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Downscaled original capture for the scan viewer (nullable: pre-feature rows).
    image_blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=True, default=None)
    image_content_type: Mapped[str] = mapped_column(String(32), default="image/jpeg")
    # Display flag so list queries never touch the blob column (N+1 lazy loads
    # would make filtering slower, not faster). Backfilled by migration.
    has_image: Mapped[bool] = mapped_column(Boolean, default=False)
    # Product identity: auto-filled from extraction at scan time, editable by
    # officers afterwards (review/label correction workflow).
    product_name: Mapped[str] = mapped_column(String(160), default="")
    brand_name: Mapped[str] = mapped_column(String(160), default="")
    category: Mapped[str] = mapped_column(String(80), default="")
    # Full Rule 6 + measurement snapshot of the evaluated declaration, so an
    # officer correction re-runs the SAME rules (measurements preserved).
    declaration_json: Mapped[str] = mapped_column(Text, default="{}")
    corrected_by: Mapped[str] = mapped_column(String(64), default="")
    corrected_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, default=None)
    # Per-finding officer attestations {rule_id: {status?, observed?, by, at}}.
    # Machine results stay pristine in results_json; overlays apply at read.
    finding_overrides_json: Mapped[str] = mapped_column(Text, default="{}")
    # Calibration actually used (explicit PPM or auto-detected card). Null =
    # uncalibrated scan; shown in the UI so officers trust the Rule 7 outcome.
    ppm_used: Mapped[float] = mapped_column(Float, nullable=True, default=None)
    # GPS captured on the officer's device at upload (nullable: desktop
    # uploads and denied permissions). Shown on the report for legal trail.
    scan_lat: Mapped[float] = mapped_column(Float, nullable=True, default=None)
    scan_lon: Mapped[float] = mapped_column(Float, nullable=True, default=None)
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


class ScanJob(Base):
    """Async analysis job: uploads return 202 instantly, the verdict arrives later.

    Long multi-angle analyses must not hold an HTTP connection open for
    minutes — middleboxes (VPN NAT, proxies) reap quiet connections and the
    client sees a fake 500. The frontend polls GET /jobs/{id} instead.
    Created by create_all (new table, no ALTER needed).
    """

    __tablename__ = "scan_jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex[:16])
    owner_id: Mapped[str] = mapped_column(String(32), index=True, default="")
    request_id: Mapped[str] = mapped_column(String(32), default="")
    kind: Mapped[str] = mapped_column(String(16), default="scan")  # scan | merge
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|working|done|failed
    scan_id: Mapped[str] = mapped_column(String(32), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    frames_total: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex[:16])
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(16), default="officer")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
