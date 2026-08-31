"""Import exported wineries into the production (Replit Postgres) database.

Run this on Replit after committing data/wineries_export.json:

    python scripts/import_wineries_export.py

Uses DATABASE_URL from the environment (Replit auto-provisions Postgres).
Deduplicates by name + lat/lon proximity (~2km). Upserts description,
website, and phone when a match is found.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import init_db, async_session
from backend.models.location import Location
from sqlalchemy import select, func

EXPORT_PATH = Path(__file__).resolve().parent.parent / "data" / "wineries_export.json"


async def main():
    if not EXPORT_PATH.exists():
        print(f"❌ Export file not found at {EXPORT_PATH}")
        print("   Run scripts/export_wineries.py first, then commit the file.")
        return

    with open(EXPORT_PATH) as f:
        data = json.load(f)

    print(f"📦 Loading {data['count']} wineries from export...")
    wineries = data["wineries"]

    await init_db()
    async with async_session() as s:
        created = 0
        updated = 0
        skipped = 0

        for i, w in enumerate(wineries):
            if not w["lat"] or not w["lon"]:
                skipped += 1
                continue

            # Check for existing by name + proximity
            result = await s.execute(
                select(Location).where(
                    Location.name == w["name"],
                    Location.lat >= w["lat"] - 0.02,
                    Location.lat <= w["lat"] + 0.02,
                    Location.lon >= w["lon"] - 0.02,
                    Location.lon <= w["lon"] + 0.02,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update fields if they're richer
                changed = False
                if w["description"] and (not existing.description or existing.description.startswith("Located in")):
                    existing.description = w["description"]
                    changed = True
                if w["website"] and not existing.website:
                    existing.website = w["website"]
                    changed = True
                if w["phone"] and not existing.phone:
                    existing.phone = w["phone"]
                    changed = True
                if w["state_or_region"] and not existing.state_or_region:
                    existing.state_or_region = w["state_or_region"]
                    changed = True
                if w["country"] and not existing.country:
                    existing.country = w["country"]
                    changed = True
                if changed:
                    updated += 1
            else:
                location = Location(
                    name=w["name"],
                    address=w.get("address", ""),
                    state_or_region=w.get("state_or_region", ""),
                    country=w.get("country", "United States"),
                    lat=w["lat"],
                    lon=w["lon"],
                    venue_type="winery",
                    website=w.get("website", ""),
                    phone=w.get("phone", ""),
                    description=w.get("description", ""),
                )
                s.add(location)
                created += 1

            if (i + 1) % 500 == 0:
                await s.flush()
                print(f"   Progress: {i+1}/{len(wineries)} (created={created}, updated={updated})")

        await s.commit()

        # Final count
        total = (await s.execute(
            select(func.count()).select_from(Location).where(Location.venue_type == "winery")
        )).scalar() or 0

        print(f"\n✅ Import complete!")
        print(f"   Created: {created}")
        print(f"   Updated: {updated}")
        print(f"   Skipped: {skipped}")
        print(f"   Total wineries now: {total}")


if __name__ == "__main__":
    asyncio.run(main())