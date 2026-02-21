import logging
from datetime import date

from telegram import BotCommand, BotCommandScopeChat
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from config.settings import (
    TELEGRAM_BOT_TOKEN,
    ADMIN_CHAT_ID,
    CYCLE_LENGTH,
    LAST_PERIOD_START,
    DB_PATH,
    LOGS_DIR,
)
from src.db import Database
from src.handlers import (
    start_command,
    status_command,
    tip_command,
    period_command,
    log_command,
    history_command,
    next_command,
    phase_command,
    adjust_command,
    settings_command,
    button_handler,
    adduser_command,
    removeuser_command,
    users_command,
    setup_command,
    clearchat_command,
    chat_handler,
    about_command,
)
from src.scheduler import setup_scheduler

from logging.handlers import RotatingFileHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        RotatingFileHandler(
            LOGS_DIR / "lunaris.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


async def post_init(application):
    """Register bot commands menu on startup.

    Default menu shows regular commands only.
    Admin gets an additional scoped menu with admin commands.
    """
    user_commands = [
        BotCommand("start", "Welcome & main menu"),
        BotCommand("status", "Current cycle day & phase"),
        BotCommand("tip", "AI-generated caring tip"),
        BotCommand("period", "Log period start"),
        BotCommand("log", "Log mood or symptom"),
        BotCommand("history", "Recent logs"),
        BotCommand("next", "Predicted dates"),
        BotCommand("phase", "Detailed phase info"),
        BotCommand("adjust", "Update last period date"),
        BotCommand("settings", "View/update cycle length"),
        BotCommand("setup", "Set up your cycle info"),
        BotCommand("clearchat", "Clear AI chat history"),
        BotCommand("about", "About this bot"),
    ]
    admin_commands = user_commands + [
        BotCommand("adduser", "Whitelist a user"),
        BotCommand("removeuser", "Remove a user"),
        BotCommand("users", "List whitelisted users"),
    ]

    # Default menu for all users — no admin commands visible
    await application.bot.set_my_commands(user_commands)

    # Admin-only menu — includes admin commands
    await application.bot.set_my_commands(
        admin_commands,
        scope=BotCommandScopeChat(chat_id=ADMIN_CHAT_ID),
    )


def create_app() -> None:
    """Create and run the bot application."""
    logger.info("Starting Lunaris bot...")

    # Initialize database and bootstrap admin
    db = Database(DB_PATH)
    db.bootstrap_admin(ADMIN_CHAT_ID, CYCLE_LENGTH, LAST_PERIOD_START)
    logger.info(f"Admin {ADMIN_CHAT_ID} bootstrapped (legacy data migrated if needed)")

    # Build application
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    app.bot_data["db"] = db

    # Register command handlers
    commands = [
        ("start", start_command),
        ("status", status_command),
        ("tip", tip_command),
        ("period", period_command),
        ("log", log_command),
        ("history", history_command),
        ("next", next_command),
        ("phase", phase_command),
        ("adjust", adjust_command),
        ("settings", settings_command),
        # Admin commands
        ("adduser", adduser_command),
        ("removeuser", removeuser_command),
        ("users", users_command),
        # New user commands
        ("setup", setup_command),
        ("clearchat", clearchat_command),
        ("about", about_command),
    ]
    for name, handler in commands:
        app.add_handler(CommandHandler(name, handler))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Free-form AI chat — registered LAST so it only catches non-command text
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))

    # Set up scheduler
    scheduler = setup_scheduler(app)
    scheduler.start()
    logger.info("Scheduler started.")

    # Run the bot
    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)
