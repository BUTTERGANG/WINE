"""Auth routes — register, login, logout.

Canonical paths live under ``/api/auth/*``; friendly aliases (``/login``,
``/register``, ``/logout``) are registered on a second, prefix-less router so
links read naturally without breaking existing clients.
"""

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.user import User
from backend.services.auth import (
    hash_password,
    verify_password,
    create_session,
    delete_session,
    get_session_cookie,
    normalize_email,
    validate_credentials,
)
from backend.services.template import templates

router = APIRouter(prefix="/api/auth", tags=["auth"])
aliases = APIRouter(tags=["auth"])


@router.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse("auth/register.html", {"request": request})


@router.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    username = (username or "").strip()
    email = normalize_email(email)

    error = validate_credentials(username, email, password)
    if error:
        return templates.TemplateResponse(
            "auth/register.html", {"request": request, "error": error}, status_code=400
        )

    # Fast path: surface an obvious clash before hitting the unique constraint.
    existing = await db.execute(
        select(User).where((User.email == email) | (User.username == username))
    )
    if existing.scalar_one_or_none():
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": "Username or email already taken"},
            status_code=400,
        )

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        display_name=username,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        # Lost a race against a concurrent signup with the same username/email.
        await db.rollback()
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": "Username or email already taken"},
            status_code=400,
        )

    token = await create_session(user.id)
    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(**get_session_cookie(token))
    return resp


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    email = normalize_email(email)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Invalid email or password"},
            status_code=400,
        )

    token = await create_session(user.id)
    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(**get_session_cookie(token))
    return resp


@router.post("/logout")
async def logout(request: Request):
    token = request.cookies.get("session_token")
    if token:
        await delete_session(token)
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie("session_token", path="/")
    return resp


# ── Friendly aliases ─────────────────────────────────────────────────────

aliases.add_api_route("/login", login_page, methods=["GET"])
aliases.add_api_route("/register", register_page, methods=["GET"])
aliases.add_api_route("/login", login, methods=["POST"])
aliases.add_api_route("/register", register, methods=["POST"])
aliases.add_api_route("/logout", logout, methods=["POST"])
