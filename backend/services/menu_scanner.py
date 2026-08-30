"""Menu scanner — OCR a wine list photo and match wines against the database."""

import re
from typing import Optional

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.wine import Wine


async def scan_menu(image_data: bytes, db: AsyncSession) -> list[dict]:
    """
    OCR a restaurant wine list and return matched wines with ratings.
    
    Uses OCR to extract text, then tries to match each line against
    the wine database by producer, name, vintage, and varietal.
    """
    # Step 1: OCR the image
    text = await _ocr_menu_image(image_data)
    if not text:
        return []

    # Step 2: Parse into wine line items
    wine_lines = _parse_wine_list(text)

    # Step 3: Match each line against the DB
    results = []
    for line in wine_lines:
        match = await _match_wine_line(line, db)
        if match:
            results.append(match)

    return results


async def _ocr_menu_image(image_data: bytes) -> Optional[str]:
    """OCR the image to extract text. Uses api4.ai OCR if key set, else placeholder."""
    from backend.config import settings
    api_key = settings.ocr_api_key

    # Try api4.ai OCR
    if api_key:
        try:
            import httpx
            import base64
            b64 = base64.b64encode(image_data).decode("utf-8")

            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    "https://api4ai.cloud/ocr/v1/results",
                    json={"image": b64},
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", [])
                    if results:
                        entities = results[0].get("entities", [])
                        for entity in entities:
                            if "text" in entity:
                                return entity["text"]
        except Exception:
            pass

    # Try Google Cloud Vision OCR
    google_key = settings.google_maps_api_key
    if google_key:
        try:
            import httpx
            import base64
            b64 = base64.b64encode(image_data).decode("utf-8")

            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    f"https://vision.googleapis.com/v1/images:annotate?key={google_key}",
                    json={
                        "requests": [{
                            "image": {"content": b64},
                            "features": [{"type": "TEXT_DETECTION"}],
                        }]
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    responses = data.get("responses", [])
                    if responses:
                        annotations = responses[0].get("textAnnotations", [])
                        if annotations:
                            return annotations[0].get("description", "")
        except Exception:
            pass

    return None


def _parse_wine_list(text: str) -> list[dict]:
    """
    Parse OCR'd text into wine line items.
    Looks for patterns like:
      - Producer Name, Wine Name, Vintage, Price
      - Wine Name (Vintage) $Price
      - Producer / Wine / Vintage
    """
    lines = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line or len(line) < 5:
            continue

        # Skip header lines
        if re.search(r'(wine|list|menu|by the glass|bottle|glass|price|vintage|producer|region)', line, re.I):
            if len(line) < 10:
                continue

        # Extract vintage (4-digit year, 1900-2025)
        vintages = re.findall(r'\b(19[0-9]{2}|20[0-2][0-9])\b', line)
        vintage = int(vintages[0]) if vintages else None

        # Extract price ($XX or $XX.XX)
        prices = re.findall(r'\$(\d+(?:\.\d{2})?)', line)
        price = float(prices[0]) if prices else None

        # Clean the wine name (remove price, vintage)
        wine_text = line
        if price:
            wine_text = wine_text.replace(f"${price}", "").replace(f"$ {price}", "")
        if vintage:
            wine_text = re.sub(r'\b' + str(vintage) + r'\b', '', wine_text)

        # Clean up whitespace
        wine_text = re.sub(r'\s+', ' ', wine_text).strip().rstrip(',')

        if wine_text and len(wine_text) > 2:
            lines.append({
                "raw": line,
                "text": wine_text,
                "vintage": vintage,
                "price": price,
            })

    return lines


async def _match_wine_line(line: dict, db: AsyncSession) -> Optional[dict]:
    """Try to match a parsed wine list line against the database."""
    text = line["text"]
    vintage = line["vintage"]

    # Try different search strategies
    keywords = text.replace("/", " ").replace(",", " ").split()
    keywords = [k for k in keywords if len(k) > 2]

    if not keywords:
        return None

    # Search by producer + name combinations
    # Try the full text as a search
    from sqlalchemy import text as sa_text

    # Build a search query
    conditions = []
    for kw in keywords[:5]:  # Use first 5 keywords
        conditions.append(Wine.producer.ilike(f"%{kw}%"))
        conditions.append(Wine.name.ilike(f"%{kw}%"))

    stmt = select(Wine).where(or_(*conditions)).limit(5)
    result = await db.execute(stmt)
    wines = result.scalars().all()

    if not wines:
        return None

    matched = []
    for wine in wines:
        score = 0
        wine_text = f"{wine.producer} {wine.name}".lower()

        for kw in keywords:
            if kw.lower() in wine_text:
                score += 1

        # Bonus for vintage match
        if vintage and wine.vintage == vintage:
            score += 2

        # Bonus for exact producer match
        for kw in keywords:
            if wine.producer.lower() == kw.lower():
                score += 3

        if score > 0:
            matched.append({
                "wine_id": wine.id,
                "producer": wine.producer,
                "name": wine.name,
                "vintage": wine.vintage,
                "region": wine.region,
                "varietal": wine.varietal,
                "wine_type": wine.wine_type,
                "display": wine.display_name,
                "score": score,
                "menu_price": line.get("price"),
                "menu_text": line["raw"],
            })

    # Sort by score, return best match
    matched.sort(key=lambda x: -x["score"])
    return matched[0] if matched else None