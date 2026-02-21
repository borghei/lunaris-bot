import functools
import logging
import time
from collections import defaultdict
from datetime import date, datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ContextTypes

from config.settings import MAX_CHAT_HISTORY, VERSION
from src.ai import generate_tip, generate_chat_response
from src.cycle import (
    get_cycle_day,
    get_phase,
    get_phase_info,
    get_phase_detail,
    predict_dates,
    days_until,
    PHASE_LABELS,
    PHASE_DESCRIPTIONS,
)
from src.db import Database

MAX_NOTE_LENGTH = 500
MAX_CHAT_MESSAGE_LENGTH = 2000
AI_RATE_LIMIT = 5
AI_RATE_WINDOW = 60.0
_ai_call_timestamps: dict[int, list[float]] = defaultdict(list)

MIN_PERIOD_DURATION = 2
MAX_PERIOD_DURATION = 7


def _check_ai_rate_limit(chat_id: int) -> bool:
    """Return True if the user is within rate limits."""
    now = time.monotonic()
    timestamps = _ai_call_timestamps[chat_id]
    _ai_call_timestamps[chat_id] = [t for t in timestamps if now - t < AI_RATE_WINDOW]
    if len(_ai_call_timestamps[chat_id]) >= AI_RATE_LIMIT:
        return False
    _ai_call_timestamps[chat_id].append(now)
    return True


def _escape_markdown(text: str) -> str:
    """Escape Markdown V1 special characters in user-generated text."""
    for char in ('*', '_', '`', '['):
        text = text.replace(char, '\\' + char)
    return text

MIN_CYCLE_LENGTH = 20
MAX_CYCLE_LENGTH = 45

logger = logging.getLogger(__name__)


MAIN_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("\U0001f4ca Status", callback_data="status"),
        InlineKeyboardButton("\U0001f4a1 Tip", callback_data="tip"),
    ],
    [
        InlineKeyboardButton("\U0001fa78 Period Started!", callback_data="period"),
        InlineKeyboardButton("\U0001f52e Next Dates", callback_data="next"),
    ],
    [
        InlineKeyboardButton("\U0001f300 Phase Details", callback_data="phase"),
        InlineKeyboardButton("\U0001f4cb History", callback_data="history"),
    ],
    [
        InlineKeyboardButton("\U0001f4ac Chat with me!", callback_data="chat"),
        InlineKeyboardButton("\u2699\ufe0f Settings", callback_data="settings"),
    ],
])

BACK_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("\U0001f519 Back to Menu", callback_data="menu")],
])

TIP_AGAIN_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("\U0001f4a1 Another Tip", callback_data="tip"),
        InlineKeyboardButton("\U0001f519 Back to Menu", callback_data="menu"),
    ],
])

PERIOD_CONFIRM_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("\u2705 Yes, Today!", callback_data="period_confirm"),
        InlineKeyboardButton("\U0001f519 Cancel", callback_data="menu"),
    ],
])


# -- Auth decorators (3 tiers) --

def whitelisted(func):
    """Decorator: any whitelisted (active) user."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        db = get_db(context)
        if not db.is_user_authorized(chat_id):
            if update.message:
                await update.message.reply_text("Sorry darling, this bot isn't for you \U0001f494")
            return
        return await func(update, context)
    return wrapper


def authorized(func):
    """Decorator: whitelisted + has completed setup (has cycle config)."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        db = get_db(context)
        if not db.is_user_authorized(chat_id):
            if update.message:
                await update.message.reply_text("Sorry darling, this bot isn't for you \U0001f494")
            return
        if not db.user_has_config(chat_id):
            if update.message:
                await update.message.reply_text(
                    "You need to set up your cycle first, darling!\n"
                    "Use: `/setup <cycle_length> <last_period_date>`\n"
                    "Example: `/setup 28 2026-02-15`",
                    parse_mode="Markdown",
                )
            return
        return await func(update, context)
    return wrapper


def authorized_callback(func):
    """Decorator for callback query handlers — whitelisted + setup done."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        db = get_db(context)
        if not db.is_user_authorized(chat_id):
            await update.callback_query.answer("Not authorized")
            return
        if not db.user_has_config(chat_id):
            await update.callback_query.answer("Please run /setup first")
            return
        return await func(update, context)
    return wrapper


def admin_only(func):
    """Decorator: admin-only commands."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        db = get_db(context)
        if not db.is_admin(chat_id):
            if update.message:
                await update.message.reply_text("This command is admin-only, darling \U0001f512")
            return
        return await func(update, context)
    return wrapper


