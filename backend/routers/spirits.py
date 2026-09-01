"""Spirit & Distillery routes — CRUD, search, distillery pages, feed."""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Form, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import settings
from backend.database import get_db
from backend.models.spirit import Spirit, SpiritTastingNote, Distillery, SpiritWishlistEntry
from backend.models.community import GroupMember
from backend.models.user import User
from backend.services.auth import get_current_user
from backend.services.template import templates

router = APIRouter(prefix="/api/spirits", tags=["spirits"])
UPLOAD_DIR = Path(settings.upload_dir)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ── Search ────────────────────────────────────────────────────────

@router.get("/search")
async def search_spirits(q: str = Query(""), limit: int = Query(20), db: AsyncSession = Depends(get_db)):
    if not q or len(q) < 1:
        return {"results": []}
    result = await db.execute(
        select(Spirit).where(
            or_(Spirit.producer.ilike(f"%{q}%"), Spirit.name.ilike(f"%{q}%"))
        ).limit(limit)
    )
    spirits = result.scalars().all()
    return {"results": [{
        "id": s.id, "producer": s.producer, "name": s.name,
        "age_statement": s.age_statement, "region": s.region,
        "spirit_type": s.spirit_type, "display": s.display_name,
    } for s in spirits]}


# ── Feed (MUST be before {spirit_id} catch-all) ──

@router.get("/feed")
async def spirit_feed(limit: int = 30, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SpiritTastingNote)
        .options(selectinload(SpiritTastingNote.spirit), selectinload(SpiritTastingNote.user))
        .where(SpiritTastingNote.is_public == True)
        .order_by(SpiritTastingNote.created_at.desc())
        .limit(limit)
    )
    notes = result.scalars().all()
    return {"items": [{
        "id": n.id, "spirit_id": n.spirit.id,
        "display": n.spirit.display_name,
        "spirit_type": n.spirit.spirit_type,
        "rating": n.rating,
        "username": n.user.display_name or n.user.username,
        "user_id": n.user.id,
        "notes": n.notes[:280] if n.notes else "",
        "created_at": n.created_at.isoformat(),
    } for n in notes]}


# ── Create ────────────────────────────────────────────────────────

@router.post("")
async def create_spirit_tasting(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    form = await request.form()
    producer = (form.get("producer") or "").strip()
    name = (form.get("name") or "").strip()
    if not name and not producer:
        raise HTTPException(status_code=400, detail="Tell us which spirit")
    if not name:
        name, producer = producer, ""
    rating = (form.get("rating") or "").strip()
    try:
        rating = int(rating)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Add a rating (1–5)")
    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be 1–5")
    spirit_data = {
        "producer": producer, "name": name,
        "age_statement": form.get("age_statement", ""),
        "region": form.get("region", ""), "country": form.get("country", ""),
        "spirit_type": form.get("spirit_type", "whiskey"),
        "cask_type": form.get("cask_type", ""),
        "description": form.get("description", ""),
    }
    try:
        abv = float(form.get("abv") or 0)
        spirit_data["abv"] = abv if abv > 0 else None
    except (ValueError, TypeError):
        pass
    result = await db.execute(
        select(Spirit).where(Spirit.producer == producer, Spirit.name == name).limit(1)
    )
    spirit = result.scalar_one_or_none()
    if not spirit:
        spirit = Spirit(**spirit_data)
        db.add(spirit)
        await db.flush()
    distillery_id = None
    if form.get("distillery_name") and form.get("lat") and form.get("lon"):
        d = Distillery(
            name=form["distillery_name"],
            address=form.get("address", ""),
            lat=float(form["lat"]), lon=float(form["lon"]),
            state_or_region=form.get("state_or_region", ""),
            country=form.get("country", ""),
        )
        db.add(d)
        await db.flush()
        distillery_id = d.id
    note = SpiritTastingNote(
        spirit_id=spirit.id, user_id=user.id,
        distillery_id=distillery_id, rating=rating,
        nose=form.get("nose", ""), palate=form.get("palate", ""),
        finish=form.get("finish", ""),
        body=form.get("body", ""), sweetness=form.get("sweetness", ""),
        peat=form.get("peat", ""),
        notes=form.get("notes", ""), photo_url=form.get("photo_url", ""),
        price_paid=form.get("price_paid", type=float),
        is_public=form.get("is_public", "1") == "1",
    )
    db.add(note)
    await db.commit()
    return {"ok": True, "spirit_id": spirit.id, "note_id": note.id}


# ── Spirit Detail ─────────────────────────────────────────────────

@router.get("/{spirit_id}")
async def get_spirit_detail(spirit_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Spirit).where(Spirit.id == spirit_id)
        .options(
            selectinload(Spirit.tasting_notes).selectinload(SpiritTastingNote.user),
            selectinload(Spirit.tasting_notes).selectinload(SpiritTastingNote.distillery),
        )
    )
    spirit = result.scalar_one_or_none()
    if not spirit:
        return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)
    user = await get_current_user(request, db)
    avg_rating = spirit.avg_rating
    return templates.TemplateResponse("spirit/detail.html", {
        "request": request, "user": user, "spirit": spirit,
        "avg_rating": avg_rating,
    })


