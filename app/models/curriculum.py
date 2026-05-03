"""Curriculum models: Unit, Lesson, Exercise."""

from typing import List

from sqlalchemy import String, Boolean, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin, TimestampMixin


class Unit(Base, UUIDMixin, TimestampMixin):
    """Curriculum unit."""
    __tablename__ = "units"
    
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    
    lessons: Mapped[List["Lesson"]] = relationship(
        "Lesson",
        back_populates="unit",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Unit {self.title}>"


class Lesson(Base, UUIDMixin, TimestampMixin):
    """Individual lesson within a unit."""
    __tablename__ = "lessons"
    
    unit_id: Mapped[str] = mapped_column(
        ForeignKey("units.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    exercise_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    difficulty: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    unit: Mapped["Unit"] = relationship(
        "Unit",
        back_populates="lessons",
        lazy="joined"
    )
    exercises: Mapped[List["Exercise"]] = relationship(
        "Exercise",
        back_populates="lesson",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="Exercise.order_index"
    )
    progress_records: Mapped[List["LessonProgress"]] = relationship(
        "LessonProgress",
        back_populates="lesson",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    
    @property
    def exercise_count(self) -> int:
        return len(self.exercises)
    
    def __repr__(self) -> str:
        return f"<Lesson {self.title}>"


class Exercise(Base, UUIDMixin, TimestampMixin):
    """Individual exercise within a lesson."""
    __tablename__ = "exercises"
    
    lesson_id: Mapped[str] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    lesson: Mapped["Lesson"] = relationship(
        "Lesson",
        back_populates="exercises",
        lazy="joined"
    )
    
    def __repr__(self) -> str:
        return f"<Exercise {self.type}>"
