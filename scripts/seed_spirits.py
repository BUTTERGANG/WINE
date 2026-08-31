"""Seed spirit data — sample whiskeys, bourbons, scotches, and distilleries."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import init_db, async_session
from backend.models.spirit import Spirit, Distillery, SpiritTastingNote
from backend.models.user import User
from backend.services.auth import hash_password
from sqlalchemy import select, func

SEED_SPIRITS = [
    {"producer": "Buffalo Trace", "name": "Eagle Rare 10", "age_statement": "10", "region": "Kentucky", "country": "USA", "spirit_type": "bourbon", "abv": 45.0},
    {"producer": "Jack Daniel's", "name": "Old No. 7", "age_statement": "", "region": "Tennessee", "country": "USA", "spirit_type": "whiskey", "abv": 40.0},
    {"producer": "The Macallan", "name": "Sherry Oak 12", "age_statement": "12", "region": "Speyside", "country": "Scotland", "spirit_type": "scotch", "abv": 43.0},
    {"producer": "Jameson", "name": "Original", "age_statement": "", "region": "Cork", "country": "Ireland", "spirit_type": "irish", "abv": 40.0},
    {"producer": "Yamazaki", "name": "12 Year", "age_statement": "12", "region": "Yamazaki", "country": "Japan", "spirit_type": "japanese", "abv": 43.0},
    {"producer": "Michter's", "name": "US*1 Kentucky Straight Rye", "age_statement": "", "region": "Kentucky", "country": "USA", "spirit_type": "rye", "abv": 42.4},
    {"producer": "Lagavulin", "name": "16 Year", "age_statement": "16", "region": "Islay", "country": "Scotland", "spirit_type": "scotch", "abv": 43.0},
    {"producer": "Woodford Reserve", "name": "Distiller's Select", "age_statement": "", "region": "Kentucky", "country": "USA", "spirit_type": "bourbon", "abv": 45.2},
    {"producer": "Hibiki", "name": "Harmony", "age_statement": "", "region": "Yamazaki", "country": "Japan", "spirit_type": "japanese", "abv": 43.0},
    {"producer": "Redbreast", "name": "12 Year", "age_statement": "12", "region": "Cork", "country": "Ireland", "spirit_type": "irish", "abv": 40.0},
    {"producer": "Glenfiddich", "name": "12 Year", "age_statement": "12", "region": "Speyside", "country": "Scotland", "spirit_type": "scotch", "abv": 40.0},
    {"producer": "Bulleit", "name": "Bourbon Frontier Whiskey", "age_statement": "", "region": "Kentucky", "country": "USA", "spirit_type": "bourbon", "abv": 45.0},
    {"producer": "Laphroaig", "name": "10 Year", "age_statement": "10", "region": "Islay", "country": "Scotland", "spirit_type": "scotch", "abv": 43.0},
    {"producer": "Suntory Toki", "name": "Whisky", "age_statement": "", "region": "Yamazaki", "country": "Japan", "spirit_type": "japanese", "abv": 43.0},
    {"producer": "Wild Turkey", "name": "101", "age_statement": "", "region": "Kentucky", "country": "USA", "spirit_type": "bourbon", "abv": 50.5},
]

SEED_DISTILLERIES = [
    {"name": "Buffalo Trace Distillery", "address": "113 Great Buffalo Trace, Frankfort, KY 40601", "lat": 38.196, "lon": -84.875, "state_or_region": "KY", "country": "USA", "spirit_types": "bourbon,rye,whiskey"},
    {"name": "Jack Daniel's Distillery", "address": "133 Lynchburg Hwy, Lynchburg, TN 37352", "lat": 35.285, "lon": -86.375, "state_or_region": "TN", "country": "USA", "spirit_types": "whiskey"},
    {"name": "The Macallan Distillery", "address": "Easter Elchies, Craigellachie, AB38 9RX", "lat": 57.49, "lon": -3.30, "state_or_region": "Speyside", "country": "Scotland", "spirit_types": "scotch"},
    {"name": "Midleton Distillery", "address": "Old Midleton, Distillery Walk, Midleton, Co. Cork", "lat": 51.92, "lon": -8.18, "state_or_region": "Cork", "country": "Ireland", "spirit_types": "irish,whiskey"},
    {"name": "Yamazaki Distillery", "address": "Yamazaki, Shimamoto-cho, Mishima-gun, Osaka", "lat": 34.89, "lon": 135.67, "state_or_region": "Osaka", "country": "Japan", "spirit_types": "japanese"},
    {"name": "Lagavulin Distillery", "address": "Lagavulin, Isle of Islay, PA42 7DZ", "lat": 55.63, "lon": -6.05, "state_or_region": "Islay", "country": "Scotland", "spirit_types": "scotch"},
    {"name": "Glenfiddich Distillery", "address": "Dufftown, Keith, AB55 4DH", "lat": 57.45, "lon": -3.13, "state_or_region": "Speyside", "country": "Scotland", "spirit_types": "scotch"},
    {"name": "Wild Turkey Distillery", "address": "1525 Tyrone Rd, Lawrenceburg, KY 40342", "lat": 38.05, "lon": -84.89, "state_or_region": "KY", "country": "USA", "spirit_types": "bourbon,rye"},
]

SEED_NOTES = [
    {"rating": 5, "nose": "Vanilla, honey, citrus, oak", "palate": "Smooth, rich, balanced", "finish": "Long, warm, oaky", "body": "medium", "sweetness": "off-dry", "peat": "none", "notes": "A classic. Perfectly balanced bourbon."},
    {"rating": 4, "nose": "Smoky peat, brine, seaweed", "palate": "Rich, medicinal, smoky", "finish": "Very long, smoky, warming", "body": "full", "sweetness": "dry", "peat": "heavy", "notes": "The king of Islay. Not for beginners."},
    {"rating": 4, "nose": "Dried fruit, sherry, orange peel", "palate": "Rich sherry, spice, dark chocolate", "finish": "Long, drying, elegant", "body": "medium", "sweetness": "off-dry", "peat": "none", "notes": "Sherry bomb perfection. A Speyside classic."},
    {"rating": 3, "nose": "Honey, vanilla, green apple", "palate": "Smooth, light, malty", "finish": "Short, clean", "body": "light", "sweetness": "off-dry", "peat": "none", "notes": "Solid everyday sipper. Great value."},
    {"rating": 5, "nose": "Sandalwood, Mizunara oak, tropical fruit", "palate": "Elegant, complex, honeyed", "finish": "Long, refined, slightly spicy", "body": "medium", "sweetness": "off-dry", "peat": "none", "notes": "Japanese whisky at its finest. Sublime."},
    {"rating": 4, "nose": "Spicy rye, vanilla, caramel", "palate": "Bold, peppery, sweet", "finish": "Long, spicy, warm", "body": "full", "sweetness": "dry", "peat": "none", "notes": "Best rye in its price range. Punchy."},
    {"rating": 3, "nose": "Honey, pear, light floral", "palate": "Smooth, approachable, slightly sweet", "finish": "Medium, malty", "body": "light", "sweetness": "off-dry", "peat": "none", "notes": "Easy drinking. Great intro to single malt."},
    {"rating": 4, "nose": "Rich caramel, vanilla, toasted oak", "palate": "Full-bodied, smooth, buttery", "finish": "Long, warm, sweet", "body": "full", "sweetness": "sweet", "peat": "none", "notes": "Excellent bourbon. The honey finish is incredible."},
]


async def seed_spirits():
    await init_db()
    async with async_session() as s:
        # Check if already seeded
        count = (await s.execute(select(func.count()).select_from(Spirit))).scalar() or 0
        if count > 0:
            print(f"Database already has {count} spirits. Skipping seed.")
            return

        # Get or create demo user
        result = await s.execute(select(User).where(User.username == "wine_lover"))
        user = result.scalar_one_or_none()
        if not user:
            return

        # Create distilleries
        dist_map = {}
        for d in SEED_DISTILLERIES:
            dist = Distillery(**d)
            s.add(dist)
            await s.flush()
            dist_map[d["name"]] = dist

        # Create spirits
        spirits = []
        for sp in SEED_SPIRITS:
            spirit = Spirit(**sp)
            s.add(spirit)
            spirits.append(spirit)
        await s.flush()
        print(f"✅ Created {len(spirits)} spirits")

        # Create tasting notes
        import random
        notes_created = 0
        for i, note_data in enumerate(SEED_NOTES):
            spirit = spirits[i % len(spirits)]
            dist = list(dist_map.values())[i % len(dist_map)]
            note = SpiritTastingNote(
                spirit_id=spirit.id, user_id=user.id, distillery_id=dist.id,
                rating=note_data["rating"], nose=note_data["nose"],
                palate=note_data["palate"], finish=note_data["finish"],
                body=note_data["body"], sweetness=note_data["sweetness"],
                peat=note_data["peat"], notes=note_data["notes"],
                is_public=True,
            )
            s.add(note)
            notes_created += 1
        await s.commit()
        print(f"✅ Created {notes_created} spirit tasting notes")
        print(f"✅ Created {len(dist_map)} distilleries")
        print("🎉 Spirit seed complete!")


if __name__ == "__main__":
    asyncio.run(seed_spirits())