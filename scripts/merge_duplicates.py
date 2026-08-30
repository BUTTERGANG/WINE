"""Merge duplicate winery entries — transfer tasting notes to winerymap IDs."""
import sys
sys.path.insert(0, '/home/alex/code/BUTTERGANG/WINE')
import asyncio
from backend.database import init_db, async_session
from backend.models.location import Location
from backend.models.wine import TastingNote
from sqlalchemy import select

DUPES = [
    # (name, approximate lat/lon range)
    ("Robert Mondavi Winery", 38.43, 38.44),
    ("Opus One Winery", 38.43, 38.44),
    ("Fritz Cellars", 36.77, 36.79),
    ("Raymond Vineyard & Cellar", 36.77, 36.79),
]

async def merge():
    await init_db()
    async with async_session() as s:
        for name, lat_min, lat_max in DUPES:
            # Find all locations with this name
            result = await s.execute(
                select(Location).where(Location.name == name)
            )
            locations = list(result.scalars().all())
            
            if len(locations) <= 1:
                continue
            
            print(f"\n=== {name}: {len(locations)} entries ===")
            
            # The winerymap entries have the most info (lat/lon from dataset)
            # The seed entries have the tasting notes
            winerymap_entries = [l for l in locations if not l.description and l.website == ""]
            seed_entries = [l for l in locations if l.description or l.website]
            
            for wm in winerymap_entries:
                print(f"  winerymap: id={wm.id[:12]} lat={wm.lat:.3f}")
            for se in seed_entries:
                print(f"  seed:      id={se.id[:12]} lat={se.lat:.3f} website={bool(se.website)} desc={bool(se.description)}")
            
            # Pick the best one to keep (prefer winerymap for lat/lon, seed for website/description)
            # Transfer tasting notes from seed to winerymap
            for se in seed_entries:
                # Count notes attached to seed venue
                notes = await s.execute(
                    select(TastingNote).where(TastingNote.location_id == se.id)
                )
                notes_list = list(notes.scalars().all())
                
                if not notes_list:
                    print(f"  Seed has no tasting notes, safe to skip")
                    continue
                
                for wm in winerymap_entries:
                    # Transfer notes from seed -> winerymap
                    for note in notes_list:
                        note.location_id = wm.id
                    print(f"  Transferred {len(notes_list)} notes from seed ({se.id[:12]}) to winerymap ({wm.id[:12]})")
            
            # Delete seed entries that no longer have notes
            for se in seed_entries:
                check = await s.execute(
                    select(TastingNote).where(TastingNote.location_id == se.id)
                )
                if not check.scalar_one_or_none():
                    await s.delete(se)
                    print(f"  Deleted seed entry {se.id[:12]}")
        
        await s.commit()
        print(f"\n✅ Merge complete!")

asyncio.run(merge())