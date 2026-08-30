"""Seed wineries from the winerymap dataset (34k wineries worldwide, 3.8k US)."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import init_db, async_session
from backend.models.location import Location

VINEYARDS_PATH = Path(__file__).resolve().parent.parent / "data" / "vineyards.json"


async def seed_from_winerymap(region_filter: str = "United States", limit: int = 0):
    """Import wineries from the winerymap dataset.
    
    Args:
        region_filter: Only import regions containing this string (e.g. "United States" or "" for all)
        limit: Max wineries to import (0 = all)
    """
    if not VINEYARDS_PATH.exists():
        print(f"❌ Dataset not found at {VINEYARDS_PATH}")
        print("   Download from: https://raw.githubusercontent.com/oOo0oOo/winerymap/main/vineyards.json")
        return

    with open(VINEYARDS_PATH) as f:
        data = json.load(f)

    await init_db()

    async with async_session() as session:
        # Count existing wineries for dedup
        from sqlalchemy import select, func
        existing = await session.execute(
            select(func.count()).select_from(Location).where(Location.venue_type == "winery")
        )
        existing_count = existing.scalar() or 0
        print(f"📊 Existing wineries in DB: {existing_count}")

        # Filter regions
        regions = {}
        for region_key, region_val in data.items():
            if region_filter and region_filter not in region_key:
                continue
            regions[region_key] = region_val

        print(f"📋 Regions matching '{region_filter}': {len(regions)}")

        created = 0
        skipped_existing = 0
        skipped_no_name = 0

        for region_key, region_val in regions.items():
            vineyards = region_val.get("vineyards", [])
            
            # Derive state from region key (e.g. "Napa Valley, United States")
            parts = region_key.split(",")
            country = parts[-1].strip() if len(parts) > 1 else ""
            state_or_region = parts[0].strip() if len(parts) > 1 else region_key

            for v in vineyards:
                if limit and created >= limit:
                    break

                # Format: [lat, lon, name, website, [grape_list]]
                if len(v) < 3:
                    skipped_no_name += 1
                    continue

                lat = v[0]
                lon = v[1]
                name = v[2]
                website = v[3] if len(v) > 3 else ""
                grapes = v[4] if len(v) > 4 else []

                if not name:
                    skipped_no_name += 1
                    continue

                # Check for existing (within ~100m tolerance)
                result = await session.execute(
                    select(Location.id).where(
                        Location.name == name,
                        Location.lat.between(lat - 0.001, lat + 0.001),
                        Location.lon.between(lon - 0.001, lon + 0.001),
                    )
                )
                if result.scalar_one_or_none():
                    skipped_existing += 1
                    continue

                # Build description from grapes and region
                desc_parts = []
                if country == "United States":
                    desc_parts.append(f"Located in {state_or_region}")
                else:
                    desc_parts.append(f"Located in {region_key}")
                if grapes:
                    # Grapes can be IDs (int) or names (str)
                    grape_names = [str(g) for g in grapes[:5]]
                    desc_parts.append(f"Known for: {', '.join(grape_names)}")

                location = Location(
                    name=name,
                    address=state_or_region,
                    lat=lat,
                    lon=lon,
                    venue_type="winery",
                    website=website,
                    description=". ".join(desc_parts),
                    phone="",
                )
                session.add(location)
                created += 1

            if limit and created >= limit:
                break

        await session.commit()

        print(f"\n✅ Import complete!")
        print(f"   Created: {created}")
        print(f"   Skipped (already in DB): {skipped_existing}")
        print(f"   Skipped (no name): {skipped_no_name}")

        # Verify
        final_count = await session.execute(
            select(func.count()).select_from(Location).where(Location.venue_type == "winery")
        )
        print(f"   Total wineries now: {final_count.scalar()}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="United States", help="Filter by region (empty=all)")
    parser.add_argument("--limit", type=int, default=0, help="Max wineries to import (0=all)")
    args = parser.parse_args()

    asyncio.run(seed_from_winerymap(region_filter=args.region, limit=args.limit))