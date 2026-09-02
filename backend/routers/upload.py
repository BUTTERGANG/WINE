"""Photo upload endpoint and save helper."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Request, UploadFile, File, HTTPException

from backend.config import settings

router = APIRouter(prefix="/api/upload", tags=["upload"])

UPLOAD_DIR = Path(settings.upload_dir)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/photo")
async def upload_photo(
    request: Request,
    file: UploadFile = File(...),
):
    """Upload a photo and return its URL."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Check content length before reading
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large")

    ext = file.filename.split(".")[-1] if file.filename else "jpg"
    filename = f"{uuid.uuid4().hex[:12]}.{ext}"
    filepath = UPLOAD_DIR / filename

    # Read in chunks to avoid memory issues
    max_size = settings.max_upload_size_mb * 1024 * 1024
    content = b""
    while True:
        chunk = await file.read(8192)
        if not chunk:
            break
        content += chunk
        if len(content) > max_size:
            raise HTTPException(status_code=400, detail="File too large")

    filepath.write_bytes(content)

    return {"url": f"/static/uploads/{filename}"}
