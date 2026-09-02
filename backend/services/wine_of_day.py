"""Wine service — shared logic for wine operations."""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.wine import Wine, TastingNote


async def get_wine_of_the_day(db: AsyncSession) -> dict:
    """Pick a random wine with a tasting note for the Wine of the Day."""
    # Use SQL random for efficiency
    result = await db.execute(
        select(Wine)
        .where(Wine.id.in_(
            select(TastingNote.wine_id).distinct()
        ))
        .order_by(func.random())
        .limit(1)
    )
    wine = result.scalar_one_or_none()

    if not wine:
        return {}

    note_result = await db.execute(
        select(TastingNote)
        .where(TastingNote.wine_id == wine.id)
        .order_by(TastingNote.created_at.desc())
        .limit(1)
    )
    note = note_result.scalar_one_or_none()

    return {
        "id": wine.id,
        "producer": wine.producer,
        "name": wine.name,
        "vintage": wine.vintage,
        "region": wine.region,
        "varietal": wine.varietal,
        "wine_type": wine.wine_type,
        "display": wine.display_name,
        "avg_rating": None,
        "note_preview": note.notes if note else None,
        "note_rating": note.rating if note else None,
    }
