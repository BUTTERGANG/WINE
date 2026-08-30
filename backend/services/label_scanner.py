"""Label scanner — OCR + wine matching."""

import io
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wine_db import search_local_wines


async def scan_label(image_data: bytes, db: AsyncSession) -> list[dict]:
    """
    Scan a bottle label photo and return candidate wine matches.
    
    Uses OCR to extract text from the label, then searches the wine DB.
    Falls back gracefully if no OCR API is configured.
    """
    # Try OCR via api4.ai wine recognition first
    candidates = []
    
    # Attempt external OCR
    text_extracted = await _ocr_image(image_data)
    
    if text_extracted:
        # Search DB with extracted text
        results = await search_local_wines(db, text_extracted, limit=5)
        for wine in results:
            candidates.append({
                "wine_id": wine.id,
                "producer": wine.producer,
                "name": wine.name,
                "vintage": wine.vintage,
                "region": wine.region,
                "varietal": wine.varietal,
                "wine_type": wine.wine_type,
                "display": wine.display_name,
                "confidence": 0.85,  # Placeholder — real OCR returns confidence
            })
    
    # If OCR found nothing, return empty
    return candidates


async def _ocr_image(image_data: bytes) -> Optional[str]:
    """
    OCR the label image. Uses api4.ai's wine recognition API if key is set,
    otherwise returns None (user must search manually).
    """
    from backend.config import settings
    
    api_key = settings.ocr_api_key
    if not api_key:
        return None
    
    # api4.ai wine recognition API
    try:
        import httpx
        
        import base64
        b64 = base64.b64encode(image_data).decode("utf-8")
        
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api4ai.cloud/wine-rec/v1/results",
                json={"image": b64},
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                # Extract wine name / producer from results
                results = data.get("results", [])
                if results:
                    entities = results[0].get("entities", [])
                    for entity in entities:
                        classes = entity.get("classes", {})
                        if classes:
                            # Highest confidence class
                            best = max(classes, key=classes.get)
                            if classes[best] > 0.3:
                                return best
    except Exception:
        pass
    
    return None