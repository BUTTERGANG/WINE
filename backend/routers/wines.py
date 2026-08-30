"""Wine routes — CRUD, search, scan."""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Form, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
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

    # Get or create the wine
    wine_data = {
        "producer": form.get("producer", ""),
        "name": form.get("name", ""),
        "vintage": int(form["vintage"]) if form.get("vintage") else None,
        "region": form.get("region", ""),
        "country": form.get("country", ""),
        "varietal": form.get("varietal", ""),
        "wine_type": form.get("wine_type", "red"),
        "abv": float(form["abv"]) if form.get("abv") else None,
        "description": form.get("description", ""),
    }

    wine = await get_or_create_wine(db, wine_data)

    # Location
    location_id = None
    if form.get("location_name") and form.get("lat") and form.get("lon"):
        location = Location(
            name=form["location_name"],
            address=form.get("address", ""),
            lat=float(form["lat"]),
            lon=float(form["lon"]),
            venue_type=form.get("venue_type", "other"),
        )
        db.add(location)
        await db.flush()
        location_id = location.id

    # Tasting note
    note = TastingNote(
        wine_id=wine.id,
        user_id=user.id,
        location_id=location_id,
        rating=int(form.get("rating", 3)),
        appearance=form.get("appearance", ""),
        nose=form.get("nose", ""),
        palate=form.get("palate", ""),
        finish=form.get("finish", ""),
        body=form.get("body", ""),
        sweetness=form.get("sweetness", ""),
        acidity=form.get("acidity", ""),
        tannins=form.get("tannins", ""),
        food_pairing=form.get("food_pairing", ""),
        price_paid=float(form["price_paid"]) if form.get("price_paid") else None,
        notes=form.get("notes", ""),
        photo_url=form.get("photo_url", ""),
        is_public=form.get("is_public", "1") == "1",
    )
    db.add(note)
    await db.commit()

    return {"ok": True, "wine_id": wine.id, "note_id": note.id}


@router.get("/{wine_id}")
async def get_wine(wine_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Wine detail page."""
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Wine)
        .options(selectinload(Wine.tasting_notes))
        .where(Wine.id == wine_id)
    )
    wine = result.scalar_one_or_none()
    if not wine:
        raise HTTPException(status_code=404, detail="Wine not found")

    user = await get_current_user(request, db)

    # Compute avg rating in async context
    ratings = [tn.rating for tn in wine.tasting_notes if tn.rating]
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None

    return templates.TemplateResponse(
        "wine/detail.html",
        {
            "request": request,
            "wine": wine,
            "user": user,
            "avg_rating": avg_rating,
        },
    )


@router.get("/{wine_id}/reviews")
async def get_wine_reviews(wine_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Wine reviews in JSON for HTMX loading."""
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
            "notes": n.notes[:200] if n.notes else "",
            "created_at": n.created_at.isoformat(),
        }
        for n in notes
    ]}