# -- Helpers --

def get_db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    return context.bot_data["db"]


def get_cycle_info(db: Database, chat_id: int) -> tuple[date, int, int]:
    """Get last_period_start, cycle_length, and period_duration from DB."""
    config = db.get_user_config(chat_id)
    last_period = date.fromisoformat(config["last_period_date"])
    cycle_length = config["cycle_length"]
    period_duration = config.get("period_duration", 5) or 5
    return last_period, cycle_length, period_duration


# -- Admin commands --

@admin_only
async def adduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: `/adduser <telegram_user_id>`",
            parse_mode="Markdown",
        )
        return
    try:
        new_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("That doesn't look like a valid user ID, darling.")
        return

    db = get_db(context)
    db.add_user(new_user_id, added_by=update.effective_chat.id)
    await update.message.reply_text(f"\u2705 User `{new_user_id}` has been whitelisted!", parse_mode="Markdown")


@admin_only
async def removeuser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: `/removeuser <telegram_user_id>`",
            parse_mode="Markdown",
        )
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("That doesn't look like a valid user ID, darling.")
        return

    db = get_db(context)
    if db.is_admin(target_id):
        await update.message.reply_text("Can't remove an admin, darling \U0001f512")
        return
    db.remove_user(target_id)
    await update.message.reply_text(f"\u2705 User `{target_id}` has been removed.", parse_mode="Markdown")


@admin_only
async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = get_db(context)
    users = db.get_all_whitelisted_users()
    if not users:
        await update.message.reply_text("No users in the whitelist.")
        return

    lines = ["\U0001f465 *Whitelisted Users:*\n"]
    for u in users:
        status = "\u2705" if u["is_active"] else "\u274c"
        role = " (admin)" if u["is_admin"] else ""
        lines.append(f"{status} `{u['chat_id']}`{role}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# -- Setup command (whitelisted users who haven't configured yet) --

@whitelisted
async def setup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Set up your cycle, darling!\n"
            "Usage: `/setup <cycle_length> <last_period_date> [period_duration] [birth_year]`\n"
            "Example: `/setup 28 2026-02-15`\n"
            "Or: `/setup 28 2026-02-15 5 1995`",
            parse_mode="Markdown",
        )
        return

    try:
        cycle_length = int(context.args[0])
        if not MIN_CYCLE_LENGTH <= cycle_length <= MAX_CYCLE_LENGTH:
            await update.message.reply_text(f"Cycle length should be between {MIN_CYCLE_LENGTH} and {MAX_CYCLE_LENGTH} days, darling.")
            return
    except ValueError:
        await update.message.reply_text("Cycle length must be a number, darling.")
        return

    try:
        last_period = date.fromisoformat(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "Wrong date format darling. Use YYYY-MM-DD, like `2026-02-15`",
            parse_mode="Markdown",
        )
        return

    if last_period > date.today():
        await update.message.reply_text("That date is in the future, darling! Use a past or today's date.")
        return

    # Optional: period duration
    period_duration = 5
    if len(context.args) >= 3:
        try:
            period_duration = int(context.args[2])
            if not MIN_PERIOD_DURATION <= period_duration <= MAX_PERIOD_DURATION:
                await update.message.reply_text(
                    f"Period duration should be between {MIN_PERIOD_DURATION} and {MAX_PERIOD_DURATION} days, darling."
                )
                return
        except ValueError:
            await update.message.reply_text("Period duration must be a number, darling.")
            return

    # Optional: birth year
    year_of_birth = None
    if len(context.args) >= 4:
        try:
            year_of_birth = int(context.args[3])
            current_year = date.today().year
            if not 1940 <= year_of_birth <= current_year - 10:
                await update.message.reply_text(
                    f"Birth year should be between 1940 and {current_year - 10}, darling."
                )
                return
        except ValueError:
            await update.message.reply_text("Birth year must be a number, darling.")
            return

    chat_id = update.effective_chat.id
    db = get_db(context)
    db.upsert_user_config(chat_id, cycle_length, last_period.isoformat(), period_duration, year_of_birth)

    cycle_day = get_cycle_day(last_period, date.today(), cycle_length)
    info = get_phase_info(cycle_day, cycle_length, period_duration)

    lines = [
        f"\u2705 All set, darling!\n",
        f"\U0001f4cf Cycle length: *{cycle_length}* days",
        f"\U0001f4c5 Last period: *{last_period}*",
        f"\U0001fa78 Period duration: *{period_duration}* days",
    ]
    if year_of_birth:
        age = date.today().year - year_of_birth
        lines.append(f"\U0001f382 Age: ~*{age}* years old")
    lines.append(f"\U0001f4c5 Today is day *{cycle_day}* \u2014 {info['label']}")
    lines.append(f"\nYou're all good to go! Use /start to see the main menu \U0001f49b")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
    )


