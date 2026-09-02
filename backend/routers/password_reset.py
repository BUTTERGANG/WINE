"""Password reset — token-based reset flow."""

import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from backend.config import settings
from backend.database import get_db
from backend.models.user import User
from backend.services.auth import hash_password, get_session_cookie, create_session
from backend.services.template import templates

router = APIRouter(prefix="/api/auth", tags=["auth"])

_reset_serializer = URLSafeTimedSerializer(settings.secret_key, salt="wine-password-reset")
TOKEN_MAX_AGE = 3600  # 1 hour


@router.get("/forgot-password")
async def forgot_password_page(request: Request):
    return templates.TemplateResponse("auth/forgot_password.html", {"request": request})


@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    email: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Generate a password reset token for the user."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    # Don't reveal if email exists
    reset_url = None
    if user:
        token = _reset_serializer.dumps(user.id)
        # In a real app, email this link. For demo, we show it.
        reset_url = f"/api/auth/reset-password?token={token}"
    
    return templates.TemplateResponse(
        "auth/forgot_password_sent.html",
        {"request": request, "reset_url": reset_url, "email": email},
    )


@router.get("/reset-password")
async def reset_password_page(request: Request, token: str = ""):
    """Show reset password form."""
    try:
        user_id = _reset_serializer.loads(token, max_age=TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return templates.TemplateResponse(
            "auth/reset_password.html",
            {"request": request, "error": "Invalid or expired token", "token": token},
            status_code=400,
        )
    
    return templates.TemplateResponse(
        "auth/reset_password.html",
        {"request": request, "token": token},
    )


@router.post("/reset-password")
async def reset_password(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Reset password using a valid token."""
    try:
        user_id = _reset_serializer.loads(token, max_age=TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return templates.TemplateResponse(
            "auth/reset_password.html",
            {"request": request, "error": "Invalid or expired token", "token": token},
            status_code=400,
        )
    
    if len(password) < 8:
        return templates.TemplateResponse(
            "auth/reset_password.html",
            {"request": request, "error": "Password must be at least 8 characters", "token": token},
            status_code=400,
        )
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.password_hash = hash_password(password)
    await db.commit()
    
    # Auto-login after reset
    session_token = await create_session(user.id)
    resp = HTMLResponse("<html><body>Password reset! <a href='/'>Go home</a></body></html>")
    cookie = get_session_cookie(session_token)
    resp.set_cookie(**cookie)
    return resp
