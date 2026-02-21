from datetime import date, timedelta


def get_cycle_day(last_period_start: date, today: date, cycle_length: int = 28) -> int:
    """Return current cycle day (1-based). Auto-wraps if past cycle_length."""
    delta = (today - last_period_start).days
    if delta < 0:
        return 1
    return (delta % cycle_length) + 1


def get_phase(cycle_day: int, cycle_length: int = 28) -> str:
    """Return the current phase name based on cycle day."""
    if 1 <= cycle_day <= 5:
        return "menstruation"
    elif 6 <= cycle_day <= 13:
        return "follicular"
    elif cycle_day == 14:
        return "ovulation"
    elif 15 <= cycle_day <= 21:
        return "luteal"
    else:
        return "pms"


PHASE_LABELS = {
    "menstruation": "🩸 Period",
    "follicular": "🌱 Follicular",
    "ovulation": "✨ Ovulation",
    "luteal": "🌙 Luteal",
    "pms": "⚡ PMS",
}

PHASE_DESCRIPTIONS = {
    "menstruation": "You're on your period darling, your body's working hard. Be extra kind to yourself 💛",
    "follicular": "You made it through the tough part darling! Energy's coming back 🌸",
    "ovulation": "It's ovulation day darling — you're glowing and at peak energy! ✨",
    "luteal": "Your body's gearing up darling, totally okay if you're a bit tired 🌙",
    "pms": "PMS has entered the chat darling. If everything's annoying, it's not you, it's hormones 💜",
}

PHASE_DETAILS = {
    "menstruation": (
        "🩸 *Period Phase (Day 1-5)*\n\n"
        "Your body is shedding the uterine lining, darling.\n"
        "Cramps, back pain, fatigue, mood swings — the whole package.\n"
        "Not exactly a party, but it'll pass! 💪\n\n"
        "💛 Tips:\n"
        "- Get plenty of rest\n"
        "- Warm drinks (tea fixes everything ☕)\n"
        "- Heating pad on your belly\n"
        "- Light exercise like walking"
    ),
    "follicular": (
        "🌱 *Follicular Phase (Day 6-13)*\n\n"
        "Energy's coming back darling! Estrogen is rising 🌸\n"
        "Creativity and focus are at their best.\n"
        "You're the best version of yourself right now, enjoy it!\n\n"
        "💛 Tips:\n"
        "- Great time to start new projects\n"
        "- High-energy workouts\n"
        "- Nutritious, protein-rich meals"
    ),
    "ovulation": (
        "✨ *Ovulation (Day 14)*\n\n"
        "Peak energy, confidence, and social drive, darling!\n"
        "Fertility is at its highest.\n"
        "You can conquer anything today 👑\n\n"
        "💛 Tips:\n"
        "- Make the most of your high energy\n"
        "- Intense workouts are totally fine\n"
        "- Be social!"
    ),
    "luteal": (
        "🌙 *Luteal Phase (Day 15-21)*\n\n"
        "Progesterone is rising darling. Your body is preparing.\n"
        "Energy might dip a bit — that's totally normal.\n"
        "Time to slow down, the world isn't going anywhere 🫂\n\n"
        "💛 Tips:\n"
        "- High-fiber foods\n"
        "- Get enough sleep\n"
        "- Moderate exercise like yoga"
    ),
    "pms": (
        "⚡ *PMS Phase (Day 22-28)*\n\n"
        "Hormones are shifting, darling.\n"
        "Sensitivity, mood swings, fatigue, cravings — all normal.\n"
        "If you wanna yell at everyone, that's the hormones talking, not you 💜\n\n"
        "💛 Tips:\n"
        "- Be kind to yourself\n"
        "- Magnesium and vitamin B6\n"
        "- Dark chocolate is fine — it's science, not an excuse! 🍫\n"
        "- Walking and deep breathing"
    ),
}


def get_phase_info(cycle_day: int, cycle_length: int = 28) -> dict:
    """Return detailed phase info."""
    phase = get_phase(cycle_day, cycle_length)
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
    next_ovulation = last_period_start + timedelta(days=14)

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
