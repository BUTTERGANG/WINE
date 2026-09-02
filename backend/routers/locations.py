"""Location routes — map pins, nearby query, heatmap, search, regions."""

from fastapi import APIRouter, Depends, Request, Query, Form, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select, func, text, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models.location import Location
from backend.models.wine import Wine, TastingNote
from backend.models.user import User
from backend.models.spirit import Distillery
from backend.services.auth import get_current_user
from backend.services.geocoder import geocode_address, reverse_geocode
from backend.services.template import templates

router = APIRouter(prefix="/api/locations", tags=["locations"])


@router.get("/nearby")
async def get_nearby_locations(
    request: Request,
    lat: float = Query(...),
    lon: float = Query(...),
    radius: float = Query(50, description="Radius in km"),
    user_id: str = Query("", description="Filter to one user"),
    db: AsyncSession = Depends(get_db),
):
    """
    Return tasting-note pins within radius as GeoJSON.
    Uses a bounding-box approximation (no PostGIS in SQLite).
    """
    deg_per_km = 1 / 111.0
    lat_range = radius * deg_per_km
    lon_range = radius * deg_per_km / max(0.1, abs(lat * 3.14159 / 180))

    lat_min = lat - lat_range
    lat_max = lat + lat_range
    lon_min = lon - lon_range
    lon_max = lon + lon_range

    stmt = (
        select(TastingNote, Wine, Location, User)
        .join(Wine, TastingNote.wine_id == Wine.id)
        .join(Location, TastingNote.location_id == Location.id)
        .join(User, TastingNote.user_id == User.id)
        .where(TastingNote.is_public == True)
        .where(Location.lat.between(lat_min, lat_max))
        .where(Location.lon.between(lon_min, lon_max))
        .limit(500)
    )

    if user_id:
        stmt = stmt.where(TastingNote.user_id == user_id)

    result = await db.execute(stmt)
    rows = result.all()

    features = []
    for note, wine, loc, user in rows:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [loc.lon, loc.lat],
            },
            "properties": {
                "id": note.id,
                "wine_id": wine.id,
                "wine_name": wine.display_name,
                "producer": wine.producer,
                "vintage": wine.vintage,
                "varietal": wine.varietal,
                "wine_type": wine.wine_type,
                "rating": note.rating,
                "username": user.display_name or user.username,
                "user_id": user.id,
                "location_name": loc.name,
                "location_id": loc.id,
                "notes": note.notes[:140] if note.notes else "",
                "photo_url": note.photo_url or "",
                "created_at": note.created_at.isoformat(),
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


@router.get("/heatmap")
async def get_heatmap_data(
    request: Request,
    db: AsyncSession = Depends(get_db),
    wine_type: str = Query("", description="Filter by wine type"),
):
    """
    Return weighted points for Leaflet.heat — intensity based on rating.
    Returns array of [lat, lon, intensity] triplets.
    """
    stmt = (
        select(Location.lat, Location.lon, TastingNote.rating, TastingNote.created_at)
        .join(TastingNote, TastingNote.location_id == Location.id)
        .where(TastingNote.is_public == True)
    )

    if wine_type:
        stmt = stmt.join(Wine, TastingNote.wine_id == Wine.id).where(Wine.wine_type == wine_type)

    stmt = stmt.limit(500)
    result = await db.execute(stmt)
    rows = result.all()

    # Normalize ratings to 0.2–1.0 intensity, recency bonus
    from datetime import datetime
    now = datetime.utcnow()

    points = []
    for lat, lon, rating, created_at in rows:
        intensity = 0.2 + (rating / 5.0) * 0.6  # 0.2–0.8 from rating
        # Recency bonus: tastings within 30 days get +0.2
        if created_at:
            # Make naive if needed
            if created_at.tzinfo:
                created_at = created_at.replace(tzinfo=None)
            age_days = (now - created_at).days
            if age_days < 30:
                intensity += 0.2
        intensity = min(intensity, 1.0)

        points.append([lat, lon, intensity])

    return {"points": points}


@router.post("/geocode")
async def geocode(
    request: Request,
    address: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Resolve an address to lat/lon via Nominatim."""
    result = await geocode_address(address)
    if result:
        return {"lat": result[0], "lon": result[1], "display_name": result[2]}
    raise HTTPException(status_code=404, detail="Address not found")


@router.post("/reverse")
async def reverse(
    request: Request,
    lat: float = Form(...),
    lon: float = Form(...),
):
    """Resolve the viewer's coordinates to a nearby venue (one-tap 'log here')."""
    result = await reverse_geocode(lat, lon)
    if result:
        return result
    # Still useful — let the client save a bare pin.
    return {"name": "Dropped pin", "address": "", "lat": lat, "lon": lon, "venue_type": "other"}


# ── Unified Search ─────────────────────────────────────────────

@router.get("/search")
async def unified_search(
    q: str = Query(""),
    limit: int = Query(10),
    db: AsyncSession = Depends(get_db),
):
    """Unified search across wines, venues, users, and wineries."""
    if not q or len(q) < 2:
        return {"results": []}

    q_lower = q.lower()
    results = []

    # Wines
    wine_result = await db.execute(
        select(Wine).where(
            or_(Wine.name.ilike(f"%{q}%"), Wine.producer.ilike(f"%{q}%"))
        ).limit(limit)
    )
    for wine in wine_result.scalars().all():
        results.append({
            "id": wine.id,
            "type": "wine",
            "name": wine.display_name,
            "subtitle": wine.region,
        })

    # Venues
    venue_result = await db.execute(
        select(Location).where(
            Location.name.ilike(f"%{q}%")
        ).limit(limit)
    )
    for venue in venue_result.scalars().all():
        results.append({
            "id": venue.id,
            "type": "venue",
            "name": venue.name,
            "subtitle": venue.address[:60] if venue.address else "",
        })

    # Users
    user_result = await db.execute(
        select(User).where(
            or_(User.username.ilike(f"%{q}%"), User.display_name.ilike(f"%{q}%"))
        ).limit(limit)
    )
    for user in user_result.scalars().all():
        results.append({
            "id": user.id,
            "type": "user",
            "name": user.display_name or user.username,
            "subtitle": "@" + user.username,
        })

    # Wineries
    winery_result = await db.execute(
        select(Location).where(
            Location.venue_type == "winery",
            Location.name.ilike(f"%{q}%")
        ).limit(limit)
    )
    for winery in winery_result.scalars().all():
        results.append({
            "id": winery.id,
            "type": "winery",
            "name": winery.name,
            "subtitle": winery.address[:60] if winery.address else "",
        })

    # Distilleries
    dist_result = await db.execute(
        select(Distillery).where(
            Distillery.name.ilike(f"%{q}%")
        ).limit(limit)
    )
    for dist in dist_result.scalars().all():
        results.append({
            "id": dist.id,
            "type": "distillery",
            "name": dist.name,
            "subtitle": dist.address[:60] if dist.address else "",
        })

    return {"results": results[:limit]}


# ── Region Boundaries ──────────────────────────────────────────

@router.get("/regions/boundaries")
async def region_boundaries(
    db: AsyncSession = Depends(get_db),
):
    """Return GeoJSON polygon boundaries for wine regions."""
    # Return simplified boundaries for known wine regions
    # These are approximate bounding polygons
    regions = [
        {
            "type": "Feature",
            "properties": {"name": "Napa Valley"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-122.55, 38.35], [-122.30, 38.35], [-122.30, 38.65],
                    [-122.55, 38.65], [-122.55, 38.35]
                ]]
            }
        },
        {
            "type": "Feature",
            "properties": {"name": "Sonoma County"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-123.20, 38.25], [-122.60, 38.25], [-122.60, 38.85],
                    [-123.20, 38.85], [-123.20, 38.25]
                ]]
            }
        },
        {
            "type": "Feature",
            "properties": {"name": "Bordeaux"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-0.80, 44.70], [-0.20, 44.70], [-0.20, 45.10],
                    [-0.80, 45.10], [-0.80, 44.70]
                ]]
            }
        },
        {
            "type": "Feature",
            "properties": {"name": "Burgundy"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [4.30, 46.80], [5.10, 46.80], [5.10, 47.30],
                    [4.30, 47.30], [4.30, 46.80]
                ]]
            }
        },
        {
            "type": "Feature",
            "properties": {"name": "Tuscany"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [10.90, 42.80], [11.80, 42.80], [11.80, 43.60],
                    [10.90, 43.60], [10.90, 42.80]
                ]]
            }
        },
        {
            "type": "Feature",
            "properties": {"name": "Rioja"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-2.90, 42.30], [-2.20, 42.30], [-2.20, 42.70],
                    [-2.90, 42.70], [-2.90, 42.30]
                ]]
            }
        },
        {
            "type": "Feature",
            "properties": {"name": "Barossa Valley"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [138.70, -34.40], [139.10, -34.40], [139.10, -34.70],
                    [138.70, -34.70], [138.70, -34.40]
                ]]
            }
        },
        {
            "type": "Feature",
            "properties": {"name": "Marlborough"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [173.60, -41.30], [174.10, -41.30], [174.10, -41.70],
                    [173.60, -41.70], [173.60, -41.30]
                ]]
            }
        },
    ]
    return {"type": "FeatureCollection", "features": regions}