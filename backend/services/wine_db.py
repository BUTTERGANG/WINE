"""Wine DB service — search local + external APIs."""

import httpx
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.wine import Wine


async def search_local_wines(db: AsyncSession, query: str, limit: int = 20) -> list[Wine]:
    """Fuzzy match against local wine database."""
    q = f"%{query}%"
    stmt = (
        select(Wine)
        .where(
            or_(
                Wine.producer.ilike(q),
                Wine.name.ilike(q),
                Wine.region.ilike(q),
                Wine.varietal.ilike(q),
            )
        )
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def search_external_wine_api(query: str) -> list[dict]:
    """Fallback: search external wine APIs for wines not in local DB."""
    results = []
    # Try GrapeMinds API (free tier, 290K wines)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.grapeminds.eu/public/v1/wines",
                params={"q": query, "per_page": 10},
                headers={}
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("data", []):
                    results.append({
                        "producer": item.get("producer", ""),
                        "name": item.get("name", item.get("display_name", "")),
                        "vintage": item.get("vintage"),
                        "region": item.get("region", ""),
                        "country": item.get("country", ""),
                        "varietal": item.get("grape_variety", ""),
                        "wine_type": item.get("color", "red"),
                        "abv": item.get("alcohol_percentage"),
                    })
    except Exception:
        pass  # Fallback silently
    return results


async def get_or_create_wine(db: AsyncSession, wine_data: dict) -> Wine:
    """Get existing wine or create a new one."""
    from sqlalchemy import select

    # Try to find by producer + name + vintage
    stmt = select(Wine).where(
        Wine.producer.ilike(wine_data["producer"]),
        Wine.name.ilike(wine_data["name"]),
    )
    if wine_data.get("vintage"):
        stmt = stmt.where(Wine.vintage == wine_data["vintage"])

    result = await db.execute(stmt)
    wine = result.scalar_one_or_none()

    if not wine:
        wine = Wine(
            producer=wine_data.get("producer", "Unknown Producer"),
            name=wine_data.get("name", "Unknown Wine"),
            vintage=wine_data.get("vintage"),
            region=wine_data.get("region", ""),
            country=wine_data.get("country", ""),
            varietal=wine_data.get("varietal", ""),
            wine_type=wine_data.get("wine_type", "red"),
            abv=wine_data.get("abv"),
            description=wine_data.get("description", ""),
        )
        db.add(wine)
        await db.commit()
        await db.refresh(wine)

    return wine