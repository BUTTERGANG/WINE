"""Winery service — discover and search wineries via Google Places + OSM."""

import asyncio
from typing import Optional

import httpx

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.location import Location


GOOGLE_PLACES_BASE = "https://places.googleapis.com/v1"


async def search_wineries_google(
    query: str = "",
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    radius: int = 50,
    limit: int = 20,
) -> list[dict]:
    """Search for wineries via Google Places API (Text Search New).
    
    Requires GOOGLE_MAPS_API_KEY in .env to be set.
    Falls back silently if no key configured or API fails.
    """
    api_key = settings.google_maps_api_key
    if not api_key:
        return []

    try:
        radius_meters = radius * 1000
        text_query = f"winery {query}" if query else "wineries"

        body = {
            "textQuery": text_query,
            "maxResultCount": min(limit, 20),
        }
        if lat and lon:
            body["locationBias"] = {
                "circle": {
                    "center": {"latitude": lat, "longitude": lon},
                    "radius": radius_meters,
                }
            }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{GOOGLE_PLACES_BASE}/places:searchText",
                headers={
                    "X-Goog-Api-Key": api_key,
                    "X-Goog-FieldMask": (
                        "places.id,places.displayName,places.formattedAddress,"
                        "places.location,places.websiteUri,places.nationalPhoneNumber,"
                        "places.editorialSummary,places.photos,places.types,"
                        "places.rating,places.userRatingCount"
                    ),
                    "Content-Type": "application/json",
                },
                json=body,
            )
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for place in data.get("places", []):
                    loc = place.get("location", {})
                    lat = loc.get("latitude")
                    lon = loc.get("longitude")
                    if not lat or not lon:
                        continue

                    name = place.get("displayName", {}).get("text", "")
                    if not name:
                        continue

                    summary = place.get("editorialSummary", {})
                    description = summary.get("text", "") if isinstance(summary, dict) else ""

                    # Photo reference (for later resolution via Place Photos API)
                    photos = place.get("photos", [])
                    photo_ref = photos[0].get("name", "") if photos else ""

                    results.append({
                        "name": name,
                        "address": place.get("formattedAddress", ""),
                        "lat": float(lat),
                        "lon": float(lon),
                        "venue_type": "winery",
                        "website": place.get("websiteUri", ""),
                        "description": description[:300] if description else "",
                        "phone": place.get("nationalPhoneNumber", ""),
                        "image_url": photo_ref,
                        "google_place_id": place.get("id", ""),
                        "rating": place.get("rating"),
                        "rating_count": place.get("userRatingCount", 0),
                    })
                return results
    except Exception:
        pass
    return []


async def search_wineries_osm(
    query: str = "",
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    radius: int = 50,
    limit: int = 25,
) -> list[dict]:
    """Search for wineries/vineyards via OSM Overpass API."""
    # Build Overpass QL query
    filters = []
    if query:
        filters.append(f'(name ~ "{query}" || description ~ "{query}")')

    if lat and lon:
        deg = radius / 111.0
        bbox = f"{lat - deg},{lon - deg},{lat + deg},{lon + deg}"
        bbox_filter = f"({bbox})"
    else:
        bbox_filter = ""

    filter_str = " " + " && ".join(filters) if filters else ""
    overpass_query = f"""
    [out:json]{bbox_filter};
    (
      node["craft"="winery"]{filter_str};
      way["craft"="winery"]{filter_str};
      node["tourism"="vineyard"]{filter_str};
      way["tourism"="vineyard"]{filter_str};
      node["shop"="wine"]{filter_str};
      node["industrial"="winery"]{filter_str};
    );
    out center {limit};
    """

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": overpass_query},
            )
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for el in data.get("elements", []):
                    tags = el.get("tags", {})
                    name = tags.get("name", "")
                    if not name:
                        continue

                    # Get lat/lon
                    element_lat = el.get("lat") or el.get("center", {}).get("lat")
                    element_lon = el.get("lon") or el.get("center", {}).get("lon")
                    if not element_lat or not element_lon:
                        continue

                    description = tags.get("description", "") or tags.get("craft", "")
                    website = tags.get("website", "") or tags.get("contact:website", "")
                    phone = tags.get("phone", "") or tags.get("contact:phone", "")

                    # Build address from tags
                    addr_parts = [
                        tags.get("addr:housenumber", ""),
                        tags.get("addr:street", ""),
                        tags.get("addr:city", ""),
                        tags.get("addr:state", ""),
                        tags.get("addr:postcode", ""),
                        tags.get("addr:country", ""),
                    ]
                    address = ", ".join(p for p in addr_parts if p) or tags.get("display_name", "")

                    results.append({
                        "name": name,
                        "address": address,
                        "lat": float(element_lat),
                        "lon": float(element_lon),
                        "venue_type": "winery",
                        "website": website,
                        "description": description,
                        "phone": phone,
                        "image_url": "",
                        "osm_id": el.get("id"),
                        "osm_type": el.get("type"),
                    })
                return results
    except Exception:
        pass
    return []


async def search_vineyards_nominatim(query: str, limit: int = 10) -> list[dict]:
    """Fallback — search for wineries via Nominatim."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": f"winery {query}",
                    "format": "json",
                    "limit": limit,
                    "featuretype": "amenity",
                },
                headers={"User-Agent": "WINE-App/1.0 (buttergang.dev)"},
            )
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for item in data:
                    name = item.get("display_name", "").split(",")[0] if item.get("display_name") else query
                    results.append({
                        "name": name,
                        "address": item.get("display_name", ""),
                        "lat": float(item["lat"]),
                        "lon": float(item["lon"]),
                        "venue_type": "winery",
                        "website": "",
                        "description": "",
                        "phone": "",
                        "image_url": "",
                    })
                return results
    except Exception:
        pass
    return []


async def search_local_wineries(db: AsyncSession, query: str = "", limit: int = 30) -> list[Location]:
    """Search wineries already in the local DB."""
    stmt = select(Location).where(Location.venue_type == "winery")

    if query:
        q = f"%{query}%"
        stmt = stmt.where(
            or_(
                Location.name.ilike(q),
                Location.address.ilike(q),
                Location.description.ilike(q),
            )
        )

    stmt = stmt.order_by(Location.name).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def import_wineries_to_db(
    wineries: list[dict],
    db: AsyncSession,
) -> tuple[int, int]:
    """Import wineries into the database, avoiding duplicates by name+lat."""
    created = 0
    skipped = 0

    for w in wineries:
        # Check for existing (within ~100m tolerance)
        stmt = select(Location).where(
            Location.name == w["name"],
            Location.lat.between(w["lat"] - 0.001, w["lat"] + 0.001),
            Location.lon.between(w["lon"] - 0.001, w["lon"] + 0.001),
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            skipped += 1
            continue

        location = Location(
            name=w["name"],
            address=w.get("address", ""),
            lat=w["lat"],
            lon=w["lon"],
            venue_type="winery",
            website=w.get("website", ""),
            description=w.get("description", ""),
            phone=w.get("phone", ""),
            image_url=w.get("image_url", ""),
        )
        db.add(location)
        created += 1

    await db.commit()
    return created, skipped