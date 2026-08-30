"""Community models: follows and groups."""

import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Follow(Base):
    __tablename__ = "follows"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    follower_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    followed_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("follower_id", "followed_id", name="uq_follow"),)

    follower = relationship("User", foreign_keys=[follower_id], back_populates="followed", lazy="joined")
    followed_user = relationship("User", foreign_keys=[followed_id], back_populates="followers_rel", lazy="joined")


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="")
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class GroupMember(Base):
    __tablename__ = "group_members"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    group_id: Mapped[str] = mapped_column(String, ForeignKey("groups.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), default="member")  # owner, admin, member
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_group_member"),)