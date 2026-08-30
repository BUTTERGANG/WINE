"""Page routes — HTML pages rendered with Jinja2."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.wine import Wine, TastingNote
from backend.models.location import Location
from backend.models.user import User
from backend.services.auth import get_current_user
from backend.services.template import templates

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Landing page with feed and mini map."""
    user = await get_current_user(request, db)

    # Latest tastings
    stmt = (
        select(TastingNote)
        .where(TastingNote.is_public == True)
        .order_by(TastingNote.created_at.desc())
        .limit(20)
    )
    result = await db.execute(stmt)
    feed_notes = list(result.scalars().all())

    # Total counts
    wine_count = (await db.execute(select(func.count()).select_from(Wine))).scalar() or 0
    tasting_count = (await db.execute(select(func.count()).select_from(TastingNote))).scalar() or 0
    user_count = (await db.execute(select(func.count()).select_from(User))).scalar() or 0

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": user,
            "feed_notes": feed_notes,
            "wine_count": wine_count,
            "tasting_count": tasting_count,
            "user_count": user_count,
        },
    )


@router.get("/map", response_class=HTMLResponse)
async def map_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Full-screen map view."""
    user = await get_current_user(request, db)
    return templates.TemplateResponse("location/map.html", {"request": request, "user": user})


@router.get("/wine/add", response_class=HTMLResponse)
async def add_wine_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Add a wine manually or via scan."""
    user = await get_current_user(request, db)
    return templates.TemplateResponse("wine/add.html", {"request": request, "user": user})


@router.get("/wine/scan", response_class=HTMLResponse)
async def scan_wine_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Scan a bottle or glass."""
    user = await get_current_user(request, db)
    return templates.TemplateResponse("wine/scan.html", {"request": request, "user": user})


@router.get("/feed", response_class=HTMLResponse)
async def feed_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Full community feed page."""
    user = await get_current_user(request, db)
    return templates.TemplateResponse("community/feed.html", {"request": request, "user": user})


@router.get("/profile/{user_id}", response_class=HTMLResponse)
async def profile_page(user_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """User profile page — lookup by user ID or username."""
    result = await db.execute(
        select(User).where(
            (User.id == user_id) | (User.username == user_id)
        )
    )
    profile_user = result.scalar_one_or_none()
    if not profile_user:
        return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)

    current_user = await get_current_user(request, db)

    # User's tasting notes — eagerly load relationships
    from sqlalchemy.orm import selectinload
    stmt = (
        select(TastingNote)
        .options(selectinload(TastingNote.wine), selectinload(TastingNote.location))
        .where(
            TastingNote.user_id == user_id,
            TastingNote.is_public == True if current_user and current_user.id != user_id else True,
        )
        .order_by(TastingNote.created_at.desc())
        .limit(30)
    )
    result = await db.execute(stmt)
    notes = list(result.scalars().all())

    return templates.TemplateResponse(
        "community/profile.html",
        {
            "request": request,
            "profile_user": profile_user,
            "user": current_user,
            "notes": notes,
        },
    )