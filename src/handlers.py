import functools
import logging
import time
from collections import defaultdict
from datetime import date, datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ContextTypes

from config.settings import MAX_CHAT_HISTORY
from src.ai import generate_tip, generate_chat_response
from src.cycle import (
    get_cycle_day,
    get_phase,
    get_phase_info,
    predict_dates,
    days_until,
    PHASE_LABELS,
    PHASE_DESCRIPTIONS,
    PHASE_DETAILS,
)
from src.db import Database

MAX_NOTE_LENGTH = 500
MAX_CHAT_MESSAGE_LENGTH = 2000
AI_RATE_LIMIT = 5
AI_RATE_WINDOW = 60.0
_ai_call_timestamps: dict[int, list[float]] = defaultdict(list)


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
        InlineKeyboardButton("📊 Status", callback_data="status"),
        InlineKeyboardButton("💡 Tip", callback_data="tip"),
    ],
    [
        InlineKeyboardButton("🩸 Period Started!", callback_data="period"),
        InlineKeyboardButton("🔮 Next Dates", callback_data="next"),
    ],
    [
        InlineKeyboardButton("🌀 Phase Details", callback_data="phase"),
        InlineKeyboardButton("📋 History", callback_data="history"),
    ],
    [
        InlineKeyboardButton("💬 Chat with me!", callback_data="chat"),
        InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
    ],
])

BACK_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")],
])

TIP_AGAIN_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("💡 Another Tip", callback_data="tip"),
        InlineKeyboardButton("🔙 Back to Menu", callback_data="menu"),
    ],
])

PERIOD_CONFIRM_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("✅ Yes, Today!", callback_data="period_confirm"),
        InlineKeyboardButton("🔙 Cancel", callback_data="menu"),
    ],
])


# ── Auth decorators (3 tiers) ──────────────────────────────────────

