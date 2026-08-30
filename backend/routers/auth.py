"""Auth routes — register, login, logout."""

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.user import User
from backend.services.auth import (
    hash_password,
    verify_password,
    create_session,
    delete_session,
    get_current_user,
    get_session_cookie,
)
from backend.services.template import templates

router = APIRouter(prefix="/api/auth", tags=["auth"])


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
    # Check for existing user
    result = await db.execute(select(User).where((User.email == email) | (User.username == username)))
    if result.scalar_one_or_none():
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
    await db.commit()

    token = await create_session(user.id)
    resp = RedirectResponse(url="/", status_code=303)
    cookie = get_session_cookie(token)
    resp.set_cookie(**cookie)
    return resp


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
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
    cookie = get_session_cookie(token)
    resp.set_cookie(**cookie)
    return resp


@router.post("/logout")
async def logout(request: Request):
    token = request.cookies.get("session_token")
    if token:
        await delete_session(token)
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie("session_token", path="/")
    return resp