"""Auth service — password hashing, signed session cookies."""

import bcrypt
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Request, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.user import User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


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
    """No-op — logout clears the cookie client-side."""
    return None


async def get_current_user(request: Request, db: AsyncSession) -> User | None:
    token = request.cookies.get("session_token")
    if not token:
        return None
    return await get_user_from_token(token, db)


async def require_user(request: Request, db: AsyncSession) -> User:
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def get_session_cookie(token: str) -> dict:
    return {
        "key": "session_token",
        "value": token,
        "httponly": True,
        "max_age": _MAX_AGE,
        "samesite": "lax",
        "path": "/",
        "secure": settings.secure_cookies,
    }
