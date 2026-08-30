"""Menu scan routes — upload a wine list photo, get matched wines with ratings."""

from fastapi import APIRouter, Depends, Request, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.services.auth import get_current_user
from backend.services.menu_scanner import scan_menu
from backend.services.template import templates

router = APIRouter(prefix="/api/menu", tags=["menu"])


@router.post("/scan")
async def scan_wine_list(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a wine list photo and get matched wines with ratings."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    image_data = await file.read()
    if len(image_data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    matches = await scan_menu(image_data, db)

    return JSONResponse({"matches": matches})


@router.get("/scan", response_class=HTMLResponse)
async def scan_menu_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Menu scan page."""
    user = await get_current_user(request, db)
    return templates.TemplateResponse("wine/menu_scan.html", {"request": request, "user": user})