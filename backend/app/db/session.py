from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings

settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def ensure_columns() -> None:
    """Idempotent lightweight migration for columns added after first deploy.

    `Base.metadata.create_all` only creates missing TABLES, so nullable
    columns added to ScanRecord need explicit ALTERs on existing databases.
    Safe to run on every startup; failures on one column never block others.
    """
    alters = [
        "ALTER TABLE scans ADD COLUMN image_blob BLOB",
        "ALTER TABLE scans ADD COLUMN image_content_type VARCHAR(32) DEFAULT 'image/jpeg'",
        "ALTER TABLE scans ADD COLUMN boxes_json TEXT DEFAULT '[]'",
        "ALTER TABLE scans ADD COLUMN ocr_width INTEGER",
        "ALTER TABLE scans ADD COLUMN ocr_height INTEGER",
        "ALTER TABLE scans ADD COLUMN product_name VARCHAR(160) DEFAULT ''",
        "ALTER TABLE scans ADD COLUMN brand_name VARCHAR(160) DEFAULT ''",
        "ALTER TABLE scans ADD COLUMN category VARCHAR(80) DEFAULT ''",
    ]
    with engine.begin() as conn:
        for ddl in alters:
            try:
                conn.execute(text(ddl))
            except Exception:  # noqa: S110 — column already exists; that is the expected path
                pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
