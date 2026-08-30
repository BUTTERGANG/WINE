"""WINE — main application entry point."""

from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import init_db, get_db
from backend.services.auth import get_current_user


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    await init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    debug=settings.debug,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Auth check middleware on page routes (skip for /api/auth)
@app.middleware("http")
async def auth_redirect(request: Request, call_next):
    # Skip API routes and static files
    if request.url.path.startswith(("/api/auth", "/static", "/api/wines/search", "/api/feed")):
        return await call_next(request)
    
    response = await call_next(request)
    return response


# Import and register routers
from backend.routers import auth, wines, locations, community, pages

app.include_router(auth.router)
app.include_router(wines.router)
app.include_router(locations.router)
app.include_router(community.router)
app.include_router(pages.router)


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name}