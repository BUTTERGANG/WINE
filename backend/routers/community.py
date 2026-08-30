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


# ── Feed ─────────────────────────────────────────────────────────────────


@router.get("/feed")
async def get_feed(
    request: Request,
    db: AsyncSession = Depends(get_db),
    limit: int = 30,
):
    """Recent public tasting notes for the global feed."""
    stmt = (
        select(TastingNote)
        .options(selectinload(TastingNote.wine), selectinload(TastingNote.user), selectinload(TastingNote.location))
        .where(TastingNote.is_public == True)
        .order_by(TastingNote.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    notes = result.scalars().all()

    items = []
    for note in notes:
        items.append({
            "id": note.id,
            "wine_id": note.wine.id,
            "wine_name": note.wine.display_name,
            "wine_type": note.wine.wine_type,
            "rating": note.rating,
            "username": note.user.display_name or note.user.username,
            "user_id": note.user.id,
            "user_avatar": note.user.avatar_url,
            "location_name": note.location.name if note.location else None,
            "notes": note.notes[:150] if note.notes else "",
            "created_at": note.created_at.isoformat(),
        })

    return {"items": items}


@router.get("/feed/personal")
async def get_personal_feed(
    request: Request,
    db: AsyncSession = Depends(get_db),
    limit: int = 30,
):
    """Feed filtered to users the current user follows."""
    user = await get_current_user(request, db)
    if not user:
        return {"items": []}

    # Get followed user IDs
    follow_result = await db.execute(
        select(Follow.followed_id).where(Follow.follower_id == user.id)
    )
    followed_ids = [row[0] for row in follow_result.all()] + [user.id]  # Include own tastings

    stmt = (
        select(TastingNote)
        .options(selectinload(TastingNote.wine), selectinload(TastingNote.user), selectinload(TastingNote.location))
        .where(TastingNote.is_public == True)
        .where(TastingNote.user_id.in_(followed_ids))
        .order_by(TastingNote.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    notes = result.scalars().all()

    items = []
    for note in notes:
        items.append({
            "id": note.id,
            "wine_id": note.wine.id,
            "wine_name": note.wine.display_name,
            "wine_type": note.wine.wine_type,
            "rating": note.rating,
            "username": note.user.display_name or note.user.username,
            "user_id": note.user.id,
            "user_avatar": note.user.avatar_url,
            "location_name": note.location.name if note.location else None,
            "notes": note.notes[:150] if note.notes else "",
            "created_at": note.created_at.isoformat(),
        })

    return {"items": items}


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
    if user.id == target_id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")

    stmt = select(Follow).where(
        Follow.follower_id == user.id,
        Follow.followed_id == target_id,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        await db.delete(existing)
        await db.commit()
        return {"following": False}

    follow = Follow(follower_id=user.id, followed_id=target_id)
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
    if not user or user.id == target_id:
        return {"following": False}

    stmt = select(Follow).where(
        Follow.follower_id == user.id,
        Follow.followed_id == target_id,
    )
    result = await db.execute(stmt)
    return {"following": result.scalar_one_or_none() is not None}


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


@router.get("/follows/{user_id}/list")
async def get_follow_lists(
    user_id: str,
    direction: str = "following",
    db: AsyncSession = Depends(get_db),
):
    """Get list of users a user follows or who follow them."""
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
    db.add(group)
    await db.flush()

    # Add owner as member
    member = GroupMember(group_id=group.id, user_id=user.id, role="owner")
    db.add(member)
    await db.commit()
    await db.refresh(group)

    return {"ok": True, "id": group.id, "name": group.name}


@router.get("/groups")
async def list_groups(
    request: Request,
    db: AsyncSession = Depends(get_db),
    limit: int = 30,
):
    """List public groups."""
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


@router.get("/groups/{group_id}")
async def get_group(
    group_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Group detail page."""
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)

    user = await get_current_user(request, db)

    # Members
    members = await db.execute(
        select(User)
        .join(GroupMember, GroupMember.user_id == User.id)
        .where(GroupMember.group_id == group_id)
    )
    member_list = members.scalars().all()

    # Group tasting notes
    member_ids = [m.id for m in member_list]
    stmt = (
        select(TastingNote)
        .options(selectinload(TastingNote.wine), selectinload(TastingNote.user), selectinload(TastingNote.location))
        .where(TastingNote.user_id.in_(member_ids), TastingNote.is_public == True)
        .order_by(TastingNote.created_at.desc())
        .limit(30)
    )
    result = await db.execute(stmt)
    notes = list(result.scalars().all())

    # Check membership
    is_member = False
    is_owner = False
    if user:
        for m in member_list:
            if m.id == user.id:
                is_member = True
                break

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