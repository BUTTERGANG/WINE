"""Import free distillery data from multiple sources (no API keys needed).

Sources:
1. WhiskeyFYI API — ~130 global distilleries, free, no key
2. OpenStreetMap Overpass — unlimited, ODbL license

Usage:
    python scripts/seed_free_distilleries.py
    python scripts/seed_free_distilleries.py --source whiskeyfyi
    python scripts/seed_free_distilleries.py --source overpass
"""

import asyncio
import json
import subprocess
import sys
import httpx
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import init_db, async_session
from backend.models.spirit import Distillery
from sqlalchemy import select, func


async def import_whiskeyfyi():
    """Import distilleries from the free WhiskeyFYI API (no key needed)."""
    print("🥃 Importing from WhiskeyFYI API...")
    async with httpx.AsyncClient(timeout=15) as client:
        all_results = []
        for page in range(1, 6):
            try:
                resp = await client.get(
                    f"https://whiskeyfyi.com/api/v1/distilleries/?page={page}",
                    headers={"User-Agent": "WINE/1.0"}
                )
                if resp.status_code != 200:
                    break
                data = resp.json()
                results = data.get("results", [])
                if not results:
                    break
                all_results.extend(results)
                if not data.get("next"):
                    break
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"   Page {page} error: {e}")
                break

    print(f"   Found {len(all_results)} distilleries")

    await init_db()
    async with async_session() as s:
        created = 0
        skipped = 0
        for d in all_results:
            name = (d.get("name") or "").strip()
            if not name:
                skipped += 1
                continue
            existing = await s.execute(select(Distillery.id).where(Distillery.name.ilike(name)))
            if existing.first() is not None:
                skipped += 1
                continue
            dist = Distillery(
                name=name,
                state_or_region=d.get("region_name") or "",
                country=d.get("country_name") or "",
                website=d.get("website", "") or "",
                lat=39.8, lon=-98.5, venue_type="distillery",
                description=(d.get("description") or "")[:500],
            )
            s.add(dist)
            created += 1

        await s.commit()
        total = (await s.execute(select(func.count()).select_from(Distillery))).scalar() or 0
        print(f"   ✅ Created: {created}, Skipped: {skipped}, Total: {total}")


def _overpass_query(region_name: str, lat_min: float, lon_min: float, lat_max: float, lon_max: float) -> list[dict]:
    """Query Overpass API via subprocess (curl — httpx sends wrong content-type)."""
    query = f"""[out:json];(
        node["industrial"="distillery"]({lat_min},{lon_min},{lat_max},{lon_max});
        node["craft"="distillery"]({lat_min},{lon_min},{lat_max},{lon_max});
        node["man_made"="distillery"]({lat_min},{lon_min},{lat_max},{lon_max});
    );out center;"""
    
    try:
        result = subprocess.run(
            ["curl", "-s", "-X", "POST", "https://overpass-api.de/api/interpreter",
             "--data-urlencode", f"data={query}"],
            capture_output=True, text=True, timeout=45,
        )
        if result.returncode != 0 or not result.stdout:
            print(f"   {region_name}: curl failed (exit {result.returncode})")
            return []
        
        data = json.loads(result.stdout)
        elements = data.get("elements", [])
        print(f"   {region_name}: {len(elements)} distilleries")
        return elements
    except subprocess.TimeoutExpired:
        print(f"   {region_name}: timeout")
        return []
    except json.JSONDecodeError as e:
        print(f"   {region_name}: parse error - {e}")
        return []


async def import_overpass():
    """Query OSM Overpass for distilleries worldwide using subprocess curl."""
    print("🌍 Querying OSM Overpass for distilleries...")

    regions = [
        ("North America", 15, -130, 60, -60),
        ("Europe", 35, -15, 60, 40),
        ("Asia", 10, 40, 55, 145),
        ("South America", -40, -80, 15, -35),
        ("Africa", -35, -20, 37, 50),
        ("Oceania", -45, 110, -10, 180),
    ]

    all_features = []
    for name, lat_min, lon_min, lat_max, lon_max in regions:
        features = _overpass_query(name, lat_min, lon_min, lat_max, lon_max)
        all_features.extend(features)
        await asyncio.sleep(2)

    print(f"   Total from OSM: {len(all_features)}")

    await init_db()
    async with async_session() as s:
        created = 0
        skipped = 0
        for elem in all_features:
            tags = elem.get("tags", {})
            name = (tags.get("name") or "").strip()
            if not name:
                continue
            lat = elem.get("lat") or (elem.get("center") or {}).get("lat") or 0
            lon = elem.get("lon") or (elem.get("center") or {}).get("lon") or 0
            if lat == 0:
                continue
            existing = await s.execute(
                select(Distillery.id).where(Distillery.name.ilike(name))
            )
            if existing.first() is not None:
                skipped += 1
                continue
            dist = Distillery(
                name=name, lat=lat, lon=lon, venue_type="distillery",
                website=tags.get("website", "") or "",
                country=tags.get("country", "") or "",
                state_or_region=tags.get("addr:state", "") or tags.get("region", "") or "",
                description=(tags.get("description") or "")[:500],
            )
            s.add(dist)
            created += 1

        await s.commit()
        total = (await s.execute(select(func.count()).select_from(Distillery))).scalar() or 0
        print(f"   ✅ Created: {created}, Skipped: {skipped}, Total: {total}")


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=str, default="all", help="all, whiskeyfyi, overpass")
    args = parser.parse_args()

    await init_db()
    async with async_session() as s:
        start = (await s.execute(select(func.count()).select_from(Distillery))).scalar() or 0
    print(f"📊 Starting with {start} distilleries")

    if args.source in ("all", "whiskeyfyi"):
        await import_whiskeyfyi()

    if args.source in ("all", "overpass"):
        await import_overpass()

    async with async_session() as s:
        end = (await s.execute(select(func.count()).select_from(Distillery))).scalar() or 0
    print(f"\n✅ Final: {end} distilleries (+{end - start})")


if __name__ == "__main__":
    asyncio.run(main())