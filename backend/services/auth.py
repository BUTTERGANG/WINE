"""Auth service — password hashing, session tokens."""

import hashlib
import os
import secrets
from datetime import datetime, timedelta

import bcrypt
from fastapi import Request, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.user import User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def generate_session_token() -> str:
    return secrets.token_hex(32)


# In-memory session store (dev only; swap to Redis or DB for prod)
# Maps token -> (user_id, expiry)
_session_store: dict[str, tuple[str, datetime]] = {}


async def create_session(user_id: str) -> str:
    token = generate_session_token()
    expiry = datetime.utcnow() + timedelta(hours=settings.session_ttl_hours)
    _session_store[token] = (user_id, expiry)
    return token


async def get_user_from_token(token: str, db: AsyncSession) -> User | None:
    data = _session_store.get(token)
    if not data:
        return None
    user_id, expiry = data
    if datetime.utcnow() > expiry:
        del _session_store[token]
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def delete_session(token: str):
    _session_store.pop(token, None)


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
        "max_age": settings.session_ttl_hours * 3600,
        "samesite": "lax",
        "path": "/",
    }