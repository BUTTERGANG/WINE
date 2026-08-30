"""Wine routes — CRUD, search, scan."""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Form, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.models.wine import Wine, TastingNote
from backend.models.location import Location
from backend.models.user import User
from backend.services.auth import get_current_user
from backend.services.wine_db import search_local_wines, search_external_wine_api, get_or_create_wine
from backend.services.label_scanner import scan_label
from backend.services.glass_scanner import analyze_glass
from backend.services.template import templates


UPLOAD_DIR = Path(settings.upload_dir)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def save_upload(file: UploadFile) -> str | None:
    """Save an uploaded image and return the URL path."""
    if not file.content_type or not file.content_type.startswith("image/"):
        return None
    ext = file.filename.split(".")[-1] if file.filename else "jpg"
    filename = f"{uuid.uuid4().hex[:12]}.{ext}"
    filepath = UPLOAD_DIR / filename
    content = await file.read()
    filepath.write_bytes(content)
    return f"/static/uploads/{filename}"

router = APIRouter(prefix="/api/wines", tags=["wines"])


@router.get("/search")
async def search_wines(
    q: str = Query(""),
    limit: int = Query(20),
    db: AsyncSession = Depends(get_db),
):
    """Live autocomplete search — local first, then external."""
    if not q or len(q) < 1:
        return {"results": []}

    local = await search_local_wines(db, q, limit)

    results = []
    for wine in local:
        results.append({
            "id": wine.id,
            "producer": wine.producer,
            "name": wine.name,
            "vintage": wine.vintage,
            "region": wine.region,
            "varietal": wine.varietal,
            "wine_type": wine.wine_type,
            "display": wine.display_name,
        })

    # If under limit, try external API
    if len(results) < limit:
        try:
            external = await search_external_wine_api(q)
            for ext in external:
                display = f"{ext['producer']} {ext['name']}"
                if ext.get("vintage"):
                    display += f" ({ext['vintage']})"
                results.append({
                    "id": None,
                    "producer": ext["producer"],
                    "name": ext["name"],
                    "vintage": ext.get("vintage"),
                    "region": ext.get("region", ""),
                    "varietal": ext.get("varietal", ""),
                    "wine_type": ext.get("wine_type", "red"),
                    "display": display,
                    "external": True,
                })
        except Exception:
            pass

    return {"results": results[:limit]}


