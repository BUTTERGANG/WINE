"""Winery routes — discover, search, import wineries."""

from fastapi import APIRouter, Depends, Request, Query, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func, or_
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
    list_winery_regions,
    import_wineries_to_db,
)
from backend.config import settings
from backend.services.template import templates
from backend.services.geo_lookup import resolve_state, resolve_zip

router = APIRouter(prefix="/api/wineries", tags=["wineries"])


@router.get("/regions")
async def winery_regions(db: AsyncSession = Depends(get_db)):
    """Wine regions with winery counts, for the search filter dropdown."""
    return {"regions": await list_winery_regions(db)}


@router.get("/search")
async def search_wineries(
    request: Request,
    q: str = Query(""),
    lat: float = Query(None),
    lon: float = Query(None),
    radius: int = Query(100),
    region: str = Query(""),
    state: str = Query(""),
    has_tastings: bool = Query(False),
    sort: str = Query("name"),
    db: AsyncSession = Depends(get_db),
):
    """Search wineries — local DB first, then Google Places or OSM."""

    # Ensure radius is within bounds
    radius = min(max(radius, 10), 500)

    has_filters = bool(region or state or has_tastings)
    limit = 60 if has_filters else 20

    # Local first
    local = await search_local_wineries(
        db, q, limit, region=region, state=state, has_tastings=has_tastings, sort=sort
    )

    # Tasting counts in one grouped query (avoids N+1).
    ids = [loc.id for loc in local]
    counts: dict[str, int] = {}
    if ids:
        rows = await db.execute(
            select(TastingNote.location_id, func.count())
            .where(TastingNote.location_id.in_(ids))
            .group_by(TastingNote.location_id)
        )
        counts = {loc_id: n for loc_id, n in rows.all()}

    results = [
        {
            "id": loc.id,
            "name": loc.name,
            "address": loc.address,
            "region": loc.state_or_region,
            "lat": loc.lat,
            "lon": loc.lon,
            "description": loc.description,
            "website": loc.website,
            "phone": loc.phone,
            "tasting_count": counts.get(loc.id, 0),
            "google_rating": None,
            "local": True,
        }
        for loc in local
    ]

    # External fallback only for plain text queries (external APIs can't
    # honour our region / tastings filters).
    if not has_filters and q and len(results) < 10:
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


@router.get("/locate")
async def locate_wineries(
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    """Resolve a search term (US state, ZIP code, wine region, or winery name)
    to a map target so the client can fly there. Returns
    {found, lat, lon, zoom, label, count}."""
    q = q.strip()

    # 1. US ZIP code — GeoNames centroid (falls back to a coarse region).
    zip_hit = resolve_zip(q)
    if zip_hit:
        zip5, lat, lon, exact = zip_hit
        return {
            "found": True, "lat": lat, "lon": lon,
            "zoom": 12 if exact else 8,
            "label": f"ZIP {zip5}" if exact else f"ZIP {zip5} (approx.)",
            "count": 0,
        }

    # 2. US state by name or 2-letter abbreviation.
    state = resolve_state(q)
    if state:
        abbr, lat, lon = state
        cnt = await db.execute(
            select(func.count()).select_from(Location).where(
                Location.venue_type == "winery",
                or_(Location.address.ilike(f"%, {abbr} %"), Location.address.ilike(f"%, {abbr}%")),
            )
        )
        return {"found": True, "lat": lat, "lon": lon, "zoom": 6,
                "label": abbr, "count": cnt.scalar() or 0}

    # 3. Wine region / winery name — center on the matching wineries.
    matches = await search_local_wineries(db, q, 100)
    matches = [m for m in matches if m.lat is not None and m.lon is not None]
    if matches:
        lat = sum(m.lat for m in matches) / len(matches)
        lon = sum(m.lon for m in matches) / len(matches)
        spread = max(
            (max(m.lat for m in matches) - min(m.lat for m in matches)),
            (max(m.lon for m in matches) - min(m.lon for m in matches)),
        )
        zoom = 12 if spread < 0.15 else 10 if spread < 1 else 8 if spread < 5 else 6
        return {"found": True, "lat": lat, "lon": lon, "zoom": zoom,
                "label": q, "count": len(matches)}

    return {"found": False, "label": q}


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