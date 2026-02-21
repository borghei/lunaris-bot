from datetime import date, timedelta


def get_cycle_day(last_period_start: date, today: date, cycle_length: int = 28) -> int:
    """Return current cycle day (1-based). Auto-wraps if past cycle_length."""
    delta = (today - last_period_start).days
    if delta < 0:
        return 1
    return (delta % cycle_length) + 1


def get_phase(cycle_day: int, cycle_length: int = 28, period_duration: int = 5) -> str:
    """Return the current phase name based on cycle day with proportional boundaries.

    Medical model: luteal phase is fixed at ~14 days before end of cycle.
    """
    ovulation_day = max(cycle_length - 14, period_duration + 1)
    pms_start = cycle_length - 6

    if 1 <= cycle_day <= period_duration:
        return "menstruation"
    elif period_duration < cycle_day < ovulation_day:
        return "follicular"
    elif cycle_day == ovulation_day:
        return "ovulation"
    elif ovulation_day < cycle_day < pms_start:
        return "luteal"
    else:
        return "pms"


PHASE_LABELS = {
    "menstruation": "\U0001fa78 Period",
    "follicular": "\U0001f331 Follicular",
    "ovulation": "\u2728 Ovulation",
    "luteal": "\U0001f319 Luteal",
    "pms": "\u26a1 PMS",
}

PHASE_DESCRIPTIONS = {
    "menstruation": "You're on your period darling, your body's working hard. Be extra kind to yourself \U0001f49b",
    "follicular": "You made it through the tough part darling! Energy's coming back \U0001f338",
    "ovulation": "It's ovulation day darling \u2014 you're glowing and at peak energy! \u2728",
    "luteal": "Your body's gearing up darling, totally okay if you're a bit tired \U0001f319",
    "pms": "PMS has entered the chat darling. If everything's annoying, it's not you, it's hormones \U0001f49c",
}


def get_phase_detail(phase: str, cycle_length: int = 28, period_duration: int = 5) -> str:
    """Return phase detail text with proportional day ranges."""
    ovulation_day = max(cycle_length - 14, period_duration + 1)
    pms_start = cycle_length - 6

    details = {
        "menstruation": (
            f"\U0001fa78 *Period Phase (Day 1-{period_duration})*\n\n"
            "Your body is shedding the uterine lining, darling.\n"
            "Cramps, back pain, fatigue, mood swings \u2014 the whole package.\n"
            "Not exactly a party, but it'll pass! \U0001f4aa\n\n"
            "\U0001f49b Tips:\n"
            "- Get plenty of rest\n"
            "- Warm drinks (tea fixes everything \u2615)\n"
            "- Heating pad on your belly\n"
            "- Light exercise like walking"
        ),
        "follicular": (
            f"\U0001f331 *Follicular Phase (Day {period_duration + 1}-{ovulation_day - 1})*\n\n"
            "Energy's coming back darling! Estrogen is rising \U0001f338\n"
            "Creativity and focus are at their best.\n"
            "You're the best version of yourself right now, enjoy it!\n\n"
            "\U0001f49b Tips:\n"
            "- Great time to start new projects\n"
            "- High-energy workouts\n"
            "- Nutritious, protein-rich meals"
        ),
        "ovulation": (
            f"\u2728 *Ovulation (Day {ovulation_day})*\n\n"
            "Peak energy, confidence, and social drive, darling!\n"
            "Fertility is at its highest.\n"
            "You can conquer anything today \U0001f451\n\n"
            "\U0001f49b Tips:\n"
            "- Make the most of your high energy\n"
            "- Intense workouts are totally fine\n"
            "- Be social!"
        ),
        "luteal": (
            f"\U0001f319 *Luteal Phase (Day {ovulation_day + 1}-{pms_start - 1})*\n\n"
            "Progesterone is rising darling. Your body is preparing.\n"
            "Energy might dip a bit \u2014 that's totally normal.\n"
            "Time to slow down, the world isn't going anywhere \U0001fac2\n\n"
            "\U0001f49b Tips:\n"
            "- High-fiber foods\n"
            "- Get enough sleep\n"
            "- Moderate exercise like yoga"
        ),
        "pms": (
            f"\u26a1 *PMS Phase (Day {pms_start}-{cycle_length})*\n\n"
            "Hormones are shifting, darling.\n"
            "Sensitivity, mood swings, fatigue, cravings \u2014 all normal.\n"
            "If you wanna yell at everyone, that's the hormones talking, not you \U0001f49c\n\n"
            "\U0001f49b Tips:\n"
            "- Be kind to yourself\n"
            "- Magnesium and vitamin B6\n"
            "- Dark chocolate is fine \u2014 it's science, not an excuse! \U0001f36b\n"
            "- Walking and deep breathing"
        ),
    }
    return details.get(phase, PHASE_DESCRIPTIONS.get(phase, ""))


# Keep static PHASE_DETAILS for backward compatibility (default 28-day/5-day values)
PHASE_DETAILS = {phase: get_phase_detail(phase) for phase in PHASE_LABELS}


def get_phase_info(cycle_day: int, cycle_length: int = 28, period_duration: int = 5) -> dict:
    """Return detailed phase info."""
    phase = get_phase(cycle_day, cycle_length, period_duration)
    return {
        "cycle_day": cycle_day,
        "phase": phase,
        "label": PHASE_LABELS[phase],
        "description": PHASE_DESCRIPTIONS[phase],
    }


def predict_dates(last_period_start: date, cycle_length: int = 28) -> dict:
    """Predict next period, PMS start, and ovulation dates from last period start."""
    next_period = last_period_start + timedelta(days=cycle_length)
    next_pms = last_period_start + timedelta(days=cycle_length - 7)
    next_ovulation = last_period_start + timedelta(days=cycle_length - 15)

    today = date.today()
    # If predicted dates are in the past, advance by one cycle
    while next_period <= today:
        next_period += timedelta(days=cycle_length)
        next_pms += timedelta(days=cycle_length)
        next_ovulation += timedelta(days=cycle_length)

    return {
        "next_period": next_period,
        "next_pms": next_pms,
        "next_ovulation": next_ovulation,
    }


def days_until(target: date, today: date | None = None) -> int:
    today = today or date.today()
    return (target - today).days


def get_current_cycle_start(last_period_start: date, today: date, cycle_length: int = 28) -> date:
    """Get the start date of the current cycle."""
    delta = (today - last_period_start).days
    if delta < 0:
        return last_period_start
    cycles_passed = delta // cycle_length
    return last_period_start + timedelta(days=cycles_passed * cycle_length)
