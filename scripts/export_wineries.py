"""Export all wineries to a portable JSON for production migration.

Dumps every winery from the local SQLite into data/wineries_export.json.
Commit this file to the repo, then on Replit run:

    python scripts/import_wineries_export.py

which upserts these rows into the Replit Postgres (DATABASE_URL).

Usage: python scripts/export_wineries.py [--limit N] [--state CA]
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import init_db, async_session
from backend.models.location import Location
from sqlalchemy import select

OUT = Path(__file__).resolve().parent.parent / "data" / "wineries_export.json"


async def export(limit: int = 0, state: str = ""):
    await init_db()
    async with async_session() as s:
        query = select(Location).where(Location.venue_type == "winery")
        if state:
            query = query.where(Location.state_or_region == state.upper())
        query = query.order_by(Location.name)
        if limit:
            query = query.limit(limit)

        result = await s.execute(query)
        wineries = list(result.scalars().all())

        rows = []
        for w in wineries:
            rows.append({
                "name": w.name,
                "address": w.address or "",
                "state_or_region": w.state_or_region or "",
                "country": w.country or "",
                "lat": w.lat,
                "lon": w.lon,
                "venue_type": w.venue_type or "winery",
                "website": w.website or "",
                "phone": w.phone or "",
                "description": w.description or "",
            })

        OUT.parent.mkdir(parents=True, exist_ok=True)
        with open(OUT, "w") as f:
            json.dump({"count": len(rows), "wineries": rows}, f, indent=2)

        print(f"✅ Exported {len(rows)} wineries to {OUT}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--state", type=str, default="")
    args = p.parse_args()
    asyncio.run(export(args.limit, args.state))