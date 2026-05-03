"""Initial schema: parents, children, curriculum, progress, gamification

Revision ID: 001_initial
Revises: 
Create Date: 2026-05-03 00:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Parents table
    op.create_table(
        "parents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="parent"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_parents_email", "parents", ["email"], unique=True)
    op.create_index("ix_parents_role", "parents", ["role"])

    # Children table
    op.create_table(
        "children",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("parents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("age", sa.Integer, nullable=False),
        sa.Column("avatar_url", sa.String(255), nullable=True),
        sa.Column("learning_level", sa.String(50), nullable=True),
        sa.Column("xp_total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("level_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("streak_current", sa.Integer, nullable=False, server_default="0"),
        sa.Column("streak_best", sa.Integer, nullable=False, server_default="0"),
        sa.Column("streak_last_activity_date", sa.String(10), nullable=True),
        sa.Column("lessons_completed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("accuracy_rate", sa.Float, nullable=False, server_default="0"),
        sa.Column("last_activity_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_children_parent_id", "children", ["parent_id"])
    op.create_index("ix_children_age", "children", ["age"])
    op.create_index("ix_children_xp_total", "children", ["xp_total"])

    # Units table
    op.create_table(
        "units",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("order_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("published", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_units_title", "units", ["title"])
    op.create_index("ix_units_published", "units", ["published"])

    # Lessons table
    op.create_table(
        "lessons",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("unit_id", sa.String(36), sa.ForeignKey("units.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("exercise_type", sa.String(50), nullable=False),
        sa.Column("order_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("published", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("difficulty", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_lessons_unit_id", "lessons", ["unit_id"])
    op.create_index("ix_lessons_published", "lessons", ["published"])
    op.create_index("ix_lessons_exercise_type", "lessons", ["exercise_type"])

    # Exercises table
    op.create_table(
        "exercises",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("lesson_id", sa.String(36), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("order_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("difficulty", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_exercises_lesson_id", "exercises", ["lesson_id"])
    op.create_index("ix_exercises_type", "exercises", ["type"])

    # Lesson progress table
    op.create_table(
        "lesson_progress",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("child_id", sa.String(36), sa.ForeignKey("children.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_id", sa.String(36), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("completed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("correct_answers", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_questions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("score", sa.Float, nullable=False, server_default="0"),
        sa.Column("duration_seconds", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_lesson_progress_child_id", "lesson_progress", ["child_id"])
    op.create_index("ix_lesson_progress_lesson_id", "lesson_progress", ["lesson_id"])

    # Badges table
    op.create_table(
        "badges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("child_id", sa.String(36), sa.ForeignKey("children.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("awarded_at", sa.DateTime, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_badges_child_id", "badges", ["child_id"])
    op.create_index("ix_badges_name", "badges", ["name"])

    # Notifications table
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("parents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("sent_at", sa.DateTime, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_notifications_parent_id", "notifications", ["parent_id"])
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])

    # Audit logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("parents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource", sa.String(100), nullable=False),
        sa.Column("details", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("notifications")
    op.drop_table("badges")
    op.drop_table("lesson_progress")
    op.drop_table("exercises")
    op.drop_table("lessons")
    op.drop_table("units")
    op.drop_table("children")
    op.drop_table("parents")
