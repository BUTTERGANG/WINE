"""WINE — main application entry point."""

from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import init_db, get_db


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
from backend.routers import auth, wines, locations, community, pages, upload, wineries, menu

app.include_router(auth.router)
app.include_router(wines.router)
app.include_router(locations.router)
app.include_router(community.router)
app.include_router(pages.router)
app.include_router(upload.router)
app.include_router(wineries.router)
app.include_router(menu.router)


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name}


@app.get("/api/stats")
async def live_stats(db: AsyncSession = Depends(get_db)):
    """Live stats for the home page — HTMX-polled every 30s."""
    from sqlalchemy import select, func
    from backend.models.wine import Wine, TastingNote
    from backend.models.user import User
    from backend.models.location import Location
    wine_count = (await db.execute(select(func.count()).select_from(Wine))).scalar() or 0
    tasting_count = (await db.execute(select(func.count()).select_from(TastingNote))).scalar() or 0
    user_count = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    winery_count = (await db.execute(select(func.count()).select_from(Location).where(Location.venue_type == "winery"))).scalar() or 0
    from fastapi.responses import HTMLResponse
    html = f"""<div class="grid grid-cols-4 gap-3 max-w-2xl mx-auto mb-10 text-center" id="live-stats">
        <div class="bg-neutral-900 rounded-xl p-4 border border-neutral-800"><div class="text-2xl md:text-3xl font-display text-wine-400">{wine_count}</div><div class="text-xs text-neutral-400 uppercase tracking-[0.15em] mt-0.5">Wines</div></div>
        <div class="bg-neutral-900 rounded-xl p-4 border border-neutral-800"><div class="text-2xl md:text-3xl font-display text-wine-400">{tasting_count}</div><div class="text-xs text-neutral-400 uppercase tracking-[0.15em] mt-0.5">Tastings</div></div>
        <div class="bg-neutral-900 rounded-xl p-4 border border-neutral-800"><div class="text-2xl md:text-3xl font-display text-wine-400">{winery_count}</div><div class="text-xs text-neutral-400 uppercase tracking-[0.15em] mt-0.5">Wineries</div></div>
        <div class="bg-neutral-900 rounded-xl p-4 border border-neutral-800"><div class="text-2xl md:text-3xl font-display text-wine-400">{user_count}</div><div class="text-xs text-neutral-400 uppercase tracking-[0.15em] mt-0.5">Drinkers</div></div>
    </div>"""
    return HTMLResponse(html)