# ── Spirit Groups Feed ──────────────────────────────────────────


@router.get("/feed/groups")
async def spirit_group_feed(
    group_id: str = Query(...),
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
):
    """Spirit tasting notes from members of a group."""
    # Get group members
    result = await db.execute(
        select(GroupMember.user_id).where(GroupMember.group_id == group_id)
    )
    member_ids = [row[0] for row in result.all()]
    if not member_ids:
        return {"items": []}

    result = await db.execute(
        select(SpiritTastingNote)
        .options(selectinload(SpiritTastingNote.spirit), selectinload(SpiritTastingNote.user))
        .where(SpiritTastingNote.is_public == True)
        .where(SpiritTastingNote.user_id.in_(member_ids))
        .order_by(SpiritTastingNote.created_at.desc())
        .limit(limit)
    )
    notes = result.scalars().all()
    return {"items": [{
        "id": n.id, "spirit_id": n.spirit.id,
        "display": n.spirit.display_name,
        "spirit_type": n.spirit.spirit_type,
        "rating": n.rating,
        "username": n.user.display_name or n.user.username,
        "user_id": n.user.id,
        "notes": n.notes[:280] if n.notes else "",
        "created_at": n.created_at.isoformat(),
    } for n in notes]}


# ── Distillery routes ─────────────────────────────────────────────

@router.get("/distilleries/search")
async def search_distilleries(q: str = Query(""), limit: int = Query(20), db: AsyncSession = Depends(get_db)):
    if not q or len(q) < 1:
        return {"results": []}
    result = await db.execute(
        select(Distillery).where(
            or_(Distillery.name.ilike(f"%{q}%"), Distillery.state_or_region.ilike(f"%{q}%"))
        ).limit(limit)
    )
    distilleries = result.scalars().all()
    return {"results": [{
        "id": d.id, "name": d.name, "address": d.address,
        "state_or_region": d.state_or_region, "country": d.country,
        "lat": d.lat, "lon": d.lon, "website": d.website,
        "spirit_types": d.spirit_types,
    } for d in distilleries]}


@router.get("/distilleries/nearby")
async def distilleries_nearby(
    lat: float = Query(...), lon: float = Query(...),
    radius: float = Query(100), db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import text
    stmt = select(Distillery).where(
        Distillery.lat >= lat - radius / 111.0,
        Distillery.lat <= lat + radius / 111.0,
        Distillery.lon >= lon - radius / (111.0 * func.cos(func.radians(lat))),
        Distillery.lon <= lon + radius / (111.0 * func.cos(func.radians(lat))),
    ).limit(100)
    result = await db.execute(stmt)
    distilleries = result.scalars().all()
    features = []
    for d in distilleries:
        tn_count = await db.execute(
            select(func.count()).select_from(SpiritTastingNote).where(SpiritTastingNote.distillery_id == d.id)
        )
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [d.lon, d.lat]},
            "properties": {
                "id": d.id, "name": d.name, "address": d.address[:80] if d.address else "",
                "website": d.website, "tasting_count": tn_count.scalar() or 0,
                "spirit_types": d.spirit_types,
            },
        })
    return {"type": "FeatureCollection", "features": features}


# ── Wishlist ──────────────────────────────────────────────────────

@router.get("/wishlist")
async def get_spirit_wishlist(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return {"items": []}
    result = await db.execute(
        select(SpiritWishlistEntry).where(SpiritWishlistEntry.user_id == user.id)
        .order_by(SpiritWishlistEntry.added_at.desc())
    )
    return {"items": [{"id": e.id, "spirit_id": e.spirit.id, "producer": e.spirit.producer,
        "name": e.spirit.name, "display": e.spirit.display_name,
        "region": e.spirit.region, "spirit_type": e.spirit.spirit_type,
        "added_at": e.added_at.isoformat()} for e in result.scalars().all()]}


@router.post("/wishlist/{spirit_id}")
async def toggle_spirit_wishlist(spirit_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    result = await db.execute(select(Spirit).where(Spirit.id == spirit_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Spirit not found")
    result = await db.execute(
        select(SpiritWishlistEntry).where(
            SpiritWishlistEntry.user_id == user.id, SpiritWishlistEntry.spirit_id == spirit_id
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.commit()
        return {"saved": False}
    db.add(SpiritWishlistEntry(user_id=user.id, spirit_id=spirit_id))
    await db.commit()
    return {"saved": True}


@router.get("/wishlist/{spirit_id}/status")
async def spirit_wishlist_status(spirit_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return {"saved": False}
    result = await db.execute(
        select(SpiritWishlistEntry).where(
            SpiritWishlistEntry.user_id == user.id, SpiritWishlistEntry.spirit_id == spirit_id
        )
    )
    return {"saved": result.scalar_one_or_none() is not None}