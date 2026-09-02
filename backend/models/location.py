"""Location model for map pinning and winery profiles."""

import uuid
from datetime import datetime

from sqlalchemy import String, Float, Integer, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    address: Mapped[str] = mapped_column(String(500), default="")
    state_or_region: Mapped[str] = mapped_column(String(100), default="")
    country: Mapped[str] = mapped_column(String(100), default="")
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    venue_type: Mapped[str] = mapped_column(String(50), default="other", index=True)
    
    # Contact & web
    website: Mapped[str] = mapped_column(String(500), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    
    # Enrichment data from external APIs
    image_url: Mapped[str] = mapped_column(String(500), default="")
    photo_urls: Mapped[str] = mapped_column(Text, default="")  # JSON array of photo URLs
    menu_url: Mapped[str] = mapped_column(String(500), default="")
    hours: Mapped[str] = mapped_column(Text, default="")  # JSON object of opening hours
    price_level: Mapped[int] = mapped_column(Integer, nullable=True)  # 1-4 ($ to $$$$)
    google_rating: Mapped[float] = mapped_column(Float, nullable=True)
    google_review_count: Mapped[int] = mapped_column(Integer, default=0)
    google_place_id: Mapped[str] = mapped_column(String(200), default="", index=True)
    
    # Content
    description: Mapped[str] = mapped_column(Text, default="")
    amenities: Mapped[str] = mapped_column(Text, default="")  # JSON array
    
    # Timestamps
    enriched_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships - use string reference to avoid circular import
    tasting_notes = relationship(
        "backend.models.wine.TastingNote",
        back_populates="location",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Location {self.name} ({self.lat}, {self.lon})>"

    @property
    def photo_list(self) -> list[str]:
        """Parse photo_urls JSON into a list."""
        import json
        if not self.photo_urls:
            return []
        try:
            return json.loads(self.photo_urls)
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def amenity_list(self) -> list[str]:
        """Parse amenities JSON into a list."""
        import json
        if not self.amenities:
            return []
        try:
            return json.loads(self.amenities)
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def hours_dict(self) -> dict:
        """Parse hours JSON into a dict."""
        import json
        if not self.hours:
            return {}
        try:
            return json.loads(self.hours)
        except (json.JSONDecodeError, TypeError):
            return {}