# -- Clear chat command --

@authorized
async def clearchat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db = get_db(context)
    db.clear_chat_history(chat_id)
    await update.message.reply_text("\u2705 Chat history cleared, darling! Fresh start \U0001f49b")


# -- Existing commands (now per-user) --

@whitelisted
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db = get_db(context)

    if not db.user_has_config(chat_id):
        await update.message.reply_text(
            "Hey darling! \U0001f319\n\n"
            "I'm *Lunaris*, your cycle companion.\n"
            "Let's get you set up first!\n\n"
            "Use: `/setup <cycle_length> <last_period_date>`\n"
            "Example: `/setup 28 2026-02-15`",
            parse_mode="Markdown",
        )
        return

    last_period, cycle_length, period_duration = get_cycle_info(db, chat_id)
    today = date.today()
    cycle_day = get_cycle_day(last_period, today, cycle_length)
    info = get_phase_info(cycle_day, cycle_length, period_duration)

    text = (
        f"Hey darling! \U0001f319\n\n"
        f"I'm *Lunaris*, your cycle companion.\n"
        f"I promise not to be annoying \u2014 just here to look out for you \U0001f49b\n\n"
        f"\U0001f4c5 Today is day *{info['cycle_day']}* of your cycle\n"
        f"Phase: *{info['label']}*\n"
        f"{info['description']}\n\n"
        f"Pick something from below, or use commands anytime!"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)


@authorized_callback
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all inline keyboard button presses."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu":
        await _show_menu(query, context)
    elif data == "status":
        await _show_status(query, context)
    elif data == "tip":
        await _show_tip(query, context)
    elif data == "next":
        await _show_next(query, context)
    elif data == "phase":
        await _show_phase(query, context)
    elif data == "history":
        await _show_history(query, context)
    elif data == "settings":
        await _show_settings(query, context)
    elif data == "period":
        await _show_period_confirm(query, context)
    elif data == "period_confirm":
        await _do_period_today(query, context)
    elif data == "chat":
        await _show_chat_intro(query, context)


async def _show_menu(query, context):
    chat_id = query.message.chat_id
    db = get_db(context)
    last_period, cycle_length, period_duration = get_cycle_info(db, chat_id)
    today = date.today()
    cycle_day = get_cycle_day(last_period, today, cycle_length)
    info = get_phase_info(cycle_day, cycle_length, period_duration)

    text = (
        f"\U0001f319 *Lunaris \u2014 Main Menu*\n\n"
        f"\U0001f4c5 Day *{info['cycle_day']}* \u2014 {info['label']}\n"
        f"{info['description']}\n\n"
        f"What would you like to do, darling?"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)


async def _show_status(query, context):
    chat_id = query.message.chat_id
    db = get_db(context)
    last_period, cycle_length, period_duration = get_cycle_info(db, chat_id)
    today = date.today()
    cycle_day = get_cycle_day(last_period, today, cycle_length)
    info = get_phase_info(cycle_day, cycle_length, period_duration)

    text = (
        f"\U0001f4ca *Your Status, Darling*\n\n"
        f"\U0001f4c5 Cycle day: *{info['cycle_day']}* of {cycle_length}\n"
        f"Phase: *{info['label']}*\n\n"
        f"{info['description']}"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=BACK_KEYBOARD)


