"""WINE application configuration."""

from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "WINE"
    debug: bool = True
    secret_key: str = "change-me-in-production-wine-app-2026"

    # Database
    database_url: str = f"sqlite+aiosqlite:///{BASE_DIR}/data/wine.db"

    # External APIs
    wine_db_api_key: str = ""
    ocr_api_key: str = ""

    # Map tile URL (default: OpenStreetMap free tier)
    map_tile_url: str = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"

    # Uploads
    upload_dir: str = str(BASE_DIR / "backend" / "uploads")
    max_upload_size_mb: int = 10

    # Session
    session_ttl_hours: int = 24

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()