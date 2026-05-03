from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin, TimestampMixin


class LessonProgress(Base, UUIDMixin, TimestampMixin):
    """Таблица, которая связывает ребенка и пройденный урок."""
    __tablename__ = "lesson_progress"

    child_id: Mapped[str] = mapped_column(ForeignKey("children.id", ondelete="CASCADE"), index=True)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)

    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    correct_answers: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    child = relationship("Child", back_populates="progress_records")
    lesson = relationship("Lesson", back_populates="progress_records")
