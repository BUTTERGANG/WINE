"""Auto-seed on startup — called when the DB is empty."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import init_db, async_session
from backend.models.wine import Wine
from sqlalchemy import select, func

async def auto_seed():
    """Check if the DB is empty, and if so, seed it."""
    await init_db()
    async with async_session() as s:
        count = (await s.execute(select(func.count()).select_from(Wine))).scalar() or 0
        if count > 0:
            return  # Already seeded

    # Run seed scripts
    from scripts.seed import seed as seed_basic
    await seed_basic()

    # Try importing wineries (may fail if no internet, that's OK)
    try:
        from scripts.seed_north_america import main as seed_na
        await seed_na()
    except Exception:
        pass

    print("🍷 Auto-seed complete!")

if __name__ == "__main__":
    asyncio.run(auto_seed())