def whitelisted(func):
    """Decorator: any whitelisted (active) user."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        db = get_db(context)
        if not db.is_user_authorized(chat_id):
            if update.message:
                await update.message.reply_text("Sorry darling, this bot isn't for you 💔")
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
                await update.message.reply_text("Sorry darling, this bot isn't for you 💔")
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
                await update.message.reply_text("This command is admin-only, darling 🔒")
            return
        return await func(update, context)
    return wrapper


# ── Helpers ─────────────────────────────────────────────────────────

def get_db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    return context.bot_data["db"]


def get_cycle_info(db: Database, chat_id: int) -> tuple[date, int]:
    """Get last_period_start and cycle_length from DB for a specific user."""
    config = db.get_user_config(chat_id)
    last_period = date.fromisoformat(config["last_period_date"])
    cycle_length = config["cycle_length"]
    return last_period, cycle_length


# ── Admin commands ──────────────────────────────────────────────────

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
    await update.message.reply_text(f"✅ User `{new_user_id}` has been whitelisted!", parse_mode="Markdown")


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
        await update.message.reply_text("Can't remove an admin, darling 🔒")
        return
    db.remove_user(target_id)
    await update.message.reply_text(f"✅ User `{target_id}` has been removed.", parse_mode="Markdown")


@admin_only
async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = get_db(context)
    users = db.get_all_whitelisted_users()
    if not users:
        await update.message.reply_text("No users in the whitelist.")
        return

    lines = ["👥 *Whitelisted Users:*\n"]
    for u in users:
        status = "✅" if u["is_active"] else "❌"
        role = " (admin)" if u["is_admin"] else ""
        lines.append(f"{status} `{u['chat_id']}`{role}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── Setup command (whitelisted users who haven't configured yet) ────

@whitelisted
async def setup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Set up your cycle, darling!\n"
            "Usage: `/setup <cycle_length> <last_period_date>`\n"
            "Example: `/setup 28 2026-02-15`",
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

    chat_id = update.effective_chat.id
    db = get_db(context)
    db.upsert_user_config(chat_id, cycle_length, last_period.isoformat())

    cycle_day = get_cycle_day(last_period, date.today(), cycle_length)
    info = get_phase_info(cycle_day, cycle_length)

    await update.message.reply_text(
        f"✅ All set, darling!\n\n"
        f"📏 Cycle length: *{cycle_length}* days\n"
        f"📅 Last period: *{last_period}*\n"
        f"📅 Today is day *{cycle_day}* — {info['label']}\n\n"
        f"You're all good to go! Use /start to see the main menu 💛",
        parse_mode="Markdown",
    )


# ── Clear chat command ──────────────────────────────────────────────

@authorized
async def clearchat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db = get_db(context)
    db.clear_chat_history(chat_id)
    await update.message.reply_text("✅ Chat history cleared, darling! Fresh start 💛")


# ── Existing commands (now per-user) ────────────────────────────────

@whitelisted
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db = get_db(context)

    if not db.user_has_config(chat_id):
        await update.message.reply_text(
            "Hey darling! 🌙\n\n"
            "I'm *Lunaris*, your cycle companion.\n"
            "Let's get you set up first!\n\n"
            "Use: `/setup <cycle_length> <last_period_date>`\n"
            "Example: `/setup 28 2026-02-15`",
            parse_mode="Markdown",
        )
        return

    last_period, cycle_length = get_cycle_info(db, chat_id)
    today = date.today()
    cycle_day = get_cycle_day(last_period, today, cycle_length)
    info = get_phase_info(cycle_day, cycle_length)

    text = (
        f"Hey darling! 🌙\n\n"
        f"I'm *Lunaris*, your cycle companion.\n"
        f"I promise not to be annoying — just here to look out for you 💛\n\n"
        f"📅 Today is day *{info['cycle_day']}* of your cycle\n"
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
    last_period, cycle_length = get_cycle_info(db, chat_id)
    today = date.today()
    cycle_day = get_cycle_day(last_period, today, cycle_length)
    info = get_phase_info(cycle_day, cycle_length)

    text = (
        f"🌙 *Lunaris — Main Menu*\n\n"
        f"📅 Day *{info['cycle_day']}* — {info['label']}\n"
        f"{info['description']}\n\n"
        f"What would you like to do, darling?"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)


async def _show_status(query, context):
    chat_id = query.message.chat_id
    db = get_db(context)
    last_period, cycle_length = get_cycle_info(db, chat_id)
    today = date.today()
    cycle_day = get_cycle_day(last_period, today, cycle_length)
    info = get_phase_info(cycle_day, cycle_length)

    text = (
        f"📊 *Your Status, Darling*\n\n"
        f"📅 Cycle day: *{info['cycle_day']}* of {cycle_length}\n"
        f"Phase: *{info['label']}*\n\n"
        f"{info['description']}"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=BACK_KEYBOARD)


async def _show_tip(query, context):
    chat_id = query.message.chat_id
    if not _check_ai_rate_limit(chat_id):
        await query.edit_message_text(
            "Easy there darling, let me catch my breath! Try again in a minute 💛",
            reply_markup=BACK_KEYBOARD,
        )
        return
    db = get_db(context)
    last_period, cycle_length = get_cycle_info(db, chat_id)
    today = date.today()
    cycle_day = get_cycle_day(last_period, today, cycle_length)
    phase = get_phase(cycle_day, cycle_length)
    recent_logs = db.get_user_recent_logs(chat_id, 3)

    await query.edit_message_text("Hold on darling, thinking of something good for you... 🤔")

    try:
        tip = await generate_tip(phase, cycle_day, recent_logs, model="claude-sonnet-4-6")
        await query.edit_message_text(
            f"💡 *Tip for You, Darling:*\n\n{tip}",
            parse_mode="Markdown",
            reply_markup=TIP_AGAIN_KEYBOARD,
        )
    except Exception as e:
        logger.error(f"AI tip generation failed: {e}")
        await query.edit_message_text(
            "Oops, my brain froze darling 😅 Try again in a sec!",
            reply_markup=BACK_KEYBOARD,
        )


async def _show_next(query, context):
    chat_id = query.message.chat_id
    db = get_db(context)
    last_period, cycle_length = get_cycle_info(db, chat_id)
    predictions = predict_dates(last_period, cycle_length)
    today = date.today()

    text = (
        f"🔮 *Upcoming Dates, Darling*\n\n"
        f"🩸 Next period: *{predictions['next_period']}* ({days_until(predictions['next_period'], today)} days)\n"
        f"⚡ Next PMS: *{predictions['next_pms']}* ({days_until(predictions['next_pms'], today)} days)\n"
        f"✨ Next ovulation: *{predictions['next_ovulation']}* ({days_until(predictions['next_ovulation'], today)} days)"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=BACK_KEYBOARD)


async def _show_phase(query, context):
    chat_id = query.message.chat_id
    db = get_db(context)
    last_period, cycle_length = get_cycle_info(db, chat_id)
    today = date.today()
    cycle_day = get_cycle_day(last_period, today, cycle_length)
    info = get_phase_info(cycle_day, cycle_length)

    text = PHASE_DETAILS.get(info["phase"], info["description"])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=BACK_KEYBOARD)


async def _show_history(query, context):
    chat_id = query.message.chat_id
    db = get_db(context)
    logs = db.get_user_recent_logs(chat_id, 10)

    if not logs:
        await query.edit_message_text(
            "📋 No notes yet, darling.\nUse /log to add one!",
            reply_markup=BACK_KEYBOARD,
        )
        return

    lines = ["📋 *Recent Notes, Darling:*\n"]
    for log in logs:
        phase_label = PHASE_LABELS.get(log["phase"], log["phase"])
        lines.append(f"📅 {log['date']} — {phase_label}\n📝 {_escape_markdown(log['note'])}\n")

    await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=BACK_KEYBOARD)


async def _show_settings(query, context):
    chat_id = query.message.chat_id
    db = get_db(context)
    config = db.get_user_config(chat_id)

    text = (
        f"⚙️ *Settings, Darling*\n\n"
        f"📏 Cycle length: *{config['cycle_length']}* days\n"
        f"📅 Last period start: *{config['last_period_date']}*\n\n"
        f"To change cycle length:\n`/settings 30`\n"
        f"To change period date:\n`/adjust 2026-02-25`"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=BACK_KEYBOARD)


async def _show_chat_intro(query, context):
    text = (
        "💬 *Chat with Lunaris*\n\n"
        "Just type anything, darling! No commands needed.\n"
        "Ask me about your cycle, symptoms, nutrition, exercise, "
        "hormones, sleep, skin — anything women's health related 💛\n\n"
        "I'll remember our conversation, and you can clear it anytime with /clearchat"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=BACK_KEYBOARD)


async def _show_period_confirm(query, context):
    text = (
        "🩸 *Period started today, darling?*\n\n"
        "I'll reset your cycle and update your cycle length.\n"
        "If it started on a different day, use:\n`/period 2026-02-25`"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=PERIOD_CONFIRM_KEYBOARD)


async def _do_period_today(query, context):
    chat_id = query.message.chat_id
    db = get_db(context)
    last_period, cycle_length = get_cycle_info(db, chat_id)
    period_date = date.today()

    actual_gap = (period_date - last_period).days
    if actual_gap > 0 and 18 <= actual_gap <= 45:
        new_cycle_length = round(actual_gap * 0.7 + cycle_length * 0.3)
        db.update_user_cycle_length(chat_id, new_cycle_length)
        length_msg = f"📏 Cycle length updated to *{new_cycle_length}* days (this one was {actual_gap} days)"
    elif actual_gap > 0:
        length_msg = f"This cycle was {actual_gap} days — a bit unusual, so I kept the length as is"
    else:
        length_msg = "Cycle length unchanged"

    db.update_user_last_period_date(chat_id, period_date.isoformat())

    text = (
        f"✅ Got it darling! New period started on *{period_date}*.\n\n"
        f"{length_msg}\n\n"
        f"Take it easy these next few days 💛 I'm here for you!"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=BACK_KEYBOARD)


# === Command handlers (still work alongside buttons) ===

@authorized
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db = get_db(context)
    last_period, cycle_length = get_cycle_info(db, chat_id)
    today = date.today()
    cycle_day = get_cycle_day(last_period, today, cycle_length)
    info = get_phase_info(cycle_day, cycle_length)

    text = (
        f"📊 *Your Status, Darling*\n\n"
        f"📅 Cycle day: *{info['cycle_day']}* of {cycle_length}\n"
        f"Phase: *{info['label']}*\n\n"
        f"{info['description']}"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)


@authorized
async def tip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not _check_ai_rate_limit(chat_id):
        await update.message.reply_text("Easy there darling, let me catch my breath! Try again in a minute 💛")
        return
    db = get_db(context)
    last_period, cycle_length = get_cycle_info(db, chat_id)
    today = date.today()
    cycle_day = get_cycle_day(last_period, today, cycle_length)
    phase = get_phase(cycle_day, cycle_length)
    recent_logs = db.get_user_recent_logs(chat_id, 3)

    await update.message.reply_text("Hold on darling, thinking... 🤔")

    try:
        tip = await generate_tip(phase, cycle_day, recent_logs, model="claude-sonnet-4-6")
        await update.message.reply_text(
            f"💡 *Tip for You, Darling:*\n\n{tip}",
            parse_mode="Markdown",
            reply_markup=TIP_AGAIN_KEYBOARD,
        )
    except Exception as e:
        logger.error(f"AI tip generation failed: {e}")
        await update.message.reply_text("Oops, my brain froze darling 😅 Try again in a sec!")


@authorized
async def period_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Record that period has started. Resets cycle and learns actual cycle length."""
    chat_id = update.effective_chat.id
    db = get_db(context)
    last_period, cycle_length = get_cycle_info(db, chat_id)

    if context.args:
        try:
            period_date = date.fromisoformat(context.args[0])
        except ValueError:
            await update.message.reply_text(
                "Wrong date format darling. Use this:\n"
                "`/period 2026-02-25`\n\n"
                "Or just type `/period` to log today 💛",
                parse_mode="Markdown",
            )
            return
        if period_date > date.today():
            await update.message.reply_text("That date is in the future, darling! Use a past or today's date.")
            return
    else:
        period_date = date.today()

    actual_gap = (period_date - last_period).days
    if actual_gap > 0 and 18 <= actual_gap <= 45:
        new_cycle_length = round(actual_gap * 0.7 + cycle_length * 0.3)
        db.update_user_cycle_length(chat_id, new_cycle_length)
        length_msg = f"📏 Cycle length updated to *{new_cycle_length}* days (this one was {actual_gap} days)"
    elif actual_gap > 0:
        length_msg = f"This cycle was {actual_gap} days — a bit unusual, so I kept the length as is"
    else:
        length_msg = "Cycle length unchanged"

    db.update_user_last_period_date(chat_id, period_date.isoformat())

    text = (
        f"✅ Got it darling! New period started on *{period_date}*.\n\n"
        f"{length_msg}\n\n"
        f"Take it easy these next few days 💛 I'm here for you!"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)


