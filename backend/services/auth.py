"""Auth service — password hashing, signed session cookies, request deps."""

import re

import bcrypt
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Request, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.models.user import User


# bcrypt hashes at most 72 bytes and *raises* on longer input, so clamp first.
_BCRYPT_MAX_BYTES = 72

MIN_PASSWORD_LENGTH = 8
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,30}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clamp(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_clamp(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_clamp(password), password_hash.encode("utf-8"))
    except ValueError:
        return False


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_credentials(username: str, email: str, password: str) -> str | None:
    """Return a human-readable error, or ``None`` when the input is acceptable."""
    if not _USERNAME_RE.match(username or ""):
        return "Username must be 3–30 characters — letters, numbers, dashes, underscores."
    if not _EMAIL_RE.match(email or ""):
        return "Enter a valid email address."
    if len(password or "") < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    return None


# Stateless signed-cookie sessions — survive restarts, no server-side store.
_serializer = URLSafeTimedSerializer(settings.secret_key, salt="wine-session")
_MAX_AGE = settings.session_ttl_hours * 3600


async def create_session(user_id: str) -> str:
    """Return a signed token embedding the user id."""
    return _serializer.dumps(user_id)


async def get_user_from_token(token: str, db: AsyncSession) -> User | None:
    try:
        user_id = _serializer.loads(token, max_age=_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def delete_session(token: str) -> None:
    """No-op — logout clears the cookie client-side (stateless sessions)."""
    return None


async def get_current_user(request: Request, db: AsyncSession) -> User | None:
    token = request.cookies.get("session_token")
    if not token:
        return None
    return await get_user_from_token(token, db)


# ── FastAPI dependencies ─────────────────────────────────────────────────


async def current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User | None:
    """Optional authenticated user, for routes that render differently when signed in."""
    return await get_current_user(request, db)


async def required_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    """Authenticated user or 401."""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


# Back-compat alias — older call sites pass (request, db) positionally.
require_user = required_user


def get_session_cookie(token: str) -> dict:
    return {
        "key": "session_token",
        "value": token,
        "httponly": True,
        "max_age": _MAX_AGE,
        "samesite": "lax",
        "secure": not settings.debug,
        "path": "/",
    }
