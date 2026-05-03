"""
Gamification service.

All business logic for XP, streaks, levels, badges, and lesson completion
lives here. Controllers must NOT contain this logic.
"""

from datetime import datetime, timedelta, date
from typing import List, Tuple, Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Badge, Child, Notification
from app.db.app.models.progress import LessonProgress


class GamificationService:
    """Service for XP, streaks, level calculation, badges, and lesson completion."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------ #
    # XP & Levels                                                          #
    # ------------------------------------------------------------------ #

    def calculate_xp(self, lesson_difficulty: int) -> int:
        """
        Calculate XP for lesson completion.
        Formula: 100 + (difficulty - 1) * 20
        """
        BASE_XP = 100
        DIFFICULTY_BONUS = 20
        return BASE_XP + (lesson_difficulty - 1) * DIFFICULTY_BONUS

    def get_level_threshold(self, level: int) -> int:
        """
        XP needed to reach *level*.
        Formula: level * level * 100
          Level 2: 400 XP  |  Level 3: 900 XP
        """
        return level * level * 100

    def check_level_up(
        self, current_level: int, current_xp: int, xp_to_add: int
    ) -> Tuple[int, bool]:
        """Return (new_level, leveled_up) after adding XP."""
        total_xp = current_xp + xp_to_add
        threshold = self.get_level_threshold(current_level + 1)
        if total_xp >= threshold:
            return current_level + 1, True
        return current_level, False

    # ------------------------------------------------------------------ #
    # Streaks                                                              #
    # ------------------------------------------------------------------ #

    def update_streak(self, child: Child) -> Tuple[int, bool]:
        """
        Update child's streak based on activity date.
        Returns (new_streak, was_updated).
        """
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        if child.streak_last_activity_date == today:
            return child.streak_current, False          # already counted today

        if child.streak_last_activity_date == yesterday:
            return child.streak_current + 1, True       # consecutive day

        return 1, True                                   # first or broken streak

    # ------------------------------------------------------------------ #
    # Lesson completion (core business logic)                              #
    # ------------------------------------------------------------------ #

    async def process_lesson_complete(
        self,
        child: Child,
        lesson_id: str,
        lesson_difficulty: int,
        correct: int,
        total: int,
        duration_seconds: int,
    ) -> Dict[str, Any]:
        """
        Full lesson completion flow:
          1. Upsert LessonProgress record
          2. Award XP and check level-up
          3. Update streak
          4. Update accuracy
          5. Flush changes (caller commits)

        Returns a summary dict for the API response.
        """
        # 1. Upsert progress record
        result = await self.db.execute(
            select(LessonProgress).where(
                LessonProgress.child_id == child.id,
                LessonProgress.lesson_id == lesson_id,
            )
        )
        progress = result.scalar_one_or_none()
        score = round((correct / total) * 100.0, 2) if total > 0 else 0.0

        if progress is None:
            progress = LessonProgress(
                child_id=child.id,
                lesson_id=lesson_id,
                completed=True,
                correct_answers=correct,
                total_questions=total,
                score=score,
                duration_seconds=duration_seconds,
                completed_at=datetime.utcnow(),
            )
            self.db.add(progress)
        else:
            progress.completed = True
            progress.correct_answers = correct
            progress.total_questions = total
            progress.score = score
            progress.duration_seconds = duration_seconds
            progress.completed_at = datetime.utcnow()

        # 2. XP & level
        xp = self.calculate_xp(lesson_difficulty)
        xp_before = child.xp_total
        child.xp_total += xp
        child.lessons_completed += 1
        child.last_activity_at = datetime.utcnow()

        new_level, leveled_up = self.check_level_up(child.level_number, xp_before, xp)
        child.level_number = new_level

        # 3. Streak
        new_streak, streak_updated = self.update_streak(child)
        child.streak_current = new_streak
        child.streak_last_activity_date = date.today().isoformat()
        if new_streak > child.streak_best:
            child.streak_best = new_streak

        # 4. Accuracy
        if total > 0:
            child.accuracy_rate = round((correct / total) * 100, 2)

        await self.db.flush()
        await self.db.refresh(child)

        return {
            "xp_earned": xp,
            "total_xp": child.xp_total,
            "new_level": new_level,
            "level_up": leveled_up,
            "new_streak": new_streak,
            "streak_updated": streak_updated,
            "score": score,
        }

    # ------------------------------------------------------------------ #
    # Badges                                                               #
    # ------------------------------------------------------------------ #

    BADGE_DEFINITIONS = [
        ("first_lesson",  "First Lesson",    "Completed the first lesson",       lambda c: c.lessons_completed >= 1),
        ("xp_100",        "100 XP Earned",   "Earned 100 XP",                    lambda c: c.xp_total >= 100),
        ("xp_500",        "500 XP Earned",   "Earned 500 XP",                    lambda c: c.xp_total >= 500),
        ("streak_3",      "3-Day Streak",    "Maintained a 3-day streak",        lambda c: c.streak_current >= 3),
        ("streak_7",      "7-Day Streak",    "Maintained a 7-day streak",        lambda c: c.streak_current >= 7),
        ("lessons_5",     "5 Lessons",       "Completed 5 lessons",              lambda c: c.lessons_completed >= 5),
        ("lessons_10",    "10 Lessons",      "Completed 10 lessons",             lambda c: c.lessons_completed >= 10),
    ]

    async def award_badges(self, child: Child) -> List[Badge]:
        """
        Check badge conditions and award any not yet earned.
        Returns list of newly awarded badges.
        """
        existing_result = await self.db.execute(
            select(Badge.name).where(Badge.child_id == child.id)
        )
        earned = {row[0] for row in existing_result.all()}

        new_badges: List[Badge] = []
        for key, title, description, condition in self.BADGE_DEFINITIONS:
            if key not in earned and condition(child):
                badge = Badge(child_id=child.id, name=key, description=description)
                self.db.add(badge)
                await self.db.flush()
                await self.db.refresh(badge)
                new_badges.append(badge)

        if new_badges:
            await self.db.flush()

        return new_badges

    # ------------------------------------------------------------------ #
    # Notifications                                                        #
    # ------------------------------------------------------------------ #

    async def create_notification(
        self, parent_id: str, title: str, message: str
    ) -> Notification:
        """Persist a notification for the parent."""
        notification = Notification(parent_id=parent_id, title=title, message=message)
        self.db.add(notification)
        await self.db.flush()
        await self.db.refresh(notification)
        return notification
