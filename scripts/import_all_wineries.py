"""One-shot import: all wineries from all sources into the database.

Run this on Replit (or any fresh DB) to get all 34k+ wineries:

    python scripts/import_all_wineries.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import init_db, async_session
from backend.models.location import Location
from backend.models.wine import Wine
from sqlalchemy import select, func


async def count_wineries() -> int:
    await init_db()
    async with async_session() as s:
        r = await s.execute(
            select(func.count()).select_from(Location).where(Location.venue_type == "winery")
        )
        return r.scalar() or 0


async def import_all():
    print("=" * 60)
    print("🍷 BULK WINERY IMPORT")
    print("=" * 60)

    # 1. Basic seed (users, wines, tasting notes)
    print("\n1️⃣  Basic seed data (users, wines, notes)...")
    from scripts.seed import seed as seed_basic
    await seed_basic()

    # 2. winerymap global dataset (34k wineries, 60+ countries)
    print("\n2️⃣  Global wineries from winerymap (34k)...")
    from scripts.seed_winerymap import seed_from_winerymap
    await seed_from_winerymap(region_filter="", limit=0)

    # 3. TTB North America (16k+ US wineries with street addresses)
    print("\n3️⃣  US wineries from TTB (18k permits)...")
    from scripts.seed_north_america import load_ttb_wineries, load_winerymap_wineries, apply_centroids, import_to_database
    try:
        wineries = load_ttb_wineries()
        wm = load_winerymap_wineries()
        for w in wineries:
            key = w["name"].upper()
            if key in wm and w["lat"] is None:
                w["lat"], w["lon"] = wm[key]["lat"], wm[key]["lon"]
                w["source"] = "winerymap"
        apply_centroids(wineries)
        created, skipped = await import_to_database(wineries)
        print(f"   TTB import: {created} created, {skipped} skipped")
    except Exception as e:
        print(f"   TTB import skipped: {e}")

    final = await count_wineries()
    print(f"\n🎉 Total wineries in database: {final}")
    print("✅ Done!")


if __name__ == "__main__":
    asyncio.run(import_all())