async def _show_tip(query, context):
    chat_id = query.message.chat_id
    if not _check_ai_rate_limit(chat_id):
        await query.edit_message_text(
            "Easy there darling, let me catch my breath! Try again in a minute \U0001f49b",
            reply_markup=BACK_KEYBOARD,
        )
        return
    db = get_db(context)
    last_period, cycle_length, period_duration = get_cycle_info(db, chat_id)
    today = date.today()
    cycle_day = get_cycle_day(last_period, today, cycle_length)
    phase = get_phase(cycle_day, cycle_length, period_duration)
    recent_logs = db.get_user_recent_logs(chat_id, 3)

    await query.edit_message_text("Hold on darling, thinking of something good for you... \U0001f914")

    try:
        tip = await generate_tip(phase, cycle_day, recent_logs, model="claude-sonnet-4-6")
        await query.edit_message_text(
            f"\U0001f4a1 *Tip for You, Darling:*\n\n{tip}",
            parse_mode="Markdown",
            reply_markup=TIP_AGAIN_KEYBOARD,
        )
    except Exception as e:
        logger.error(f"AI tip generation failed: {e}")
        await query.edit_message_text(
            "Oops, my brain froze darling \U0001f605 Try again in a sec!",
            reply_markup=BACK_KEYBOARD,
        )


async def _show_next(query, context):
    chat_id = query.message.chat_id
    db = get_db(context)
    last_period, cycle_length, period_duration = get_cycle_info(db, chat_id)
    predictions = predict_dates(last_period, cycle_length)
    today = date.today()

    text = (
        f"\U0001f52e *Upcoming Dates, Darling*\n\n"
        f"\U0001fa78 Next period: *{predictions['next_period']}* ({days_until(predictions['next_period'], today)} days)\n"
        f"\u26a1 Next PMS: *{predictions['next_pms']}* ({days_until(predictions['next_pms'], today)} days)\n"
        f"\u2728 Next ovulation: *{predictions['next_ovulation']}* ({days_until(predictions['next_ovulation'], today)} days)"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=BACK_KEYBOARD)


async def _show_phase(query, context):
    chat_id = query.message.chat_id
    db = get_db(context)
    last_period, cycle_length, period_duration = get_cycle_info(db, chat_id)
    today = date.today()
    cycle_day = get_cycle_day(last_period, today, cycle_length)
    info = get_phase_info(cycle_day, cycle_length, period_duration)

    text = get_phase_detail(info["phase"], cycle_length, period_duration)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=BACK_KEYBOARD)


async def _show_history(query, context):
    chat_id = query.message.chat_id
    db = get_db(context)
    logs = db.get_user_recent_logs(chat_id, 10)

    if not logs:
        await query.edit_message_text(
            "\U0001f4cb No notes yet, darling.\nUse /log to add one!",
            reply_markup=BACK_KEYBOARD,
        )
        return

    lines = ["\U0001f4cb *Recent Notes, Darling:*\n"]
    for log in logs:
        phase_label = PHASE_LABELS.get(log["phase"], log["phase"])
        lines.append(f"\U0001f4c5 {log['date']} \u2014 {phase_label}\n\U0001f4dd {_escape_markdown(log['note'])}\n")

    await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=BACK_KEYBOARD)


async def _show_settings(query, context):
    chat_id = query.message.chat_id
    db = get_db(context)
    config = db.get_user_config(chat_id)

    lines = [
        f"\u2699\ufe0f *Settings, Darling*\n",
        f"\U0001f4cf Cycle length: *{config['cycle_length']}* days",
        f"\U0001f4c5 Last period start: *{config['last_period_date']}*",
        f"\U0001fa78 Period duration: *{config.get('period_duration', 5) or 5}* days",
    ]
    yob = config.get("year_of_birth")
    if yob:
        lines.append(f"\U0001f382 Birth year: *{yob}* (~{date.today().year - yob} years old)")
    lines.append(
        f"\nTo change cycle length:\n`/settings 30`\n"
        f"To change period duration:\n`/settings period 4`\n"
        f"To set birth year:\n`/settings age 1995`\n"
        f"To change period date:\n`/adjust 2026-02-25`"
    )

    await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=BACK_KEYBOARD)


async def _show_chat_intro(query, context):
    text = (
        "\U0001f4ac *Chat with Lunaris*\n\n"
        "Just type anything, darling! No commands needed.\n"
        "Ask me about your cycle, symptoms, nutrition, exercise, "
        "hormones, sleep, skin \u2014 anything women's health related \U0001f49b\n\n"
        "I'll remember our conversation, and you can clear it anytime with /clearchat"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=BACK_KEYBOARD)


async def _show_period_confirm(query, context):
    text = (
        "\U0001fa78 *Period started today, darling?*\n\n"
        "I'll reset your cycle and update your cycle length.\n"
        "If it started on a different day, use:\n`/period 2026-02-25`"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=PERIOD_CONFIRM_KEYBOARD)


