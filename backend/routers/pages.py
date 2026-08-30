"""Page routes — HTML pages rendered with Jinja2."""

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models.wine import Wine, TastingNote
from backend.models.location import Location
from backend.models.user import User
from backend.models.community import Follow, Group, GroupMember
from backend.services.auth import get_current_user
from backend.services.template import templates


def _not_found(request: Request):
    return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)

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
async def add_wine_page(
    request: Request,
    wine_id: str = Query("", description="Pre-fill the form from an existing wine"),
    db: AsyncSession = Depends(get_db),
):
    """Add a wine manually or via scan."""
    user = await get_current_user(request, db)
    prefill = None
    if wine_id:
        result = await db.execute(select(Wine).where(Wine.id == wine_id))
        prefill = result.scalar_one_or_none()
    return templates.TemplateResponse(
        "wine/add.html", {"request": request, "user": user, "prefill": prefill}
    )


@router.get("/wine/scan", response_class=HTMLResponse)
async def scan_wine_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Scan a bottle or glass."""
    user = await get_current_user(request, db)
    return templates.TemplateResponse("wine/scan.html", {"request": request, "user": user})


@router.get("/wine/{wine_id}", response_class=HTMLResponse)
async def wine_detail_page(wine_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Wine detail page."""
    result = await db.execute(
        select(Wine).options(selectinload(Wine.tasting_notes)).where(Wine.id == wine_id)
    )
    wine = result.scalar_one_or_none()
    if not wine:
        return _not_found(request)

    user = await get_current_user(request, db)
    ratings = [tn.rating for tn in wine.tasting_notes if tn.rating]
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None

    return templates.TemplateResponse(
        "wine/detail.html",
        {"request": request, "wine": wine, "user": user, "avg_rating": avg_rating},
    )


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
        return _not_found(request)

    current_user = await get_current_user(request, db)

    # User's tasting notes — eagerly load relationships
    stmt = (
        select(TastingNote)
        .options(selectinload(TastingNote.wine), selectinload(TastingNote.location))
        .where(
            TastingNote.user_id == profile_user.id,
            TastingNote.is_public == True if not current_user or current_user.id != profile_user.id else True,
        )
        .order_by(TastingNote.created_at.desc())
        .limit(30)
    )
    result = await db.execute(stmt)
    notes = list(result.scalars().all())

    # Stats
    total_tastings = await db.execute(
        select(func.count()).select_from(TastingNote).where(TastingNote.user_id == profile_user.id)
    )
    unique_wines = await db.execute(
        select(func.count(func.distinct(TastingNote.wine_id)))
        .where(TastingNote.user_id == profile_user.id)
    )
    unique_venues = await db.execute(
        select(func.count(func.distinct(TastingNote.location_id)))
        .where(
            TastingNote.user_id == profile_user.id,
            TastingNote.location_id.isnot(None),
        )
    )
    follow_counts = await db.execute(
        select(func.count()).select_from(Follow).where(Follow.followed_id == profile_user.id)
    )
    following_counts = await db.execute(
        select(func.count()).select_from(Follow).where(Follow.follower_id == profile_user.id)
    )

    # Check if current user follows this profile
    is_following = False
    if current_user and current_user.id != profile_user.id:
        f_result = await db.execute(
            select(Follow).where(
                Follow.follower_id == current_user.id,
                Follow.followed_id == profile_user.id,
            )
        )
        is_following = f_result.scalar_one_or_none() is not None

    return templates.TemplateResponse(
        "community/profile.html",
        {
            "request": request,
            "profile_user": profile_user,
            "user": current_user,
            "notes": notes,
            "total_tastings": total_tastings.scalar() or 0,
            "unique_wines": unique_wines.scalar() or 0,
            "unique_venues": unique_venues.scalar() or 0,
            "followers_count": follow_counts.scalar() or 0,
            "following_count": following_counts.scalar() or 0,
            "is_following": is_following,
        },
    )


@router.get("/groups", response_class=HTMLResponse)
async def groups_list_page(request: Request, db: AsyncSession = Depends(get_db)):
    """List all public wine groups."""
    user = await get_current_user(request, db)
    return templates.TemplateResponse("community/groups.html", {"request": request, "user": user})


@router.get("/group/{group_id}", response_class=HTMLResponse)
async def group_detail_page(group_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Group detail page."""
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        return _not_found(request)

    user = await get_current_user(request, db)

    members = await db.execute(
        select(User)
        .join(GroupMember, GroupMember.user_id == User.id)
        .where(GroupMember.group_id == group_id)
    )
    member_list = members.scalars().all()

    member_ids = [m.id for m in member_list]
    notes = []
    if member_ids:
        stmt = (
            select(TastingNote)
            .options(
                selectinload(TastingNote.wine),
                selectinload(TastingNote.user),
                selectinload(TastingNote.location),
            )
            .where(TastingNote.user_id.in_(member_ids), TastingNote.is_public == True)
            .order_by(TastingNote.created_at.desc())
            .limit(30)
        )
        result = await db.execute(stmt)
        notes = list(result.scalars().all())

    is_member = bool(user and any(m.id == user.id for m in member_list))

    return templates.TemplateResponse(
        "community/group_detail.html",
        {
            "request": request,
            "group": group,
            "user": user,
            "members": member_list,
            "notes": notes,
            "is_member": is_member,
        },
    )


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Personal dashboard with taste profile and recommendations."""
    user = await get_current_user(request, db)
    profile = None
    recommendations = []
    if user:
        from backend.services.taste_profile import compute_taste_profile, get_recommendations
        profile = await compute_taste_profile(user.id, db)
        recommendations = await get_recommendations(user.id, db, 6)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "profile": profile,
            "recommendations": recommendations,
        },
    )