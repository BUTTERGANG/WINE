"""Import BeerAdvocate breweries into the Distillery table."""
import sys
sys.path.insert(0, '/home/alex/code/BUTTERGANG/WINE')
import asyncio, csv
from pathlib import Path
from backend.database import init_db, async_session
from backend.models.spirit import Distillery
from sqlalchemy import select, func

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "beeradvocate_breweries.csv"


async def import_breweries():
    if not CSV_PATH.exists():
        print(f"❌ BeerAdvocate data not found at {CSV_PATH}")
        return
    
    await init_db()
    async with async_session() as s:
        with open(CSV_PATH) as f:
            rows = list(csv.DictReader(f))
        
        breweries = {}
        for r in rows:
            name = r['brewery'].strip()
            if not name: continue
            if name not in breweries:
                breweries[name] = r
        
        print(f"Found {len(breweries)} unique breweries")
        
        created = 0
        skipped = 0
        for name, data in breweries.items():
            result = await s.execute(select(Distillery.id).where(Distillery.name == name))
            if result.first() is not None:
                skipped += 1
                continue
            
            dist = Distillery(
                name=name,
                venue_type="brewery",
                description=f"BeerAdvocate brewery",
                lat=39.8283, lon=-98.5795,
                country="USA",
            )
            s.add(dist)
            created += 1
        
        await s.commit()
        total = (await s.execute(select(func.count()).select_from(Distillery))).scalar() or 0
        print(f"✅ Created: {created}, Skipped: {skipped}, Total: {total}")


if __name__ == "__main__":
    asyncio.run(import_breweries())