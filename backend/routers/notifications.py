"""Notification routes — list, mark read, mark all read."""

from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.notifications import Notification
from backend.services.auth import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    request: Request,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's notifications."""
    user = await get_current_user(request, db)
    if not user:
        return {"items": [], "unread": 0}

    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    notifications = result.scalars().all()

    unread = sum(1 for n in notifications if not n.is_read)

    return {
        "items": [{
            "id": n.id,
            "type": n.type,
            "message": n.message,
            "link": n.link,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat(),
            "actor_name": n.actor.display_name if n.actor else None,
        } for n in notifications],
        "unread": unread,
    }


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Mark a notification as read."""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user.id)
        .values(is_read=True)
    )
    await db.commit()
    return {"ok": True}


@router.post("/read-all")
async def mark_all_read(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Mark all notifications as read."""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    await db.execute(
        update(Notification)
        .where(Notification.user_id == user.id)
        .values(is_read=True)
    )
    await db.commit()
    return {"ok": True}


@router.get("/unread-count")
async def unread_count(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get the count of unread notifications."""
    user = await get_current_user(request, db)
    if not user:
        return {"count": 0}

    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user.id, Notification.is_read == False)
    )
    count = len(result.scalars().all())
    return {"count": count }
