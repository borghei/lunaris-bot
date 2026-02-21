from datetime import date, timedelta
from unittest.mock import patch

from src.cycle import (
    get_cycle_day,
    get_phase,
    get_phase_info,
    predict_dates,
    days_until,
    get_current_cycle_start,
    PHASE_LABELS,
    PHASE_DESCRIPTIONS,
    PHASE_DETAILS,
)


# ── Helpers ──────────────────────────────────────────────────────

def _make_fake_date(today_val):
    """Create a date subclass with a controlled today() (C type can't be patched directly)."""
    class FakeDate(date):
        @classmethod
        def today(cls):
            return today_val
    return FakeDate


# ── get_cycle_day ────────────────────────────────────────────────

class TestGetCycleDay:
    def test_first_day(self):
        assert get_cycle_day(date(2026, 2, 1), date(2026, 2, 1)) == 1

    def test_mid_cycle(self):
        assert get_cycle_day(date(2026, 2, 1), date(2026, 2, 15)) == 15

    def test_last_day(self):
        assert get_cycle_day(date(2026, 2, 1), date(2026, 2, 28)) == 28

    def test_wraps_past_cycle_length(self):
        assert get_cycle_day(date(2026, 2, 1), date(2026, 3, 1)) == 1

    def test_negative_delta_returns_1(self):
        assert get_cycle_day(date(2026, 3, 1), date(2026, 2, 15)) == 1

    def test_custom_cycle_length(self):
        assert get_cycle_day(date(2026, 2, 1), date(2026, 2, 15), cycle_length=30) == 15

    def test_large_delta(self):
        # 100 days after Jan 1 = Apr 11; 100 % 28 = 16 → day 17
        assert get_cycle_day(date(2026, 1, 1), date(2026, 4, 11)) == 17


# ── get_phase ────────────────────────────────────────────────────

class TestGetPhase:
    def test_menstruation_day1(self):
        assert get_phase(1) == "menstruation"

    def test_menstruation_day5(self):
        assert get_phase(5) == "menstruation"

    def test_follicular_day6(self):
        assert get_phase(6) == "follicular"

    def test_follicular_day13(self):
        assert get_phase(13) == "follicular"

    def test_ovulation_day14(self):
        assert get_phase(14) == "ovulation"

    def test_luteal_day15(self):
        assert get_phase(15) == "luteal"

    def test_luteal_day21(self):
        assert get_phase(21) == "luteal"

    def test_pms_day22(self):
        assert get_phase(22) == "pms"

    def test_pms_day28(self):
        assert get_phase(28) == "pms"

    def test_complete_coverage(self):
        phases = {get_phase(d) for d in range(1, 29)}
        assert phases == {"menstruation", "follicular", "ovulation", "luteal", "pms"}


# ── get_phase_info ───────────────────────────────────────────────

class TestGetPhaseInfo:
    def test_correct_keys(self):
        info = get_phase_info(1)
        assert set(info.keys()) == {"cycle_day", "phase", "label", "description"}

    def test_values_match_menstruation(self):
        info = get_phase_info(1)
        assert info["phase"] == "menstruation"
        assert info["label"] == PHASE_LABELS["menstruation"]
        assert info["description"] == PHASE_DESCRIPTIONS["menstruation"]
        assert info["cycle_day"] == 1

    def test_ovulation_phase(self):
        info = get_phase_info(14)
        assert info["phase"] == "ovulation"
        assert info["label"] == PHASE_LABELS["ovulation"]

    def test_pms_phase(self):
        info = get_phase_info(25)
        assert info["phase"] == "pms"


# ── predict_dates ────────────────────────────────────────────────

class TestPredictDates:
    def test_basic_prediction(self):
        fake = _make_fake_date(date(2026, 2, 10))
        with patch("src.cycle.date", fake):
            result = predict_dates(date(2026, 2, 1), 28)
        assert result["next_period"] == date(2026, 3, 1)
        assert result["next_pms"] == date(2026, 2, 22)
        assert result["next_ovulation"] == date(2026, 2, 15)

    def test_advances_past_dates(self):
        fake = _make_fake_date(date(2026, 4, 1))
        with patch("src.cycle.date", fake):
            result = predict_dates(date(2026, 2, 1), 28)
        assert result["next_period"] > date(2026, 4, 1)

    def test_custom_cycle_length(self):
        fake = _make_fake_date(date(2026, 2, 10))
        with patch("src.cycle.date", fake):
            result = predict_dates(date(2026, 2, 1), 35)
        # Feb 1 + 35 = Mar 8
        assert result["next_period"] == date(2026, 3, 8)


# ── days_until ───────────────────────────────────────────────────

class TestDaysUntil:
    def test_future(self):
        assert days_until(date(2026, 3, 1), date(2026, 2, 21)) == 8

    def test_today(self):
        assert days_until(date(2026, 2, 21), date(2026, 2, 21)) == 0

    def test_past(self):
        assert days_until(date(2026, 2, 15), date(2026, 2, 21)) == -6


# ── get_current_cycle_start ──────────────────────────────────────

class TestGetCurrentCycleStart:
    def test_same_day(self):
        assert get_current_cycle_start(date(2026, 2, 1), date(2026, 2, 1)) == date(2026, 2, 1)

    def test_mid_cycle(self):
        assert get_current_cycle_start(date(2026, 2, 1), date(2026, 2, 15)) == date(2026, 2, 1)

    def test_second_cycle(self):
        # 30 days into a 28-day cycle → second cycle started at Feb 1 + 28 = Mar 1
        assert get_current_cycle_start(date(2026, 2, 1), date(2026, 3, 3)) == date(2026, 3, 1)

    def test_negative_delta(self):
        assert get_current_cycle_start(date(2026, 3, 1), date(2026, 2, 15)) == date(2026, 3, 1)


# ── Constants integrity ──────────────────────────────────────────

class TestConstants:
    ALL_PHASES = {"menstruation", "follicular", "ovulation", "luteal", "pms"}

    def test_phase_labels_has_all_phases(self):
        assert set(PHASE_LABELS.keys()) == self.ALL_PHASES

    def test_phase_descriptions_has_all_phases(self):
        assert set(PHASE_DESCRIPTIONS.keys()) == self.ALL_PHASES

    def test_phase_details_has_all_phases(self):
        assert set(PHASE_DETAILS.keys()) == self.ALL_PHASES
