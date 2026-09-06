from typing import Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings

settings = get_settings()
connect_args: dict[str, Any] = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
if settings.database_url.startswith("sqlite"):
    # Wait (don't instantly fail) when an OCR write holds the lock.
    connect_args["timeout"] = 30
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _connection_record) -> None:
    """WAL mode: thumbnail/history reads never block OCR writes (and vice versa).

    Single-process app (one uvicorn worker + threads): WAL is strictly safer
    than the default rollback journal under this exact concurrency shape.
    Best-effort — a failure must never break startup.
    """
    try:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()
    except Exception:  # noqa: S110 — pragmas are optional tuning, not correctness
        pass


def ensure_columns() -> None:
    """Idempotent lightweight migration for columns added after first deploy.

    `Base.metadata.create_all` only creates missing TABLES, so nullable
    columns added to ScanRecord need explicit ALTERs on existing databases.
    Safe to run on every startup; failures on one column never block others.
    Uses BYTEA on PostgreSQL (BLOB is not a pg type) and BLOB on SQLite.
    """
    dialect = engine.dialect.name
    blob_type = "BYTEA" if dialect == "postgresql" else "BLOB"
    alters = [
        f"ALTER TABLE scans ADD COLUMN image_blob {blob_type}",
        "ALTER TABLE scans ADD COLUMN image_content_type VARCHAR(32) DEFAULT 'image/jpeg'",
        "ALTER TABLE scans ADD COLUMN boxes_json TEXT DEFAULT '[]'",
        "ALTER TABLE scans ADD COLUMN ocr_width INTEGER",
        "ALTER TABLE scans ADD COLUMN ocr_height INTEGER",
        "ALTER TABLE scans ADD COLUMN product_name VARCHAR(160) DEFAULT ''",
        "ALTER TABLE scans ADD COLUMN brand_name VARCHAR(160) DEFAULT ''",
        "ALTER TABLE scans ADD COLUMN category VARCHAR(80) DEFAULT ''",
        "ALTER TABLE scans ADD COLUMN ppm_used FLOAT",
        "ALTER TABLE scans ADD COLUMN frames_json TEXT DEFAULT '[]'",
        "ALTER TABLE scans ADD COLUMN scan_lat FLOAT",
        "ALTER TABLE scans ADD COLUMN scan_lon FLOAT",
        "ALTER TABLE scans ADD COLUMN warnings_json TEXT DEFAULT '[]'",
        "ALTER TABLE scans ADD COLUMN has_image BOOLEAN DEFAULT 0",
        "ALTER TABLE scans ADD COLUMN declaration_json TEXT DEFAULT '{}'",
        "ALTER TABLE scans ADD COLUMN corrected_by VARCHAR(64) DEFAULT ''",
        "ALTER TABLE scans ADD COLUMN corrected_at TIMESTAMP",
        "ALTER TABLE scans ADD COLUMN finding_overrides_json TEXT DEFAULT '{}'",
    ]
    with engine.begin() as conn:
        for ddl in alters:
            try:
                conn.execute(text(ddl))
            except Exception:  # noqa: S110 — column already exists; that is the expected path
                pass
        try:
            # One-time backfill for pre-flag rows; harmless to repeat.
            conn.execute(text("UPDATE scans SET has_image = (image_blob IS NOT NULL)"))
        except Exception:  # noqa: S110 — keeps booting on exotic backends
            pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