def _process_period(db: Database, chat_id: int, period_date: date) -> str:
    """Common logic for logging a period. Returns the length message."""
    last_period, cycle_length, period_duration = get_cycle_info(db, chat_id)

    # Log to period history
    db.add_period_log(chat_id, period_date.isoformat())

    actual_gap = (period_date - last_period).days

    # Try adaptive cycle length from history first
    computed = db.get_computed_cycle_length(chat_id)
    if computed:
        db.update_user_cycle_length(chat_id, computed)
        length_msg = f"\U0001f4cf Cycle length updated to *{computed}* days (computed from your history)"
    elif actual_gap > 0 and 18 <= actual_gap <= 45:
        new_cycle_length = round(actual_gap * 0.7 + cycle_length * 0.3)
        db.update_user_cycle_length(chat_id, new_cycle_length)
        length_msg = f"\U0001f4cf Cycle length updated to *{new_cycle_length}* days (this one was {actual_gap} days)"
    elif actual_gap > 0:
        length_msg = f"This cycle was {actual_gap} days \u2014 a bit unusual, so I kept the length as is"
    else:
        length_msg = "Cycle length unchanged"

    db.update_user_last_period_date(chat_id, period_date.isoformat())
    return length_msg


async def _do_period_today(query, context):
    chat_id = query.message.chat_id
    db = get_db(context)
    period_date = date.today()

    length_msg = _process_period(db, chat_id, period_date)

    text = (
        f"\u2705 Got it darling! New period started on *{period_date}*.\n\n"
        f"{length_msg}\n\n"
        f"Take it easy these next few days \U0001f49b I'm here for you!"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=BACK_KEYBOARD)


# === Command handlers (still work alongside buttons) ===

@authorized
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db = get_db(context)
    last_period, cycle_length, period_duration = get_cycle_info(db, chat_id)
    today = date.today()
    cycle_day = get_cycle_day(last_period, today, cycle_length)
    info = get_phase_info(cycle_day, cycle_length, period_duration)

    text = (
        f"\U0001f4ca *Your Status, Darling*\n\n"
        f"\U0001f4c5 Cycle day: *{info['cycle_day']}* of {cycle_length}\n"
        f"Phase: *{info['label']}*\n\n"
        f"{info['description']}"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)


@authorized
async def tip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not _check_ai_rate_limit(chat_id):
        await update.message.reply_text("Easy there darling, let me catch my breath! Try again in a minute \U0001f49b")
        return
    db = get_db(context)
    last_period, cycle_length, period_duration = get_cycle_info(db, chat_id)
    today = date.today()
    cycle_day = get_cycle_day(last_period, today, cycle_length)
    phase = get_phase(cycle_day, cycle_length, period_duration)
    recent_logs = db.get_user_recent_logs(chat_id, 3)

    await update.message.reply_text("Hold on darling, thinking... \U0001f914")

    try:
        tip = await generate_tip(phase, cycle_day, recent_logs, model="claude-sonnet-4-6")
        await update.message.reply_text(
            f"\U0001f4a1 *Tip for You, Darling:*\n\n{tip}",
            parse_mode="Markdown",
            reply_markup=TIP_AGAIN_KEYBOARD,
        )
    except Exception as e:
        logger.error(f"AI tip generation failed: {e}")
        await update.message.reply_text("Oops, my brain froze darling \U0001f605 Try again in a sec!")


