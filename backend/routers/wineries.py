"""Winery routes — discover, search, import wineries."""

from fastapi import APIRouter, Depends, Request, Query, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models.location import Location
from backend.models.wine import Wine, TastingNote
from backend.models.user import User
from backend.services.auth import get_current_user
from backend.services.wineries import (
    search_wineries_google,
    search_wineries_osm,
    search_vineyards_nominatim,
    search_local_wineries,
    import_wineries_to_db,
)
from backend.config import settings
from backend.services.template import templates

router = APIRouter(prefix="/api/wineries", tags=["wineries"])


@router.get("/search")
async def search_wineries(
    request: Request,
    q: str = Query(""),
    lat: float = Query(None),
    lon: float = Query(None),
    radius: int = Query(100),
    db: AsyncSession = Depends(get_db),
):
    """Search wineries — local DB first, then Google Places or OSM."""

    # Ensure radius is within bounds
    radius = min(max(radius, 10), 500)

    # Local first
    local = await search_local_wineries(db, q, 20)
    results = [
        {
            "id": loc.id,
            "name": loc.name,
            "address": loc.address,
            "lat": loc.lat,
            "lon": loc.lon,
            "description": loc.description,
            "website": loc.website,
            "phone": loc.phone,
            "google_rating": None,
            "local": True,
        }
        for loc in local
    ]

    # If under limit, try Google Places API (with key) then OSM
    if len(results) < 10:
        has_key = bool(settings.google_maps_api_key)

        if has_key:
            google = await search_wineries_google(query=q, lat=lat, lon=lon, radius=radius, limit=10)
            for w in google:
                results.append({
                    "id": None,
                    "name": w["name"],
                    "address": w["address"],
                    "lat": w["lat"],
                    "lon": w["lon"],
                    "description": w.get("description", ""),
                    "website": w.get("website", ""),
                    "phone": w.get("phone", ""),
                    "google_rating": w.get("rating"),
                    "local": False,
                })

        if len(results) < 10:
            osm = await search_wineries_osm(query=q, lat=lat, lon=lon, radius=radius, limit=15)
            for w in osm:
                results.append({
                    "id": None,
                    "name": w["name"],
                    "address": w["address"],
                    "lat": w["lat"],
                    "lon": w["lon"],
                    "description": w.get("description", ""),
                    "website": w.get("website", ""),
                    "phone": w.get("phone", ""),
                    "google_rating": None,
                    "local": False,
                })

    return {"results": results}


@router.post("/import")
async def import_wineries(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Import wineries from OSM near a location or from a search."""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    form = await request.form()
    query = str(form.get("query", ""))
    lat_str = form.get("lat")
    lon_str = form.get("lon")
    lat = float(lat_str) if lat_str else None
    lon = float(lon_str) if lon_str else None
    radius = int(form.get("radius", 100))

    # Search: Google Places (if key) → OSM → Nominatim fallback
    wineries = []
    has_key = bool(settings.google_maps_api_key)

    if has_key:
        if lat and lon:
            wineries = await search_wineries_google(query=query, lat=lat, lon=lon, radius=radius, limit=20)
        elif query:
            wineries = await search_wineries_google(query=query, limit=20)

    if not wineries:
        if lat and lon:
            wineries = await search_wineries_osm(query=query, lat=lat, lon=lon, radius=radius, limit=50)
        elif query:
            wineries = await search_wineries_osm(query=query, limit=50)
            if not wineries:
                wineries = await search_vineyards_nominatim(query, 20)

    if not wineries:
        return {"imported": 0, "skipped": 0, "found": 0}

    created, skipped = await import_wineries_to_db(wineries, db)
    return {"imported": created, "skipped": skipped, "found": len(wineries)}


@router.get("/nearby")
async def get_wineries_nearby(
    request: Request,
    lat: float = Query(...),
    lon: float = Query(...),
    radius: float = Query(100),
    db: AsyncSession = Depends(get_db),
):
    """Return nearby wineries as GeoJSON for the map."""
    deg_per_km = 1 / 111.0
    lat_range = radius * deg_per_km
    lon_range = radius * deg_per_km / max(0.1, abs(lat * 3.14159 / 180))

    lat_min = lat - lat_range
    lat_max = lat + lat_range
    lon_min = lon - lon_range
    lon_max = lon + lon_range

    stmt = (
        select(Location)
        .where(Location.venue_type == "winery")
        .where(Location.lat.between(lat_min, lat_max))
        .where(Location.lon.between(lon_min, lon_max))
        .limit(500)
    )

    result = await db.execute(stmt)
    wineries = result.scalars().all()

    # Tasting counts for all wineries in one grouped query (avoids N+1).
    winery_ids = [w.id for w in wineries]
    counts = {}
    if winery_ids:
        rows = await db.execute(
            select(TastingNote.location_id, func.count())
            .where(TastingNote.location_id.in_(winery_ids))
            .group_by(TastingNote.location_id)
        )
        counts = {loc_id: n for loc_id, n in rows.all()}

    features = []
    for w in wineries:
        tasting_count = counts.get(w.id, 0)

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [w.lon, w.lat],
            },
            "properties": {
                "id": w.id,
                "name": w.name,
                "address": w.address[:80] if w.address else "",
                "venue_type": "winery",
                "website": w.website,
                "tasting_count": tasting_count,
                "description": w.description[:150] if w.description else "",
            },
        })

    return {"type": "FeatureCollection", "features": features}


@router.get("/{winery_id}")
async def get_winery(winery_id: str):
    """The venue/winery detail page lives at /venue/{id}."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/venue/{winery_id}", status_code=307)