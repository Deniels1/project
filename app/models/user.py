"""User models: Parent and Child."""

from datetime import datetime
from typing import List

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin, TimestampMixin


class Parent(Base, UUIDMixin, TimestampMixin):
    """Parent/Guardian user account."""
    __tablename__ = "parents"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="parent", nullable=False, index=True)

    children: Mapped[List["Child"]] = relationship(
        "Child",
        back_populates="parent",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification",
        back_populates="parent",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


class Child(Base, UUIDMixin, TimestampMixin):
    """Child learner profile."""
    __tablename__ = "children"

    parent_id: Mapped[str] = mapped_column(
        ForeignKey("parents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    avatar_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    learning_level: Mapped[str | None] = mapped_column(String(50), nullable=True)

    xp_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    level_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    streak_current: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    streak_best: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    streak_last_activity_date: Mapped[str | None] = mapped_column(String(10), nullable=True)

    lessons_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accuracy_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    parent: Mapped["Parent"] = relationship(
        "Parent",
        back_populates="children",
        lazy="joined"
    )
    progress_records: Mapped[List["LessonProgress"]] = relationship(
        "LessonProgress",
        back_populates="child",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    badges: Mapped[List["Badge"]] = relationship(
        "Badge",
        back_populates="child",
        lazy="selectin",
        cascade="all, delete-orphan"
    )


class Badge(Base, UUIDMixin, TimestampMixin):
    """Achievement badge awarded to the child."""
    __tablename__ = "badges"

    child_id: Mapped[str] = mapped_column(
        ForeignKey("children.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    awarded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    child: Mapped["Child"] = relationship(
        "Child",
        back_populates="badges",
        lazy="joined"
    )


class Notification(Base, UUIDMixin, TimestampMixin):
    """Notifications persisted for parent users."""
    __tablename__ = "notifications"

    parent_id: Mapped[str] = mapped_column(
        ForeignKey("parents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    parent: Mapped["Parent"] = relationship(
        "Parent",
        back_populates="notifications",
        lazy="joined"
    )


class AuditLog(Base, UUIDMixin, TimestampMixin):
    """Admin and platform audit logs."""
    __tablename__ = "audit_logs"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("parents.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=True)

    user: Mapped["Parent"] = relationship(
        "Parent",
        back_populates="audit_logs",
        lazy="joined"
    )
