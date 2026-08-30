"""Geocoding service — address to lat/lon via Nominatim."""

import asyncio
import time
from typing import Optional

import httpx

# Nominatim asks for <= 1 request/second. Serialize calls and only sleep
# for the remainder of the 1s window since the previous call.
_nominatim_lock = asyncio.Lock()
_last_call = 0.0
_MIN_INTERVAL = 1.1


async def _throttle():
    global _last_call
    wait = _MIN_INTERVAL - (time.monotonic() - _last_call)
    if wait > 0:
        await asyncio.sleep(wait)
    _last_call = time.monotonic()


async def geocode_address(address: str) -> Optional[tuple[float, float, str]]:
    """Resolve an address to (lat, lon, display_name)."""
    async with _nominatim_lock:
        await _throttle()

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={
                        "q": address,
                        "format": "json",
                        "limit": 1,
                    },
                    headers={
                        "User-Agent": "WINE-App/1.0 (buttergang.dev)",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        lat = float(data[0]["lat"])
                        lon = float(data[0]["lon"])
                        display_name = data[0].get("display_name", address)
                        return (lat, lon, display_name)
        except Exception:
            pass

    return None


async def search_venues(query: str) -> list[dict]:
    """Search for venues (restaurants, wineries, bars) matching a query."""
    async with _nominatim_lock:
        await _throttle()

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={
                        "q": query,
                        "format": "json",
                        "limit": 5,
                        "category": "amenity" if any(
                            kw in query.lower() for kw in ["restaurant", "bar", "winery", "cafe"]
                        ) else None,
                    },
                    headers={"User-Agent": "WINE-App/1.0 (buttergang.dev)"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = []
                    for item in data:
                        venue_type = "other"
                        name = item.get("display_name", "").split(",")[0]
                        if "restaurant" in name.lower():
                            venue_type = "restaurant"
                        elif "winery" in name.lower() or "vineyard" in name.lower():
                            venue_type = "winery"
                        elif "bar" in name.lower() or "pub" in name.lower() or "tavern" in name.lower():
                            venue_type = "bar"

                        results.append({
                            "name": name,
                            "address": item.get("display_name", ""),
                            "lat": float(item["lat"]),
                            "lon": float(item["lon"]),
                            "venue_type": venue_type,
                        })
                    return results
        except Exception:
            pass

    return []