@authorized
async def log_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "📝 Write your note, darling:\n`/log feeling tired today`",
            parse_mode="Markdown",
        )
        return

    chat_id = update.effective_chat.id
    db = get_db(context)
    last_period, cycle_length = get_cycle_info(db, chat_id)
    today = date.today()
    cycle_day = get_cycle_day(last_period, today, cycle_length)
    phase = get_phase(cycle_day, cycle_length)
    note = " ".join(context.args)[:MAX_NOTE_LENGTH]

    db.add_user_log(chat_id, note, phase)
    await update.message.reply_text(
        f"✅ Logged, darling!\n📝 {_escape_markdown(note)}\n🌀 Phase: {PHASE_LABELS[phase]}",
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
            "📋 No notes yet, darling.\nUse /log to add one!",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    lines = ["📋 *Recent Notes, Darling:*\n"]
    for log in logs:
        phase_label = PHASE_LABELS.get(log["phase"], log["phase"])
        lines.append(f"📅 {log['date']} — {phase_label}\n📝 {_escape_markdown(log['note'])}\n")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)


@authorized
async def next_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db = get_db(context)
    last_period, cycle_length = get_cycle_info(db, chat_id)
    predictions = predict_dates(last_period, cycle_length)
    today = date.today()

    text = (
        f"🔮 *Upcoming Dates, Darling*\n\n"
        f"🩸 Next period: *{predictions['next_period']}* ({days_until(predictions['next_period'], today)} days)\n"
        f"⚡ Next PMS: *{predictions['next_pms']}* ({days_until(predictions['next_pms'], today)} days)\n"
        f"✨ Next ovulation: *{predictions['next_ovulation']}* ({days_until(predictions['next_ovulation'], today)} days)"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)


