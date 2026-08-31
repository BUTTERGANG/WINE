"""WINE application configuration."""

from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from pydantic import model_validator
from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def _normalize_db_url(url: str) -> tuple[str, bool]:
    """Coerce a plain ``postgresql://`` URL into an async-capable one.

    Replit provisions ``DATABASE_URL`` as a sync ``postgresql://…?sslmode=…``
    string. SQLAlchemy's async engine needs the ``+asyncpg`` driver, and asyncpg
    rejects the libpq-style ``sslmode`` query arg, so strip it — but remember
    whether it asked for SSL so the engine can pass ``connect_args={"ssl": True}``.

    Returns ``(normalized_url, require_ssl)``.
    """
    if not url:
        return url, False

    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]

    require_ssl = False
    if url.startswith("postgresql+asyncpg://"):
        parts = urlsplit(url)
        kept = []
        for k, v in parse_qsl(parts.query):
            if k == "sslmode":
                require_ssl = v.lower() in {"require", "verify-ca", "verify-full", "prefer"}
                continue
            kept.append((k, v))
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), parts.fragment))

    return url, require_ssl


class Settings(BaseSettings):
    app_name: str = "WINE"
    debug: bool = True
    secret_key: str = "change-me-in-production-wine-app-2026"

    # Database — defaults to local SQLite; DATABASE_URL env overrides.
    database_url: str = f"sqlite+aiosqlite:///{DATA_DIR}/wine.db"
    db_echo: bool = False  # log every SQL statement (very noisy)
    db_require_ssl: bool = False  # derived from a postgres ?sslmode= arg

    # Port the web server binds (Replit forwards 5000 to the public webview).
    port: int = 5000

    # Auto-seed demo data on startup when the DB is empty.
    auto_seed: bool = True

    # External APIs
    wine_db_api_key: str = ""
    ocr_api_key: str = ""
    google_maps_api_key: str = ""

    # Map tile URL (default: OpenStreetMap free tier)
    map_tile_url: str = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"

    # Uploads
    upload_dir: str = str(BASE_DIR / "backend" / "uploads")
    max_upload_size_mb: int = 10

    # Session
    session_ttl_hours: int = 24

    @model_validator(mode="after")
    def _fix_db_url(self):
        self.database_url, self.db_require_ssl = _normalize_db_url(self.database_url)
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Ensure the SQLite directory exists before the engine opens the file.
if settings.database_url.startswith("sqlite"):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
