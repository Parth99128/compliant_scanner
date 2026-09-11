from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULTS = {
    "change-me-in-env",
    "change-me-to-a-long-random-value",
    "replace-me-generate-with-secrets-token-hex-32",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_name: str = "DrishtiLM — LMPC Compliance Scanner"
    api_v1_prefix: str = "/api/v1"
    environment: str = "local"

    database_url: str = "sqlite:///./scanner.db"
    jwt_secret: str = "change-me-in-env"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    max_upload_mb: int = 10
    allowed_content_types: str = "image/jpeg,image/png,image/webp"
    rate_limit_scans: str = "20/minute"

    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000," "http://localhost:5174,http://127.0.0.1:5174"
    )

    cloud_vision_enabled: str = "false"

    # Optional Gemini/Gemma LLM adapter (off by default; core pipeline never needs it).
    # A Google AI Studio key works for both Gemini and Gemma models.
    llm_provider: str = "off"  # 'off' | 'gemini' | 'gemma'
    gemini_api_key: str = ""
    llm_model: str = "gemini-flash-lite-latest"

    # Optional Florence-2 VLM second-opinion OCR (local CPU, off by default).
    florence_enabled: str = "false"
    florence_model: str = "microsoft/Florence-2-base"

    # Optional TrOCR line re-reader (local CPU transformer, off by default).
    # Re-reads low-confidence OCR lines; never overrules strong Tesseract rows.
    trocr_enabled: str = "false"
    trocr_model: str = "microsoft/trocr-small-printed"

    # Optional generic local VLM reader (local CPU, off by default).
    # Slower than Florence-2; only consulted when enabled AND the read is weak.
    vlm_enabled: str = "false"
    vlm_model: str = "HuggingFaceTB/SmolVLM-256M-Instruct"

    # Optional Open Food Facts barcode cross-check (public data, silent fail).
    off_lookup_enabled: str = "true"

    @property
    def allowed_content_type_list(self) -> list[str]:
        return [c.strip() for c in self.allowed_content_types.split(",") if c.strip()]

    @model_validator(mode="after")
    def _refuse_default_secret_in_production(self) -> "Settings":
        if self.environment.lower() == "production" and self.jwt_secret in INSECURE_DEFAULTS:
            raise ValueError("JWT_SECRET must be set to a strong random value in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
