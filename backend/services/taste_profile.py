"""Taste profile analysis — derive palate preferences from rating history."""

from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.wine import Wine, TastingNote


async def compute_taste_profile(user_id: str, db: AsyncSession) -> dict:
    """Analyze a user's tasting history and build a taste profile."""

    result = await db.execute(
        select(TastingNote)
        .options(selectinload(TastingNote.wine))
        .where(TastingNote.user_id == user_id)
        .order_by(TastingNote.created_at.desc())
    )
    notes = list(result.scalars().all())

    if not notes:
        return {
            "has_data": False,
            "total_tastings": 0,
            "favorite_type": None,
            "favorite_varietal": None,
            "favorite_region": None,
            "avg_rating": None,
            "preferred_body": None,
            "preferred_sweetness": None,
            "rating_by_type": {},
            "top_wines": [],
            "palette_summary": "No tastings yet — start logging to discover your palate!",
        }

    type_ratings = defaultdict(list)
    varietal_ratings = defaultdict(list)
    region_ratings = defaultdict(list)
    body_ratings = defaultdict(list)
    sweetness_ratings = defaultdict(list)
    high_rated = []

    for note in notes:
        wine = note.wine
        if not wine:
            continue
        type_ratings[wine.wine_type].append(note.rating)
        if wine.varietal:
            varietal_ratings[wine.varietal].append(note.rating)
        if wine.region:
            region_ratings[wine.region].append(note.rating)
        if note.body:
            body_ratings[note.body].append(note.rating)
        if note.sweetness:
            sweetness_ratings[note.sweetness].append(note.rating)

        if note.rating >= 4:
            high_rated.append({
                "id": wine.id,
                "display_name": wine.display_name,
                "rating": note.rating,
                "wine_type": wine.wine_type,
                "varietal": wine.varietal or "",
                "region": wine.region or "",
            })

    def avg(lst):
        return round(sum(lst) / len(lst), 1) if lst else 0

    def best_category(ratings_dict):
        scored = {k: avg(v) for k, v in ratings_dict.items() if len(v) >= 1}
        if not scored:
            return None
        return max(scored, key=scored.get)

    avg_rating = avg([n.rating for n in notes if n.rating])

    summary_parts = []
    fav_type = best_category(type_ratings)
    fav_varietal = best_category(varietal_ratings)
    fav_region = best_category(region_ratings)
    pref_body = best_category(body_ratings)
    pref_sweetness = best_category(sweetness_ratings)

    if fav_type:
        summary_parts.append(f"You tend to rate {fav_type} wines highest")
    if fav_varietal:
        summary_parts.append(f"your favorite varietal is {fav_varietal}")
    if fav_region:
        summary_parts.append(f"and you gravitate toward {fav_region}")
    if pref_body:
        summary_parts.append(f"preferring {pref_body}-bodied wines")
    if avg_rating:
        overall = "generous" if avg_rating >= 4 else "discriminating" if avg_rating < 3.5 else "balanced"
        summary_parts.append(f"with an {overall} average of {avg_rating}/5")

    palette_summary = " · ".join(summary_parts).capitalize() if summary_parts else "Keep tasting to build your profile!"

    return {
        "has_data": True,
        "total_tastings": len(notes),
        "avg_rating": avg_rating,
        "favorite_type": fav_type,
        "favorite_varietal": fav_varietal,
        "favorite_region": fav_region,
        "preferred_body": pref_body,
        "preferred_sweetness": pref_sweetness,
        "rating_by_type": {k: avg(v) for k, v in sorted(type_ratings.items())},
        "top_wines": sorted(high_rated, key=lambda x: x["rating"], reverse=True)[:5],
        "palette_summary": palette_summary,
    }


async def get_recommendations(user_id: str, db: AsyncSession, limit: int = 5) -> list[dict]:
    """
    Recommend wines the user hasn't tasted yet, based on their profile.
    Finds wines matching their favorite type + varietal that they haven't logged.
    """
    profile = await compute_taste_profile(user_id, db)
    if not profile["has_data"]:
        return []

    fav_type = profile.get("favorite_type")
    fav_varietal = profile.get("favorite_varietal")

    if not fav_type and not fav_varietal:
        return []

    # Get wines the user has already rated
    from sqlalchemy import select
    tasted = await db.execute(
        select(TastingNote.wine_id).where(TastingNote.user_id == user_id)
    )
    tasted_ids = {row[0] for row in tasted.all()}

    # Find matching wines
    stmt = select(Wine)
    conditions = []
    if fav_type:
        conditions.append(Wine.wine_type == fav_type)
    if fav_varietal:
        conditions.append(Wine.varietal.ilike(f"%{fav_varietal}%"))

    if conditions:
        from sqlalchemy import or_
        stmt = stmt.where(or_(*conditions))

    stmt = stmt.limit(limit * 3)
    result = await db.execute(stmt)
    wines = result.scalars().all()

    # Filter out already-tasted wines
    recommendations = []
    for w in wines:
        if w.id not in tasted_ids:
            recommendations.append({
                "id": w.id,
                "producer": w.producer,
                "name": w.name,
                "vintage": w.vintage,
                "region": w.region,
                "varietal": w.varietal,
                "wine_type": w.wine_type,
                "display": w.display_name,
            })
        if len(recommendations) >= limit:
            break

    return recommendations