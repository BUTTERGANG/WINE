"""User model for auth and profiles."""

import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), default="")
    bio: Mapped[str] = mapped_column(String(500), default="")
    avatar_url: Mapped[str] = mapped_column(String(500), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)  # public profile/tastings
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    tasting_notes = relationship("TastingNote", back_populates="user", lazy="select")
    followed = relationship(
        "Follow",
        foreign_keys="Follow.follower_id",
        back_populates="follower",
        lazy="select",
    )
    followers_rel = relationship(
        "Follow",
        foreign_keys="Follow.followed_id",
        back_populates="followed_user",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<User {self.username}>"