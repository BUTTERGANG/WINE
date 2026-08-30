"""Wine and TastingNote models."""

import uuid
from datetime import datetime

from sqlalchemy import String, Float, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Wine(Base):
    __tablename__ = "wines"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    producer: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    vintage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    region: Mapped[str] = mapped_column(String(200), default="")
    country: Mapped[str] = mapped_column(String(100), default="")
    varietal: Mapped[str] = mapped_column(String(100), default="")  # e.g. Cabernet Sauvignon
    wine_type: Mapped[str] = mapped_column(String(50), default="red")  # red, white, rosé, sparkling, fortified, dessert
    abv: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    tasting_notes = relationship("TastingNote", back_populates="wine", lazy="select")

    @property
    def avg_rating(self) -> float | None:
        if not self.tasting_notes:
            return None
        ratings = [tn.rating for tn in self.tasting_notes if tn.rating]
        return round(sum(ratings) / len(ratings), 1) if ratings else None

    @property
    def display_name(self) -> str:
        if self.vintage:
            return f"{self.producer} {self.name} ({self.vintage})"
        return f"{self.producer} {self.name}"

    def __repr__(self) -> str:
        return f"<Wine {self.producer} {self.name}>"


class TastingNote(Base):
    __tablename__ = "tasting_notes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    wine_id: Mapped[str] = mapped_column(String, ForeignKey("wines.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    location_id: Mapped[str | None] = mapped_column(String, ForeignKey("locations.id"), nullable=True)

    # Rating
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5

    # Structured tasting (WSET-inspired)
    appearance: Mapped[str] = mapped_column(Text, default="")
    nose: Mapped[str] = mapped_column(Text, default="")
    palate: Mapped[str] = mapped_column(Text, default="")
    finish: Mapped[str] = mapped_column(Text, default="")

    # Optional fields
    body: Mapped[str] = mapped_column(String(20), default="")  # light, medium, full
    sweetness: Mapped[str] = mapped_column(String(20), default="")  # dry, off-dry, medium, sweet
    acidity: Mapped[str] = mapped_column(String(20), default="")  # low, medium, high
    tannins: Mapped[str] = mapped_column(String(20), default="")  # low, medium, high (reds)
    food_pairing: Mapped[str] = mapped_column(String(200), default="")
    price_paid: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    photo_url: Mapped[str] = mapped_column(String(500), default="")
    is_public: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    wine = relationship("Wine", back_populates="tasting_notes", lazy="joined")
    user = relationship("User", back_populates="tasting_notes", lazy="joined")
    location = relationship("Location", back_populates="tasting_notes", lazy="joined")

    def __repr__(self) -> str:
        return f"<TastingNote {self.wine_id} by {self.user_id} — {self.rating}/5>"