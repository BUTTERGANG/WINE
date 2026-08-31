"""Community routes — feed, follows, groups."""

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models.wine import Wine, TastingNote
from backend.models.location import Location
from backend.models.user import User
from backend.models.community import Follow, Group, GroupMember
from backend.services.auth import get_current_user, require_user
from backend.services.template import templates

router = APIRouter(prefix="/api", tags=["community"])


async def _resolve_user_id(value: str, db: AsyncSession) -> str | None:
    """Accept a user id or a username, return the canonical id (or None)."""
    result = await db.execute(
        select(User.id).where((User.id == value) | (User.username == value))
    )
    return result.scalar_one_or_none()


def _feed_item(note: TastingNote) -> dict:
    return {
        "id": note.id,
        "wine_id": note.wine.id,
        "wine_name": note.wine.display_name,
        "wine_type": note.wine.wine_type,
        "rating": note.rating,
        "username": note.user.display_name or note.user.username,
        "user_id": note.user.id,
        "user_avatar": note.user.avatar_url,
        "location_name": note.location.name if note.location else None,
        "location_id": note.location.id if note.location else None,
        "notes": note.notes[:280] if note.notes else "",
        "photo_url": note.photo_url or "",
        "created_at": note.created_at.isoformat(),
    }


# ── Feed ─────────────────────────────────────────────────────────────────


