import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta

from jose import jwt  # type: ignore[import-untyped]  # python-jose ships no stubs

from app.core.config import get_settings
from app.core.logging import get_logger


def hash_password(password: str) -> str:
    """bcrypt if available, else PBKDF2-SHA256 fallback (no passlib dependency)."""
    try:
        import bcrypt  # type: ignore

        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    except Exception:
        salt = os.urandom(16).hex()
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
        return f"pbkdf2${salt}${dk}"


def verify_password(plain: str, hashed: str) -> bool:
    bcrypt_ok: bool | None = None
    try:
        import bcrypt  # type: ignore

        if hashed.startswith(("$2b$", "$2a$")):
            bcrypt_ok = bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception as exc:
        get_logger("auth").warning("bcrypt_verify_failed", error=str(exc))
    if bcrypt_ok is not None:
        return bcrypt_ok
    try:
        scheme, salt, dk = hashed.split("$")
        if scheme != "pbkdf2":
            return False
        check = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), 200_000).hex()
        return hmac.compare_digest(check, dk)
    except Exception:
        return False


def create_access_token(subject: str, role: str = "officer") -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {"sub": subject, "role": role, "exp": expire}, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )


def decode_token(token: str) -> tuple[str, str]:
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    return str(payload.get("sub", "")), str(payload.get("role", "officer"))
