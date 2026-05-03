"""Unit tests for gamification service logic."""

from datetime import date, timedelta

import pytest

from app.services.gamification_service import GamificationService


class MockChild:
    def __init__(self, **kwargs):
        self.xp_total = kwargs.get("xp_total", 0)
        self.level_number = kwargs.get("level_number", 1)
        self.streak_current = kwargs.get("streak_current", 0)
        self.streak_best = kwargs.get("streak_best", 0)
        self.streak_last_activity_date = kwargs.get("streak_last_activity_date", None)
        self.lessons_completed = kwargs.get("lessons_completed", 0)
        self.accuracy_rate = kwargs.get("accuracy_rate", 0.0)


# ------------------------------------------------------------------ #
# XP calculation                                                        #
# ------------------------------------------------------------------ #

class TestXPCalculation:
    def test_difficulty_1_gives_100_xp(self):
        svc = GamificationService(None)
        assert svc.calculate_xp(1) == 100

    def test_difficulty_2_gives_120_xp(self):
        svc = GamificationService(None)
        assert svc.calculate_xp(2) == 120

    def test_difficulty_3_gives_140_xp(self):
        svc = GamificationService(None)
        assert svc.calculate_xp(3) == 140

    def test_difficulty_5_gives_180_xp(self):
        svc = GamificationService(None)
        assert svc.calculate_xp(5) == 180


# ------------------------------------------------------------------ #
# Level thresholds                                                      #
# ------------------------------------------------------------------ #

class TestLevelThreshold:
    def test_level_2_threshold_is_400(self):
        svc = GamificationService(None)
        assert svc.get_level_threshold(2) == 400

    def test_level_3_threshold_is_900(self):
        svc = GamificationService(None)
        assert svc.get_level_threshold(3) == 900

    def test_threshold_grows_quadratically(self):
        svc = GamificationService(None)
        assert svc.get_level_threshold(4) == 1600
        assert svc.get_level_threshold(5) == 2500


# ------------------------------------------------------------------ #
# Level-up logic                                                        #
# ------------------------------------------------------------------ #

class TestLevelUp:
    def test_no_level_up_when_insufficient_xp(self):
        svc = GamificationService(None)
        new_level, leveled = svc.check_level_up(1, 50, 40)
        assert new_level == 1
        assert leveled is False

    def test_level_up_when_xp_reaches_threshold(self):
        svc = GamificationService(None)
        new_level, leveled = svc.check_level_up(1, 0, 400)
        assert new_level == 2
        assert leveled is True

    def test_level_up_exact_threshold(self):
        svc = GamificationService(None)
        # Level 1 -> 2 requires get_level_threshold(2) = 400
        new_level, leveled = svc.check_level_up(1, 300, 100)
        assert new_level == 2
        assert leveled is True

    def test_no_level_up_one_xp_below_threshold(self):
        svc = GamificationService(None)
        new_level, leveled = svc.check_level_up(1, 0, 399)
        assert new_level == 1
        assert leveled is False


# ------------------------------------------------------------------ #
# Streak logic                                                          #
# ------------------------------------------------------------------ #

class TestStreak:
    def test_first_ever_activity_sets_streak_to_1(self):
        svc = GamificationService(None)
        child = MockChild(streak_current=0, streak_last_activity_date=None)
        new_streak, updated = svc.update_streak(child)
        assert new_streak == 1
        assert updated is True

    def test_activity_yesterday_increments_streak(self):
        svc = GamificationService(None)
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        child = MockChild(streak_current=3, streak_last_activity_date=yesterday)
        new_streak, updated = svc.update_streak(child)
        assert new_streak == 4
        assert updated is True

    def test_activity_today_does_not_change_streak(self):
        svc = GamificationService(None)
        today = date.today().isoformat()
        child = MockChild(streak_current=5, streak_last_activity_date=today)
        new_streak, updated = svc.update_streak(child)
        assert new_streak == 5
        assert updated is False

    def test_gap_resets_streak_to_1(self):
        svc = GamificationService(None)
        old = (date.today() - timedelta(days=5)).isoformat()
        child = MockChild(streak_current=10, streak_last_activity_date=old)
        new_streak, updated = svc.update_streak(child)
        assert new_streak == 1
        assert updated is True

    def test_streak_best_is_preserved_by_update_streak(self):
        """update_streak itself doesn't mutate streak_best — that's done in process_lesson_complete."""
        svc = GamificationService(None)
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        child = MockChild(streak_current=7, streak_best=7, streak_last_activity_date=yesterday)
        new_streak, _ = svc.update_streak(child)
        assert new_streak == 8  # streak_best update is caller's responsibility


# ------------------------------------------------------------------ #
# Badge definitions                                                     #
# ------------------------------------------------------------------ #

class TestBadgeConditions:
    def test_first_lesson_badge_condition(self):
        svc = GamificationService(None)
        child_yes = MockChild(lessons_completed=1)
        child_no = MockChild(lessons_completed=0)
        definition = {k: v for *_, k, v in [(d[0], d[3]) for d in svc.BADGE_DEFINITIONS]}
        first = next(fn for key, _, __, fn in svc.BADGE_DEFINITIONS if key == "first_lesson")
        assert first(child_yes) is True
        assert first(child_no) is False

    def test_xp_100_badge_condition(self):
        svc = GamificationService(None)
        fn = next(fn for key, _, __, fn in svc.BADGE_DEFINITIONS if key == "xp_100")
        assert fn(MockChild(xp_total=100)) is True
        assert fn(MockChild(xp_total=99)) is False

    def test_streak_7_badge_condition(self):
        svc = GamificationService(None)
        fn = next(fn for key, _, __, fn in svc.BADGE_DEFINITIONS if key == "streak_7")
        assert fn(MockChild(streak_current=7)) is True
        assert fn(MockChild(streak_current=6)) is False