@router.get("/feed")
async def get_feed(
    request: Request,
    db: AsyncSession = Depends(get_db),
    limit: int = 30,
    offset: int = 0,
):
    """Recent public tasting notes for the global feed. Supports offset pagination."""
    stmt = (
        select(TastingNote)
        .options(selectinload(TastingNote.wine), selectinload(TastingNote.user), selectinload(TastingNote.location))
        .where(TastingNote.is_public == True)
        .order_by(TastingNote.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    notes = result.scalars().all()
    has_more = len(notes) >= limit

    return {"items": [_feed_item(n) for n in notes], "has_more": has_more}


@router.get("/feed/personal")
async def get_personal_feed(
    request: Request,
    db: AsyncSession = Depends(get_db),
    limit: int = 30,
    offset: int = 0,
):
    """Feed filtered to users the current user follows. Supports offset pagination."""
    user = await get_current_user(request, db)
    if not user:
        return {"items": []}

    follow_result = await db.execute(
        select(Follow.followed_id).where(Follow.follower_id == user.id)
    )
    followed_ids = [row[0] for row in follow_result.all()] + [user.id]

    stmt = (
        select(TastingNote)
        .options(selectinload(TastingNote.wine), selectinload(TastingNote.user), selectinload(TastingNote.location))
        .where(TastingNote.is_public == True)
        .where(TastingNote.user_id.in_(followed_ids))
        .order_by(TastingNote.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    notes = result.scalars().all()
    has_more = len(notes) >= limit

    return {"items": [_feed_item(n) for n in notes], "has_more": has_more}


# ── Follows ──────────────────────────────────────────────────────────────


@router.post("/follow/{target_id}")
async def toggle_follow(
    target_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Follow or unfollow a user."""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    target = await _resolve_user_id(target_id, db)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == target:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")

    stmt = select(Follow).where(
        Follow.follower_id == user.id,
        Follow.followed_id == target,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        await db.delete(existing)
        await db.commit()
        return {"following": False}

    follow = Follow(follower_id=user.id, followed_id=target)
    db.add(follow)
    await db.commit()
    return {"following": True}


@router.get("/follow/{target_id}/status")
async def get_follow_status(
    target_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Check if current user follows the target user."""
    user = await get_current_user(request, db)
    target = await _resolve_user_id(target_id, db) if user else None
    if not user or not target or user.id == target:
        return {"following": False}

    stmt = select(Follow).where(
        Follow.follower_id == user.id,
        Follow.followed_id == target,
    )
    result = await db.execute(stmt)
    return {"following": result.scalar_one_or_none() is not None}


@router.get("/follows/{user_id}")
async def get_follow_counts(user_id: str, db: AsyncSession = Depends(get_db)):
    """Get follower/following counts."""
    target = await _resolve_user_id(user_id, db) or user_id
    following = await db.execute(
        select(func.count()).select_from(Follow).where(Follow.follower_id == target)
    )
    followers = await db.execute(
        select(func.count()).select_from(Follow).where(Follow.followed_id == target)
    )
    return {
        "following_count": following.scalar() or 0,
        "followers_count": followers.scalar() or 0,
    }


@router.get("/follows/{user_id}/list")
async def get_follow_lists(
    user_id: str,
    direction: str = "following",
    db: AsyncSession = Depends(get_db),
):
    """Get list of users a user follows or who follow them."""
    user_id = await _resolve_user_id(user_id, db) or user_id
    if direction == "following":
        stmt = (
            select(User)
            .join(Follow, Follow.followed_id == User.id)
            .where(Follow.follower_id == user_id)
        )
    else:
        stmt = (
            select(User)
            .join(Follow, Follow.follower_id == User.id)
            .where(Follow.followed_id == user_id)
        )
    result = await db.execute(stmt)
    users = result.scalars().all()
    return {"users": [
        {"id": u.id, "username": u.username, "display_name": u.display_name or u.username}
        for u in users
    ]}


# ── Groups ───────────────────────────────────────────────────────────────


@router.post("/groups")
async def create_group(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create a new wine group."""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    form = await request.form()
    group = Group(
        name=form.get("name", "New Group"),
        description=form.get("description", ""),
        is_private=form.get("is_private", "0") == "1",
        owner_id=user.id,
    )
    if not (group.name or "").strip():
        raise HTTPException(status_code=400, detail="Group name is required")

    db.add(group)
    await db.flush()

    # Add owner as member
    member = GroupMember(group_id=group.id, user_id=user.id, role="owner")
    db.add(member)
    await db.commit()

    # Return the refreshed list so the UI can swap it in directly.
    return {"ok": True, "id": group.id, "name": group.name, **await _list_public_groups(db)}


async def _list_public_groups(db: AsyncSession, limit: int = 30) -> dict:
    stmt = (
        select(Group)
        .where(Group.is_private == False)
        .order_by(Group.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    groups = result.scalars().all()

    results = []
    for g in groups:
        count = await db.execute(
            select(func.count()).select_from(GroupMember).where(GroupMember.group_id == g.id)
        )
        results.append({
            "id": g.id,
            "name": g.name,
            "description": g.description,
            "member_count": count.scalar() or 0,
            "created_at": g.created_at.isoformat(),
        })
    return {"groups": results}


@router.get("/groups")
async def list_groups(
    request: Request,
    db: AsyncSession = Depends(get_db),
    limit: int = 30,
):
    """List public groups."""
    return await _list_public_groups(db, limit)


@router.post("/groups/{group_id}/join")
async def join_group(
    group_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Join a group."""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Check group exists
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Check if already member
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user.id,
        )
    )
    if result.scalar_one_or_none():
        return {"ok": True, "already_member": True}

    member = GroupMember(group_id=group_id, user_id=user.id, role="member")
    db.add(member)
    await db.commit()

    return {"ok": True, "already_member": False}


# ── Taste Profile & Recommendations ──────────────────────────────────────


@router.get("/profile/{user_id}/taste")
async def get_taste_profile(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Compute and return a user's taste profile."""
    from backend.services.taste_profile import compute_taste_profile

    resolved = await _resolve_user_id(user_id, db)
    if not resolved:
        if request.headers.get("HX-Request") == "true":
            return templates.TemplateResponse(
                "components/taste_profile.html",
                {"request": request, "profile": {"has_data": False}},
            )
        return {"has_data": False}

    profile = await compute_taste_profile(resolved, db)

    # If HTMX request, render the template partial
    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(
            "components/taste_profile.html",
            {"request": request, "profile": profile},
        )

    return profile


@router.get("/recommendations")
async def recommendations_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_db),
    limit: int = 5,
):
    """Get personalized wine recommendations for the current user."""
    user = await get_current_user(request, db)
    if not user:
        return {"items": []}

    from backend.services.taste_profile import get_recommendations
    items = await get_recommendations(user.id, db, limit)
    return {"items": items}