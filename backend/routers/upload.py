"""Photo upload endpoint and save helper."""

import io
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Request, UploadFile, File, HTTPException
from PIL import Image, UnidentifiedImageError

from backend.config import settings

router = APIRouter(prefix="/api/upload", tags=["upload"])

UPLOAD_DIR = Path(settings.upload_dir)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Map Pillow's detected format to a safe, fixed extension. Anything not in
# this list is rejected, regardless of what the client claimed.
_ALLOWED_FORMATS = {
    "JPEG": "jpg",
    "PNG": "png",
    "GIF": "gif",
    "WEBP": "webp",
}


@router.post("/photo")
async def upload_photo(
    request: Request,
    file: UploadFile = File(...),
):
    """Upload a photo and return its URL."""
    # Check content length before reading
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large")

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

    # Validate the actual file bytes, not the client-supplied Content-Type
    # or filename — both are trivially spoofable.
    try:
        with Image.open(io.BytesIO(content)) as img:
            img.verify()
        with Image.open(io.BytesIO(content)) as img:
            image_format = img.format
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="File must be a valid image")

    ext = _ALLOWED_FORMATS.get(image_format)
    if not ext:
        raise HTTPException(status_code=400, detail="Unsupported image format")

    # Server-generated filename only — never use the client-supplied name.
    filename = f"{uuid.uuid4().hex[:12]}.{ext}"
    filepath = UPLOAD_DIR / filename
    filepath.write_bytes(content)

    return {"url": f"/static/uploads/{filename}"}
