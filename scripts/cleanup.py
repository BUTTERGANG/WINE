"""Cleanup: remove non-winery entries and orphaned wines."""
import sys
sys.path.insert(0, '/home/alex/code/BUTTERGANG/WINE')
import asyncio
from backend.database import init_db, async_session
from backend.models.location import Location
from backend.models.wine import Wine, TastingNote
from sqlalchemy import select, or_

async def cleanup():
    await init_db()
    async with async_session() as s:
        # 1. Remove obvious non-winery entries from TTB data
        removed = 0
        result = await s.execute(
            select(Location).where(
                Location.venue_type == "winery",
                or_(
                    Location.name.ilike("%brew%"),
                    Location.name.ilike("%cider%"),
                    Location.name.ilike("%distill%"),
                    Location.name.ilike("%brewery%"),
                    Location.name.ilike("%cider house%"),
                    Location.name.ilike("%distillery%"),
                    Location.name.ilike("%anheuser%"),
                    Location.name.ilike("%miller%coors%"),
                    Location.name.ilike("%mizkan%"),
                    Location.name.ilike("%monster brewing%"),
                )
            )
        )
        entries = list(result.scalars().all())
        for loc in entries:
            await s.delete(loc)
            removed += 1
        print(f"Removed {removed} non-winery entries")

        # 2. Delete orphaned wines (no tasting notes)
        no_notes = 0
        result = await s.execute(select(Wine))
        for wine in result.scalars().all():
            check = await s.execute(
                select(TastingNote).where(TastingNote.wine_id == wine.id).limit(1)
            )
            if not check.scalar_one_or_none():
                await s.delete(wine)
                no_notes += 1
        print(f"Deleted {no_notes} orphaned wines")

        await s.commit()
        print("Cleanup complete!")

asyncio.run(cleanup())