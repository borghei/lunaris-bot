from datetime import date, timedelta
from unittest.mock import patch

from src.cycle import (
    get_cycle_day,
    get_phase,
    get_phase_info,
    get_phase_detail,
    predict_dates,
    days_until,
    get_current_cycle_start,
    PHASE_LABELS,
    PHASE_DESCRIPTIONS,
    PHASE_DETAILS,
)


# -- Helpers --

def _make_fake_date(today_val):
    """Create a date subclass with a controlled today() (C type can't be patched directly)."""
    class FakeDate(date):
        @classmethod
        def today(cls):
            return today_val
    return FakeDate


# -- get_cycle_day --

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
        # 100 days after Jan 1 = Apr 11; 100 % 28 = 16 -> day 17
        assert get_cycle_day(date(2026, 1, 1), date(2026, 4, 11)) == 17


# -- get_phase --

class TestGetPhase:
    """Default 28-day cycle, 5-day period."""

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


class TestGetPhaseProportional:
    """Proportional phase boundaries for non-default cycles."""

    def test_35_day_cycle_ovulation(self):
        # ovulation_day = 35 - 14 = 21
        assert get_phase(21, cycle_length=35) == "ovulation"

    def test_35_day_cycle_menstruation(self):
        assert get_phase(1, cycle_length=35) == "menstruation"
        assert get_phase(5, cycle_length=35) == "menstruation"

    def test_35_day_cycle_follicular(self):
        assert get_phase(6, cycle_length=35) == "follicular"
        assert get_phase(20, cycle_length=35) == "follicular"

    def test_35_day_cycle_luteal(self):
        assert get_phase(22, cycle_length=35) == "luteal"
        assert get_phase(28, cycle_length=35) == "luteal"

    def test_35_day_cycle_pms(self):
        # pms_start = 35 - 6 = 29
        assert get_phase(29, cycle_length=35) == "pms"
        assert get_phase(35, cycle_length=35) == "pms"

    def test_21_day_cycle_ovulation(self):
        # ovulation_day = 21 - 14 = 7
        assert get_phase(7, cycle_length=21) == "ovulation"

    def test_21_day_cycle_follicular(self):
        assert get_phase(6, cycle_length=21) == "follicular"

    def test_21_day_cycle_pms(self):
        # pms_start = 21 - 6 = 15
        assert get_phase(15, cycle_length=21) == "pms"
        assert get_phase(21, cycle_length=21) == "pms"

    def test_custom_period_duration_3(self):
        # period_duration=3: menstruation 1-3, follicular 4-13, ovulation 14
        assert get_phase(3, period_duration=3) == "menstruation"
        assert get_phase(4, period_duration=3) == "follicular"

    def test_custom_period_duration_7(self):
        # period_duration=7: menstruation 1-7, follicular 8-13, ovulation 14
        assert get_phase(7, period_duration=7) == "menstruation"
        assert get_phase(8, period_duration=7) == "follicular"

    def test_short_cycle_ovulation_clamped(self):
        # cycle_length=20, period_duration=5: ovulation_day = max(20-14, 6) = 6
        assert get_phase(6, cycle_length=20, period_duration=5) == "ovulation"
        assert get_phase(5, cycle_length=20, period_duration=5) == "menstruation"

    def test_all_phases_covered_35_day(self):
        phases = {get_phase(d, cycle_length=35) for d in range(1, 36)}
        assert phases == {"menstruation", "follicular", "ovulation", "luteal", "pms"}


# -- get_phase_info --

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

    def test_proportional_35_day(self):
        # Day 21 on 35-day cycle = ovulation
        info = get_phase_info(21, cycle_length=35)
        assert info["phase"] == "ovulation"

    def test_with_period_duration(self):
        info = get_phase_info(3, period_duration=3)
        assert info["phase"] == "menstruation"
        info = get_phase_info(4, period_duration=3)
        assert info["phase"] == "follicular"


# -- get_phase_detail --

class TestGetPhaseDetail:
    def test_default_boundaries(self):
        detail = get_phase_detail("menstruation")
        assert "Day 1-5" in detail

    def test_default_ovulation(self):
        detail = get_phase_detail("ovulation")
        assert "Day 14" in detail

    def test_default_pms(self):
        detail = get_phase_detail("pms")
        assert "Day 22-28" in detail

    def test_35_day_cycle_ovulation(self):
        detail = get_phase_detail("ovulation", cycle_length=35)
        assert "Day 21" in detail

    def test_35_day_cycle_pms(self):
        detail = get_phase_detail("pms", cycle_length=35)
        assert "Day 29-35" in detail

    def test_custom_period_duration(self):
        detail = get_phase_detail("menstruation", period_duration=3)
        assert "Day 1-3" in detail

    def test_all_phases_return_nonempty(self):
        for phase in PHASE_LABELS:
            detail = get_phase_detail(phase)
            assert len(detail) > 0


# -- predict_dates --

class TestPredictDates:
    def test_basic_prediction(self):
        fake = _make_fake_date(date(2026, 2, 10))
        with patch("src.cycle.date", fake):
            result = predict_dates(date(2026, 2, 1), 28)
        assert result["next_period"] == date(2026, 3, 1)
        assert result["next_pms"] == date(2026, 2, 22)
        # Ovulation: Feb 1 + (28 - 15) = Feb 1 + 13 = Feb 14
        assert result["next_ovulation"] == date(2026, 2, 14)

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

    def test_35_day_ovulation(self):
        fake = _make_fake_date(date(2026, 2, 10))
        with patch("src.cycle.date", fake):
            result = predict_dates(date(2026, 2, 1), 35)
        # Ovulation: Feb 1 + (35 - 15) = Feb 1 + 20 = Feb 21
        assert result["next_ovulation"] == date(2026, 2, 21)


# -- days_until --

class TestDaysUntil:
    def test_future(self):
        assert days_until(date(2026, 3, 1), date(2026, 2, 21)) == 8

    def test_today(self):
        assert days_until(date(2026, 2, 21), date(2026, 2, 21)) == 0

    def test_past(self):
        assert days_until(date(2026, 2, 15), date(2026, 2, 21)) == -6


# -- get_current_cycle_start --

class TestGetCurrentCycleStart:
    def test_same_day(self):
        assert get_current_cycle_start(date(2026, 2, 1), date(2026, 2, 1)) == date(2026, 2, 1)

    def test_mid_cycle(self):
        assert get_current_cycle_start(date(2026, 2, 1), date(2026, 2, 15)) == date(2026, 2, 1)

    def test_second_cycle(self):
        # 30 days into a 28-day cycle -> second cycle started at Feb 1 + 28 = Mar 1
        assert get_current_cycle_start(date(2026, 2, 1), date(2026, 3, 3)) == date(2026, 3, 1)

    def test_negative_delta(self):
        assert get_current_cycle_start(date(2026, 3, 1), date(2026, 2, 15)) == date(2026, 3, 1)


# -- Constants integrity --

class TestConstants:
    ALL_PHASES = {"menstruation", "follicular", "ovulation", "luteal", "pms"}

    def test_phase_labels_has_all_phases(self):
        assert set(PHASE_LABELS.keys()) == self.ALL_PHASES

    def test_phase_descriptions_has_all_phases(self):
        assert set(PHASE_DESCRIPTIONS.keys()) == self.ALL_PHASES

    def test_phase_details_has_all_phases(self):
        assert set(PHASE_DETAILS.keys()) == self.ALL_PHASES
