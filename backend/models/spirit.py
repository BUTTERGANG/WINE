"""Spirit and Distillery models for the Spirits category."""

import uuid
from datetime import datetime

from sqlalchemy import String, Float, Integer, Text, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Spirit(Base):
    """A whiskey, bourbon, scotch, or other spirit expression."""

    __tablename__ = "spirits"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    producer: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    age_statement: Mapped[str] = mapped_column(String(50), default="")  # e.g. "12", "18", "NAS"
    region: Mapped[str] = mapped_column(String(200), default="")
    country: Mapped[str] = mapped_column(String(100), default="")
    spirit_type: Mapped[str] = mapped_column(String(50), default="whiskey")  # whiskey, bourbon, scotch, rye, irish, japanese, etc.
    abv: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    cask_type: Mapped[str] = mapped_column(String(100), default="")  # ex-bourbon, sherry, port, etc.
    image_url: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    tasting_notes = relationship("SpiritTastingNote", back_populates="spirit", lazy="select")
    wishlist_entries = relationship("SpiritWishlistEntry", back_populates="spirit", lazy="select")

    @property
    def avg_rating(self) -> float | None:
        if not self.tasting_notes:
            return None
        ratings = [tn.rating for tn in self.tasting_notes if tn.rating]
        return round(sum(ratings) / len(ratings), 1) if ratings else None

    @property
    def display_name(self) -> str:
        parts = [p for p in (self.producer, self.name) if p]
        base = " ".join(parts) or "Unnamed spirit"
        if self.age_statement:
            return f"{base} ({self.age_statement} yr)"
        return base

    def __repr__(self) -> str:
        return f"<Spirit {self.producer} {self.name}>"


class SpiritTastingNote(Base):
    """A tasting note for a spirit."""

    __tablename__ = "spirit_tasting_notes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    spirit_id: Mapped[str] = mapped_column(String, ForeignKey("spirits.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    distillery_id: Mapped[str | None] = mapped_column(String, ForeignKey("distilleries.id"), nullable=True)

    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5

    # Tasting notes
    nose: Mapped[str] = mapped_column(Text, default="")
    palate: Mapped[str] = mapped_column(Text, default="")
    finish: Mapped[str] = mapped_column(Text, default="")

    body: Mapped[str] = mapped_column(String(20), default="")  # light, medium, full
    sweetness: Mapped[str] = mapped_column(String(20), default="")  # dry, off-dry, sweet
    peat: Mapped[str] = mapped_column(String(20), default="")  # none, light, medium, heavy

    notes: Mapped[str] = mapped_column(Text, default="")
    photo_url: Mapped[str] = mapped_column(String(500), default="")
    price_paid: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_public: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    spirit = relationship("Spirit", back_populates="tasting_notes", lazy="joined")
    user = relationship("User", back_populates="spirit_tasting_notes", lazy="joined")
    distillery = relationship("Distillery", back_populates="tasting_notes", lazy="joined")

    def __repr__(self) -> str:
        return f"<SpiritTastingNote {self.spirit_id} by {self.user_id} — {self.rating}/5>"


class Distillery(Base):
    """A distillery — whiskey, bourbon, scotch, gin, vodka, etc."""

    __tablename__ = "distilleries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    address: Mapped[str] = mapped_column(String(500), default="")
    state_or_region: Mapped[str] = mapped_column(String(100), default="", index=True)
    country: Mapped[str] = mapped_column(String(100), default="")
    lat: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    lon: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    venue_type: Mapped[str] = mapped_column(String(50), default="distillery")
    website: Mapped[str] = mapped_column(String(500), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    founded_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    spirit_types: Mapped[str] = mapped_column(String(200), default="")  # comma-separated
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    tasting_notes = relationship("SpiritTastingNote", back_populates="distillery", lazy="select")

    def __repr__(self) -> str:
        return f"<Distillery {self.name}>"


class SpiritWishlistEntry(Base):
    """A spirit a user wants to try."""

    __tablename__ = "spirit_wishlist_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    spirit_id: Mapped[str] = mapped_column(String, ForeignKey("spirits.id"), nullable=False, index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "spirit_id", name="uq_spirit_wishlist"),)

    spirit = relationship("Spirit", back_populates="wishlist_entries", lazy="joined")
    user = relationship("User", lazy="joined")

    def __repr__(self) -> str:
        return f"<SpiritWishlistEntry {self.spirit_id} by {self.user_id}>"