"""Community routes — feed, follows, groups."""

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.wine import Wine, TastingNote
from backend.models.location import Location
from backend.models.user import User
from backend.models.community import Follow, Group, GroupMember
from backend.services.auth import get_current_user
from backend.services.template import templates

router = APIRouter(prefix="/api", tags=["community"])


@router.get("/feed")
async def get_feed(
    request: Request,
    db: AsyncSession = Depends(get_db),
    limit: int = 30,
):
    """Recent public tasting notes for the feed."""
    stmt = (
        select(TastingNote, Wine, User)
        .join(Wine, TastingNote.wine_id == Wine.id)
        .join(User, TastingNote.user_id == User.id)
        .where(TastingNote.is_public == True)
        .order_by(TastingNote.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()

    items = []
    for note, wine, user in rows:
        # Fetch location separately if exists
        location_name = None
        if note.location_id:
            loc_result = await db.execute(select(Location).where(Location.id == note.location_id))
            loc = loc_result.scalar_one_or_none()
            if loc:
                location_name = loc.name

        items.append({
            "id": note.id,
            "wine_id": wine.id,
            "wine_name": wine.display_name,
            "wine_type": wine.wine_type,
            "rating": note.rating,
            "username": user.display_name or user.username,
            "user_id": user.id,
            "user_avatar": user.avatar_url,
            "location_name": location_name,
            "notes": note.notes[:150] if note.notes else "",
            "created_at": note.created_at.isoformat(),
        })

    return {"items": items}


@router.post("/follow/{user_id}")
async def toggle_follow(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Follow or unfollow a user."""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if user.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")

    stmt = select(Follow).where(
        Follow.follower_id == user.id,
        Follow.followed_id == user_id,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        await db.delete(existing)
        await db.commit()
        return {"following": False}

    follow = Follow(follower_id=user.id, followed_id=user_id)
    db.add(follow)
    await db.commit()
    return {"following": True}


@router.get("/follows/{user_id}")
async def get_follow_counts(user_id: str, db: AsyncSession = Depends(get_db)):
    """Get follower/following counts."""
    following = await db.execute(
        select(func.count()).select_from(Follow).where(Follow.follower_id == user_id)
    )
    followers = await db.execute(
        select(func.count()).select_from(Follow).where(Follow.followed_id == user_id)
    )
    return {
        "following_count": following.scalar() or 0,
        "followers_count": followers.scalar() or 0,
    }