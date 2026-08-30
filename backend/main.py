"""WINE — main application entry point."""

from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup, and seed demo data if empty."""
    await init_db()
    if settings.auto_seed:
        try:
            from scripts.seed import seed
            await seed()
        except Exception as exc:  # pragma: no cover — seeding is best-effort
            print(f"[startup] auto-seed skipped: {exc}")
    yield


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    debug=settings.debug,
)

# Static files
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Uploaded files
uploads_dir = Path(settings.upload_dir)
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


# Import and register routers
from backend.routers import auth, wines, locations, community, pages, upload

app.include_router(auth.router)
app.include_router(wines.router)
app.include_router(locations.router)
app.include_router(community.router)
app.include_router(pages.router)
app.include_router(upload.router)


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name}