@authorized
async def phase_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db = get_db(context)
    last_period, cycle_length = get_cycle_info(db, chat_id)
    today = date.today()
    cycle_day = get_cycle_day(last_period, today, cycle_length)
    info = get_phase_info(cycle_day, cycle_length)

    text = PHASE_DETAILS.get(info["phase"], info["description"])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)


@authorized
async def adjust_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "📅 Enter the start date of your last period, darling:\n"
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
        f"✅ Period start date changed to *{new_date}*, darling!",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )


@authorized
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db = get_db(context)
    config = db.get_user_config(chat_id)

    if context.args:
        try:
            new_length = int(context.args[0])
            if not MIN_CYCLE_LENGTH <= new_length <= MAX_CYCLE_LENGTH:
                await update.message.reply_text(f"Cycle length must be between {MIN_CYCLE_LENGTH} and {MAX_CYCLE_LENGTH} days, darling.")
                return
            db.update_user_cycle_length(chat_id, new_length)
            await update.message.reply_text(
                f"✅ Cycle length changed to *{new_length}* days, darling!",
                parse_mode="Markdown",
                reply_markup=MAIN_KEYBOARD,
            )
            return
        except ValueError:
            await update.message.reply_text(
                "Enter a number darling. Example: `/settings 30`",
                parse_mode="Markdown",
            )
            return

    text = (
        f"⚙️ *Settings, Darling*\n\n"
        f"📏 Cycle length: *{config['cycle_length']}* days\n"
        f"📅 Last period start: *{config['last_period_date']}*\n\n"
        f"To change cycle length:\n`/settings 30`\n"
        f"To change period date:\n`/adjust 2026-02-25`"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)


# ── Free-form AI chat handler ──────────────────────────────────────

@authorized
async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any non-command text message as a free-form AI chat."""
    chat_id = update.effective_chat.id
    db = get_db(context)
    user_message = update.message.text[:MAX_CHAT_MESSAGE_LENGTH]

    if not _check_ai_rate_limit(chat_id):
        await update.message.reply_text(
            "Easy there darling, let me catch my breath! Try again in a minute 💛"
        )
        return

    # Get cycle context
    last_period, cycle_length = get_cycle_info(db, chat_id)
    today = date.today()
    cycle_day = get_cycle_day(last_period, today, cycle_length)
    phase = get_phase(cycle_day, cycle_length)
    recent_logs = db.get_user_recent_logs(chat_id, 3)

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
        )

        # Store both messages in history
        db.add_chat_message(chat_id, "user", user_message)
        db.add_chat_message(chat_id, "assistant", response)

        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Chat response generation failed: {e}")
        await update.message.reply_text(
            "Oops, my brain froze for a second darling 😅 Try again?"
        )
