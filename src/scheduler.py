import logging
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application

from config.settings import REMINDER_HOUR, TIMEZONE
from src.ai import generate_reminder
from src.cycle import get_cycle_day, get_phase, get_phase_info
from src.db import Database

logger = logging.getLogger(__name__)


async def send_daily_reminder(app: Application):
    """Send daily proactive reminders to all active users with cycle config."""
    db: Database = app.bot_data["db"]
    today = date.today()

    for user in db.get_all_active_users():
        chat_id = user["chat_id"]
        config = db.get_user_config(chat_id)
        if not config:
            continue

        last_period = date.fromisoformat(config["last_period_date"])
        cycle_length = config["cycle_length"]
        period_duration = config.get("period_duration", 5) or 5
        year_of_birth = config.get("year_of_birth")
        age = today.year - year_of_birth if year_of_birth else None

        cycle_day = get_cycle_day(last_period, today, cycle_length)
        phase = get_phase(cycle_day, cycle_length, period_duration)
        info = get_phase_info(cycle_day, cycle_length, period_duration)

        # Proportional PMS warning: 2 days before PMS starts
        pms_start = cycle_length - 6
        pms_warning_day = pms_start - 2

        # Determine if we should send a reminder today
        should_send = False
        if phase in ("pms", "menstruation"):
            should_send = True
        elif phase == "ovulation":
            should_send = True
        elif phase == "luteal" and cycle_day == pms_warning_day:
            should_send = True

        if not should_send:
            logger.info(f"User {chat_id}: day {cycle_day}, phase {phase} — no reminder needed.")
            continue

        recent_logs = db.get_user_logs_for_date(chat_id, today) or db.get_user_recent_logs(chat_id, 3)

        try:
            tip = await generate_reminder(phase, cycle_day, recent_logs, age=age)

            if phase == "luteal" and cycle_day == pms_warning_day:
                header = "\u26a1 Heads up darling: PMS starts in 2 days! Brace yourself \U0001f49c"
            else:
                header = f"Good morning darling! \U0001f338\n{info['label']} \u2014 Day {cycle_day}"

            message = f"{header}\n\n{tip}"
            await app.bot.send_message(chat_id=chat_id, text=message)
            logger.info(f"Sent reminder to {chat_id}: day {cycle_day}, phase {phase}")
        except Exception as e:
            logger.error(f"Failed to send reminder to {chat_id}: {e}")


def setup_scheduler(app: Application) -> AsyncIOScheduler:
    """Set up APScheduler for daily reminders."""
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        send_daily_reminder,
        trigger="cron",
        hour=REMINDER_HOUR,
        minute=0,
        args=[app],
        id="daily_reminder",
        replace_existing=True,
    )
    return scheduler