@authorized
async def period_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Record that period has started. Resets cycle and learns actual cycle length."""
    chat_id = update.effective_chat.id
    db = get_db(context)

    if context.args:
        try:
            period_date = date.fromisoformat(context.args[0])
        except ValueError:
            await update.message.reply_text(
                "Wrong date format darling. Use this:\n"
                "`/period 2026-02-25`\n\n"
                "Or just type `/period` to log today \U0001f49b",
                parse_mode="Markdown",
            )
            return
        if period_date > date.today():
            await update.message.reply_text("That date is in the future, darling! Use a past or today's date.")
            return
    else:
        period_date = date.today()

    length_msg = _process_period(db, chat_id, period_date)

    text = (
        f"\u2705 Got it darling! New period started on *{period_date}*.\n\n"
        f"{length_msg}\n\n"
        f"Take it easy these next few days \U0001f49b I'm here for you!"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)


@authorized
async def log_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "\U0001f4dd Write your note, darling:\n`/log feeling tired today`",
            parse_mode="Markdown",
        )
        return

    chat_id = update.effective_chat.id
    db = get_db(context)
    last_period, cycle_length, period_duration = get_cycle_info(db, chat_id)
    today = date.today()
    cycle_day = get_cycle_day(last_period, today, cycle_length)
    phase = get_phase(cycle_day, cycle_length, period_duration)
    note = " ".join(context.args)[:MAX_NOTE_LENGTH]

    db.add_user_log(chat_id, note, phase)
    await update.message.reply_text(
        f"\u2705 Logged, darling!\n\U0001f4dd {_escape_markdown(note)}\n\U0001f300 Phase: {PHASE_LABELS[phase]}",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )


@authorized
async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db = get_db(context)
    logs = db.get_user_recent_logs(chat_id, 10)

    if not logs:
        await update.message.reply_text(
            "\U0001f4cb No notes yet, darling.\nUse /log to add one!",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    lines = ["\U0001f4cb *Recent Notes, Darling:*\n"]
    for log in logs:
        phase_label = PHASE_LABELS.get(log["phase"], log["phase"])
        lines.append(f"\U0001f4c5 {log['date']} \u2014 {phase_label}\n\U0001f4dd {_escape_markdown(log['note'])}\n")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)


@authorized
async def next_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db = get_db(context)
    last_period, cycle_length, period_duration = get_cycle_info(db, chat_id)
    predictions = predict_dates(last_period, cycle_length)
    today = date.today()

    text = (
        f"\U0001f52e *Upcoming Dates, Darling*\n\n"
        f"\U0001fa78 Next period: *{predictions['next_period']}* ({days_until(predictions['next_period'], today)} days)\n"
        f"\u26a1 Next PMS: *{predictions['next_pms']}* ({days_until(predictions['next_pms'], today)} days)\n"
        f"\u2728 Next ovulation: *{predictions['next_ovulation']}* ({days_until(predictions['next_ovulation'], today)} days)"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)


@authorized
async def phase_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db = get_db(context)
    last_period, cycle_length, period_duration = get_cycle_info(db, chat_id)
    today = date.today()
    cycle_day = get_cycle_day(last_period, today, cycle_length)
    info = get_phase_info(cycle_day, cycle_length, period_duration)

    text = get_phase_detail(info["phase"], cycle_length, period_duration)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)


@authorized
async def adjust_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "\U0001f4c5 Enter the start date of your last period, darling:\n"
            "`/adjust 2026-02-25`",
            parse_mode="Markdown",
        )
        return

    try:
        new_date = date.fromisoformat(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "Wrong date format darling. Example: `/adjust 2026-02-25`",
            parse_mode="Markdown",
        )
        return

    if new_date > date.today():
        await update.message.reply_text("That date is in the future, darling! Use a past or today's date.")
        return

    chat_id = update.effective_chat.id
    db = get_db(context)
    db.update_user_last_period_date(chat_id, new_date.isoformat())
    await update.message.reply_text(
        f"\u2705 Period start date changed to *{new_date}*, darling!",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )


@authorized
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db = get_db(context)
    config = db.get_user_config(chat_id)

    if context.args:
        subcmd = context.args[0].lower()

        # /settings period <duration>
        if subcmd == "period" and len(context.args) >= 2:
            try:
                new_duration = int(context.args[1])
                if not MIN_PERIOD_DURATION <= new_duration <= MAX_PERIOD_DURATION:
                    await update.message.reply_text(
                        f"Period duration must be between {MIN_PERIOD_DURATION} and {MAX_PERIOD_DURATION} days, darling."
                    )
                    return
                db.update_user_period_duration(chat_id, new_duration)
                await update.message.reply_text(
                    f"\u2705 Period duration changed to *{new_duration}* days, darling!",
                    parse_mode="Markdown",
                    reply_markup=MAIN_KEYBOARD,
                )
                return
            except ValueError:
                await update.message.reply_text("Period duration must be a number, darling.")
                return

        # /settings age <birth_year>
        if subcmd == "age" and len(context.args) >= 2:
            try:
                year_of_birth = int(context.args[1])
                current_year = date.today().year
                if not 1940 <= year_of_birth <= current_year - 10:
                    await update.message.reply_text(
                        f"Birth year should be between 1940 and {current_year - 10}, darling."
                    )
                    return
                db.update_user_year_of_birth(chat_id, year_of_birth)
                age = current_year - year_of_birth
                await update.message.reply_text(
                    f"\u2705 Birth year set to *{year_of_birth}* (~{age} years old), darling!",
                    parse_mode="Markdown",
                    reply_markup=MAIN_KEYBOARD,
                )
                return
            except ValueError:
                await update.message.reply_text("Birth year must be a number, darling.")
                return

        # /settings <cycle_length> (existing behavior)
        try:
            new_length = int(subcmd)
            if not MIN_CYCLE_LENGTH <= new_length <= MAX_CYCLE_LENGTH:
                await update.message.reply_text(f"Cycle length must be between {MIN_CYCLE_LENGTH} and {MAX_CYCLE_LENGTH} days, darling.")
                return
            db.update_user_cycle_length(chat_id, new_length)
            await update.message.reply_text(
                f"\u2705 Cycle length changed to *{new_length}* days, darling!",
                parse_mode="Markdown",
                reply_markup=MAIN_KEYBOARD,
            )
            return
        except ValueError:
            await update.message.reply_text(
                "Unknown setting, darling. Try:\n"
                "`/settings 30` \u2014 cycle length\n"
                "`/settings period 4` \u2014 period duration\n"
                "`/settings age 1995` \u2014 birth year",
                parse_mode="Markdown",
            )
            return

    lines = [
        f"\u2699\ufe0f *Settings, Darling*\n",
        f"\U0001f4cf Cycle length: *{config['cycle_length']}* days",
        f"\U0001f4c5 Last period start: *{config['last_period_date']}*",
        f"\U0001fa78 Period duration: *{config.get('period_duration', 5) or 5}* days",
    ]
    yob = config.get("year_of_birth")
    if yob:
        lines.append(f"\U0001f382 Birth year: *{yob}* (~{date.today().year - yob} years old)")
    lines.append(
        f"\nTo change cycle length:\n`/settings 30`\n"
        f"To change period duration:\n`/settings period 4`\n"
        f"To set birth year:\n`/settings age 1995`\n"
        f"To change period date:\n`/adjust 2026-02-25`"
    )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)


# -- About command --

@whitelisted
async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"\U0001f319 *Lunaris* \u2014 v{VERSION}\n\n"
        f"Your personal cycle companion bot.\n"
        f"Tracks your menstrual cycle, predicts upcoming dates, "
        f"and offers AI-powered tips tailored to your current phase.\n\n"
        f"\U0001f469\u200d\U0001f4bb Author: @borghei\n"
        f"\U0001f6e0 Built with: python-telegram-bot, Claude AI, SQLite"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=BACK_KEYBOARD)


# -- Free-form AI chat handler --

@authorized
async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any non-command text message as a free-form AI chat."""
    chat_id = update.effective_chat.id
    db = get_db(context)
    user_message = update.message.text[:MAX_CHAT_MESSAGE_LENGTH]

    if not _check_ai_rate_limit(chat_id):
        await update.message.reply_text(
            "Easy there darling, let me catch my breath! Try again in a minute \U0001f49b"
        )
        return

    # Get cycle context
    last_period, cycle_length, period_duration = get_cycle_info(db, chat_id)
    today = date.today()
    cycle_day = get_cycle_day(last_period, today, cycle_length)
    phase = get_phase(cycle_day, cycle_length, period_duration)
    recent_logs = db.get_user_recent_logs(chat_id, 3)

    # Get age if available
    config = db.get_user_config(chat_id)
    year_of_birth = config.get("year_of_birth") if config else None
    age = date.today().year - year_of_birth if year_of_birth else None

    # Get conversation history
    history = db.get_chat_history(chat_id, MAX_CHAT_HISTORY)

    # Send typing indicator
    await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.TYPING)

    try:
        response = await generate_chat_response(
            user_message=user_message,
            chat_history=history,
            cycle_day=cycle_day,
            phase=phase,
            recent_logs=recent_logs,
            age=age,
        )

        # Store both messages in history
        db.add_chat_message(chat_id, "user", user_message)
        db.add_chat_message(chat_id, "assistant", response)

        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Chat response generation failed: {e}")
        await update.message.reply_text(
            "Oops, my brain froze for a second darling \U0001f605 Try again?"
        )
