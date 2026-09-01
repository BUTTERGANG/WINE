"""Import free distillery data from multiple sources (no API keys needed).

Sources:
1. WhiskeyFYI API — ~130 global distilleries, free, no key
2. OpenStreetMap Overpass — unlimited, ODbL license
3. Winery enrichment restart (background)

Usage:
    python scripts/seed_free_distilleries.py
    python scripts/seed_free_distilleries.py --source whiskeyfyi
"""

import asyncio
import sys
import httpx
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import init_db, async_session
from backend.models.spirit import Distillery
from sqlalchemy import select, func

ROOT = Path(__file__).resolve().parent.parent


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
            country = d.get("country_name") or ""
            region = d.get("region_name") or ""
            founded = d.get("founded_year")
            try:
                founded = int(founded) if founded else None
            except (ValueError, TypeError):
                founded = None
            dist = Distillery(
                name=name, state_or_region=region, country=country,
                website=d.get("website", "") or "",
                lat=39.8, lon=-98.5, venue_type="distillery",
                description=(d.get("description") or "")[:500],
                founded_year=founded,
            )
            s.add(dist)
            created += 1

        await s.commit()
        total = (await s.execute(select(func.count()).select_from(Distillery))).scalar() or 0
        print(f"   ✅ Created: {created}, Skipped: {skipped}, Total: {total}")


async def import_overpass():
    """Query OSM Overpass for distilleries worldwide."""
    print("🌍 Querying OSM Overpass for distilleries...")

    regions = [
        ("North America", 15, -130, 60, -60),
        ("Europe", 35, -15, 60, 40),
        ("Asia", 10, 40, 55, 145),
        ("South America", -40, -80, 15, -35),
        ("Africa", -35, -20, 37, 50),
        ("Oceania", -45, 110, -10, 180),
    ]

    async with httpx.AsyncClient(timeout=30) as client:
        all_features = []
        for name, lat_min, lon_min, lat_max, lon_max in regions:
            query = f"""
            [out:json];
            (
                node["industrial"="distillery"]({lat_min},{lon_min},{lat_max},{lon_max});
                node["craft"="distillery"]({lat_min},{lon_min},{lat_max},{lon_max});
                node["man_made"="distillery"]({lat_min},{lon_min},{lat_max},{lon_max});
            );
            out center;
            """
            try:
                resp = await client.post(
                    "https://overpass-api.de/api/interpreter",
                    data={"data": query}, timeout=30,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    features = data.get("elements", [])
                    print(f"   {name}: {len(features)}")
                    all_features.extend(features)
            except Exception as e:
                print(f"   {name}: {e}")
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