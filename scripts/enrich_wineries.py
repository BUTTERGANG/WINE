"""Google Places integration for winery enrichment and discovery.

Requires GOOGLE_MAPS_API_KEY in .env to use.

Usage:
    # Enrich existing wineries with phone, website, rating
    python scripts/enrich_wineries.py

    # Search Google Places for wineries near a location
    python scripts/enrich_wineries.py --search "Napa, CA" --radius 50000
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import settings
from backend.database import init_db, async_session
from backend.models.location import Location
from sqlalchemy import select, func


GOOGLE_API_KEY = settings.google_maps_api_key


async def search_places(query: str, radius: int = 50000) -> list[dict]:
    """Search Google Places for wineries near a location."""
    if not GOOGLE_API_KEY:
        print("⚠️  No GOOGLE_MAPS_API_KEY set in .env")
        return []

    print(f"🔍 Searching Google Places for: '{query}' (radius={radius}m)")
    
    # First, geocode the query
    async with httpx.AsyncClient(timeout=10) as client:
        geo_resp = await client.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": query, "key": GOOGLE_API_KEY},
        )
        if geo_resp.status_code != 200:
            print(f"   Geocode failed: {geo_resp.status_code}")
            return []
        geo_data = geo_resp.json()
        if not geo_data.get("results"):
            print(f"   No location found for: {query}")
            return []
        lat = geo_data["results"][0]["geometry"]["location"]["lat"]
        lng = geo_data["results"][0]["geometry"]["location"]["lng"]
        print(f"   Centered on: {lat:.4f}, {lng:.4f}")

        # Now search for wineries
        all_results = []
        next_page_token = None
        
        for page in range(3):  # Max 3 pages (180 results)
            params = {
                "location": f"{lat},{lng}",
                "radius": radius,
                "type": "point_of_interest",
                "keyword": "winery",
                "key": GOOGLE_API_KEY,
            }
            if next_page_token:
                params["pagetoken"] = next_page_token
                await asyncio.sleep(2)  # Must wait for pagetoken to become valid

            resp = await client.get(
                "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
                params=params,
                timeout=15,
            )
            if resp.status_code != 200:
                break
            data = resp.json()
            results = data.get("results", [])
            all_results.extend(results)
            print(f"   Page {page+1}: {len(results)} results")

            next_page_token = data.get("next_page_token")
            if not next_page_token:
                break

        print(f"   Total found: {len(all_results)}")
        return all_results


async def enrich_winery(winery: Location, api_key: str) -> bool:
    """Enrich a single winery with Google Places data (phone, website, rating)."""
    if not api_key:
        return False
    
    # Skip if already has website
    if winery.website:
        return False

    async with httpx.AsyncClient(timeout=10) as client:
        # Search for this winery
        query = f"{winery.name} winery"
        if winery.state_or_region:
            query += f" {winery.state_or_region}"
        
        resp = await client.get(
            "https://maps.googleapis.com/maps/api/place/findplacefromtext/json",
            params={
                "input": query,
                "inputtype": "textquery",
                "fields": "place_id,name,formatted_address,geometry,rating,user_ratings_total,website,formatted_phone_number,international_phone_number",
                "key": api_key,
            },
            timeout=10,
        )
        if resp.status_code != 200:
            return False
        
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return False
        
        candidate = candidates[0]
        changed = False
        
        if candidate.get("website") and not winery.website:
            winery.website = candidate["website"]
            changed = True
        if candidate.get("formatted_phone_number") and not winery.phone:
            winery.phone = candidate["formatted_phone_number"]
            changed = True
        if candidate.get("international_phone_number") and not winery.phone:
            winery.phone = candidate["international_phone_number"]
            changed = True
        if candidate.get("rating") and not winery.description:
            desc = f"⭐ {candidate['rating']}/5 on Google"
            if candidate.get("user_ratings_total"):
                desc += f" ({candidate['user_ratings_total']} reviews)"
            winery.description = desc
            changed = True
        # Update coordinates if Google has better ones
        if candidate.get("geometry"):
            glat = candidate["geometry"]["location"]["lat"]
            glon = candidate["geometry"]["location"]["lng"]
            # Only update if our coords are a centroid (imprecise)
            if abs(winery.lat - round(winery.lat, 1)) < 0.05:
                winery.lat = glat
                winery.lon = glon
                changed = True

        return changed


async def enrich_all(limit: int = 500):
    """Enrich existing wineries with Google Places data."""
    if not GOOGLE_API_KEY:
        print("⚠️  No GOOGLE_MAPS_API_KEY set in .env")
        print("   Add to .env: GOOGLE_MAPS_API_KEY=your_key")
        return

    await init_db()
    async with async_session() as s:
        # Get wineries without website (most need enrichment)
        result = await s.execute(
            select(Location)
            .where(Location.venue_type == "winery", Location.website == "")
            .limit(limit)
        )
        wineries = list(result.scalars().all())
        print(f"📊 Enriching up to {len(wineries)} wineries from Google Places...")

        enriched = 0
        for i, w in enumerate(wineries):
            ok = await enrich_winery(w, GOOGLE_API_KEY)
            if ok:
                enriched += 1
            if (i + 1) % 50 == 0:
                await s.flush()
                print(f"   Progress: {i+1}/{len(wineries)} ({enriched} enriched)")

        await s.commit()
        print(f"✅ Enriched {enriched} wineries with Google Places data")


async def search_and_import(query: str, radius: int = 50000):
    """Search Google Places for wineries and import them into the DB."""
    if not GOOGLE_API_KEY:
        print("⚠️  No GOOGLE_MAPS_API_KEY set in .env")
        return

    results = await search_places(query, radius)
    if not results:
        return

    await init_db()
    async with async_session() as s:
        imported = 0
        skipped = 0
        for place in results:
            name = place.get("name", "").strip()
            if not name:
                skipped += 1
                continue

            # Check if already in DB (by name + proximity)
            lat = place["geometry"]["location"]["lat"]
            lng = place["geometry"]["location"]["lng"]
            
            existing = await s.execute(
                select(Location.id).where(
                    Location.name == name,
                    Location.lat >= lat - 0.02,
                    Location.lat <= lat + 0.02,
                    Location.lon >= lng - 0.02,
                    Location.lon <= lng + 0.02,
                )
            )
            if existing.first() is not None:
                skipped += 1
                continue

            address = place.get("vicinity", "")
            rating = place.get("rating")
            total_ratings = place.get("user_ratings_total")
            desc = f"⭐ {rating}/5 ({total_ratings} reviews)" if rating else ""

            location = Location(
                name=name,
                address=address,
                lat=lat,
                lon=lng,
                venue_type="winery",
                website=place.get("website", ""),
                description=desc,
            )
            # Try to extract state from address
            for part in address.split(","):
                part = part.strip()
                if len(part) == 2 and part.isupper():
                    location.state_or_region = part
                    break

            s.add(location)
            imported += 1

        await s.commit()
        print(f"✅ Imported {imported} new wineries from Google Places ({skipped} skipped)")


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--enrich", type=int, default=0, help="Enrich N wineries with Google data")
    parser.add_argument("--search", type=str, default="", help="Search Google Places for wineries")
    parser.add_argument("--radius", type=int, default=50000, help="Search radius in meters")
    args = parser.parse_args()

    if args.search:
        await search_and_import(args.search, args.radius)
    elif args.enrich:
        await enrich_all(args.enrich)
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())