@router.get("/mine/recent")
async def my_recent_wines(
    request: Request,
    limit: int = Query(6),
    db: AsyncSession = Depends(get_db),
):
    """The current user's most recently logged wines — for one-tap re-logging."""
    user = await get_current_user(request, db)
    if not user:
        return {"wines": []}

    last_seen = (
        select(TastingNote.wine_id, func.max(TastingNote.created_at).label("last"))
        .where(TastingNote.user_id == user.id)
        .group_by(TastingNote.wine_id)
        .subquery()
    )
    stmt = (
        select(Wine)
        .join(last_seen, Wine.id == last_seen.c.wine_id)
        .order_by(last_seen.c.last.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    wines = result.scalars().all()
    return {"wines": [
        {
            "id": w.id,
            "producer": w.producer,
            "name": w.name,
            "vintage": w.vintage,
            "region": w.region,
            "varietal": w.varietal,
            "wine_type": w.wine_type,
            "display": w.display_name,
        }
        for w in wines
    ]}


@router.post("/scan")
async def scan_wine_label(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a bottle label photo and get candidate matches."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    image_data = await file.read()

    # Try OCR scan
    candidates = await scan_label(image_data, db)

    return JSONResponse({"candidates": candidates})


@router.post("/scan-glass")
async def scan_glass_photo(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a glass photo and get wine style/varietal suggestions."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    image_data = await file.read()
    suggestions = await analyze_glass(image_data)

    return JSONResponse({"suggestions": suggestions})


@router.post("")
async def create_wine(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create a wine + tasting note from form data."""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    form = await request.form()

    def _num(key, cast, lo=None, hi=None):
        raw = (form.get(key) or "").strip()
        if not raw:
            return None
        try:
            val = cast(raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"Invalid value for {key!r}")
        if lo is not None and val < lo:
            raise HTTPException(status_code=400, detail=f"{key!r} out of range")
        if hi is not None and val > hi:
            raise HTTPException(status_code=400, detail=f"{key!r} out of range")
        return val

    producer = (form.get("producer") or "").strip()
    name = (form.get("name") or "").strip()
    if not name and not producer:
        raise HTTPException(status_code=400, detail="Tell us which wine you're drinking")
    if not name:  # a single free-text entry lands in `name`
        name, producer = producer, ""

    rating = _num("rating", int, 1, 5)
    if rating is None:
        raise HTTPException(status_code=400, detail="Add a rating (1–5)")

    # Get or create the wine
    wine_data = {
        "producer": producer,
        "name": name,
        "vintage": _num("vintage", int, 1800, 2100),
        "region": form.get("region", ""),
        "country": form.get("country", ""),
        "varietal": form.get("varietal", ""),
        "wine_type": form.get("wine_type", "red"),
        "abv": _num("abv", float, 0, 100),
        "description": form.get("description", ""),
    }

    wine = await get_or_create_wine(db, wine_data)

    # Location
    location_id = None
    if form.get("location_name") and form.get("lat") and form.get("lon"):
        location = Location(
            name=form["location_name"],
            address=form.get("address", ""),
            lat=_num("lat", float, -90, 90),
            lon=_num("lon", float, -180, 180),
            venue_type=form.get("venue_type") or "other",
        )
        db.add(location)
        await db.flush()
        location_id = location.id

    # Tasting note
    note = TastingNote(
        wine_id=wine.id,
        user_id=user.id,
        location_id=location_id,
        rating=rating,
        appearance=form.get("appearance", ""),
        nose=form.get("nose", ""),
        palate=form.get("palate", ""),
        finish=form.get("finish", ""),
        body=form.get("body", ""),
        sweetness=form.get("sweetness", ""),
        acidity=form.get("acidity", ""),
        tannins=form.get("tannins", ""),
        food_pairing=form.get("food_pairing", ""),
        price_paid=_num("price_paid", float, 0),
        notes=form.get("notes", ""),
        photo_url=form.get("photo_url", ""),
        # Checkbox: only public when explicitly checked.
        is_public=form.get("is_public") == "1",
    )
    db.add(note)
    await db.commit()

    return {"ok": True, "wine_id": wine.id, "note_id": note.id}


@router.get("/export")
async def export_journal(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Export the current user's tasting journal as CSV."""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(TastingNote)
        .options(selectinload(TastingNote.wine), selectinload(TastingNote.location))
        .where(TastingNote.user_id == user.id)
        .order_by(TastingNote.created_at.desc())
    )
    notes = result.scalars().all()

    import csv
    import io

    def _safe(v):
        """Neutralize spreadsheet formula injection (=, +, -, @, tab, CR)."""
        s = "" if v is None else str(v)
        if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
            return "'" + s
        return s

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Date", "Wine", "Producer", "Vintage", "Region", "Varietal", "Type",
        "Rating", "Appearance", "Nose", "Palate", "Finish", "Body",
        "Sweetness", "Acidity", "Tannins", "Notes", "Food Pairing",
        "Price Paid", "Venue", "Venue Type", "Latitude", "Longitude",
    ])
    for n in notes:
        wine = n.wine
        loc = n.location
        writer.writerow([_safe(x) for x in [
            n.created_at.strftime("%Y-%m-%d") if n.created_at else "",
            wine.name if wine else "",
            wine.producer if wine else "",
            wine.vintage if wine else "",
            wine.region if wine else "",
            wine.varietal if wine else "",
            wine.wine_type if wine else "",
            n.rating,
            n.appearance,
            n.nose,
            n.palate,
            n.finish,
            n.body,
            n.sweetness,
            n.acidity,
            n.tannins,
            n.notes,
            n.food_pairing,
            n.price_paid or "",
            loc.name if loc else "",
            loc.venue_type if loc else "",
            loc.lat if loc else "",
            loc.lon if loc else "",
        ]])

    from starlette.responses import Response
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="wine-journal-{user.username}.csv"',
        },
    )


@router.get("/{wine_id}/reviews")
async def get_wine_reviews(wine_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Public tasting notes for a wine, as JSON."""
    result = await db.execute(
        select(TastingNote)
        .where(TastingNote.wine_id == wine_id, TastingNote.is_public == True)
        .order_by(TastingNote.created_at.desc())
        .limit(20)
    )
    notes = result.scalars().all()
    return {"results": [
        {
            "id": n.id,
            "rating": n.rating,
            "username": n.user.display_name or n.user.username,
            "user_id": n.user.id,
            "notes": n.notes or "",
            "appearance": n.appearance or "",
            "nose": n.nose or "",
            "palate": n.palate or "",
            "finish": n.finish or "",
            "body": n.body or "",
            "sweetness": n.sweetness or "",
            "acidity": n.acidity or "",
            "tannins": n.tannins or "",
            "food_pairing": n.food_pairing or "",
            "photo_url": n.photo_url or "",
            "location_id": n.location.id if n.location else None,
            "location_name": n.location.name if n.location else None,
            "created_at": n.created_at.isoformat(),
        }
        for n in notes
    ]}


@router.get("/{wine_id}")
async def get_wine_redirect(wine_id: str):
    """Back-compat: the wine detail page moved to /wine/{id}."""
    return RedirectResponse(url=f"/wine/{wine_id}", status_code=301)