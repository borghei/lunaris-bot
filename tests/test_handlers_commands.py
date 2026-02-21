import time
from datetime import date
from unittest.mock import AsyncMock, patch

from config.settings import VERSION
from src.handlers import (
    setup_command,
    start_command,
    log_command,
    adduser_command,
    removeuser_command,
    settings_command,
    period_command,
    clearchat_command,
    chat_handler,
    about_command,
    _ai_call_timestamps,
    AI_RATE_LIMIT,
)


# ── /setup ───────────────────────────────────────────────────────

class TestSetupCommand:
    async def test_no_args(self, make_update, mock_context):
        update = make_update(chat_id=1000)
        mock_context.args = []
        await setup_command(update, mock_context)
        reply = update.message.reply_text.call_args[0][0]
        assert "Usage" in reply or "setup" in reply.lower()

    async def test_invalid_length(self, make_update, mock_context):
        update = make_update(chat_id=1000)
        mock_context.args = ["abc", "2026-02-15"]
        await setup_command(update, mock_context)
        reply = update.message.reply_text.call_args[0][0]
        assert "number" in reply.lower()

    async def test_out_of_range(self, make_update, mock_context):
        update = make_update(chat_id=1000)
        mock_context.args = ["10", "2026-02-15"]
        await setup_command(update, mock_context)
        reply = update.message.reply_text.call_args[0][0]
        assert "between" in reply.lower()

    async def test_invalid_date(self, make_update, mock_context):
        update = make_update(chat_id=1000)
        mock_context.args = ["28", "not-a-date"]
        await setup_command(update, mock_context)
        reply = update.message.reply_text.call_args[0][0]
        assert "format" in reply.lower()

    async def test_future_date(self, make_update, mock_context):
        update = make_update(chat_id=1000)
        mock_context.args = ["28", "2099-01-01"]
        await setup_command(update, mock_context)
        reply = update.message.reply_text.call_args[0][0]
        assert "future" in reply.lower()

    async def test_success(self, make_update, mock_context):
        update = make_update(chat_id=1000)
        mock_context.args = ["28", "2026-02-01"]
        await setup_command(update, mock_context)
        reply = update.message.reply_text.call_args[0][0]
        assert "All set" in reply


# ── /start ───────────────────────────────────────────────────────

class TestStartCommand:
    async def test_without_config_shows_setup(self, make_update, mock_context):
        db = mock_context.bot_data["db"]
        db.add_user(3000, added_by=1000)
        update = make_update(chat_id=3000)
        await start_command(update, mock_context)
        reply = update.message.reply_text.call_args[0][0]
        assert "setup" in reply.lower()

    async def test_with_config_shows_menu(self, make_update, mock_context):
        update = make_update(chat_id=1000)
        await start_command(update, mock_context)
        reply = update.message.reply_text.call_args[0][0]
        assert "Lunaris" in reply


# ── /log ─────────────────────────────────────────────────────────

class TestLogCommand:
    async def test_no_args(self, make_update, mock_context):
        update = make_update(chat_id=1000)
        mock_context.args = []
        await log_command(update, mock_context)
        reply = update.message.reply_text.call_args[0][0]
        assert "note" in reply.lower() or "Write" in reply

    async def test_success(self, make_update, mock_context):
        update = make_update(chat_id=1000)
        mock_context.args = ["feeling", "tired"]
        await log_command(update, mock_context)
        reply = update.message.reply_text.call_args[0][0]
        assert "Logged" in reply


# ── /adduser ─────────────────────────────────────────────────────

class TestAdduserCommand:
    async def test_no_args(self, make_update, mock_context):
        update = make_update(chat_id=1000)
        mock_context.args = []
        await adduser_command(update, mock_context)
        reply = update.message.reply_text.call_args[0][0]
        assert "Usage" in reply

    async def test_success(self, make_update, mock_context):
        update = make_update(chat_id=1000)
        mock_context.args = ["5000"]
        await adduser_command(update, mock_context)
        reply = update.message.reply_text.call_args[0][0]
        assert "whitelisted" in reply.lower()


# ── /removeuser ──────────────────────────────────────────────────

class TestRemoveuserCommand:
    async def test_cannot_remove_admin(self, make_update, mock_context):
        update = make_update(chat_id=1000)
        mock_context.args = ["1000"]
        await removeuser_command(update, mock_context)
        reply = update.message.reply_text.call_args[0][0]
        assert "admin" in reply.lower()


# ── /settings ────────────────────────────────────────────────────

class TestSettingsCommand:
    async def test_view(self, make_update, mock_context):
        update = make_update(chat_id=1000)
        mock_context.args = []
        await settings_command(update, mock_context)
        reply = update.message.reply_text.call_args[0][0]
        assert "28" in reply

    async def test_update(self, make_update, mock_context):
        update = make_update(chat_id=1000)
        mock_context.args = ["30"]
        await settings_command(update, mock_context)
        reply = update.message.reply_text.call_args[0][0]
        assert "30" in reply


# ── /period ──────────────────────────────────────────────────────

class TestPeriodCommand:
    async def test_no_args_logs_today(self, make_update, mock_context):
        update = make_update(chat_id=1000)
        mock_context.args = []
        await period_command(update, mock_context)
        reply = update.message.reply_text.call_args[0][0]
        assert "Got it" in reply

    async def test_cycle_length_learning(self, make_update, mock_context):
        db = mock_context.bot_data["db"]
        # Set last period to 25 days ago (within valid 18-45 range)
        db.update_user_last_period_date(1000, date(2026, 1, 27).isoformat())
        update = make_update(chat_id=1000)
        mock_context.args = [date.today().isoformat()]
        await period_command(update, mock_context)
        reply = update.message.reply_text.call_args[0][0]
        assert "updated" in reply.lower()


# ── /clearchat ───────────────────────────────────────────────────

class TestClearchatCommand:
    async def test_clears_history(self, make_update, mock_context):
        db = mock_context.bot_data["db"]
        db.add_chat_message(1000, "user", "hello")
        update = make_update(chat_id=1000)
        await clearchat_command(update, mock_context)
        assert db.get_chat_history(1000) == []
        reply = update.message.reply_text.call_args[0][0]
        assert "cleared" in reply.lower()


# ── /about ───────────────────────────────────────────────────────

class TestAboutCommand:
    async def test_shows_version(self, make_update, mock_context):
        update = make_update(chat_id=1000)
        await about_command(update, mock_context)
        reply = update.message.reply_text.call_args[0][0]
        assert VERSION in reply

    async def test_shows_author(self, make_update, mock_context):
        update = make_update(chat_id=1000)
        await about_command(update, mock_context)
        reply = update.message.reply_text.call_args[0][0]
        assert "borghei" in reply


# ── chat_handler ─────────────────────────────────────────────────

class TestChatHandler:
    def setup_method(self):
        _ai_call_timestamps.clear()

    async def test_stores_messages(self, make_update, mock_context):
        update = make_update(chat_id=1000, text="How are you?")
        with patch("src.handlers.generate_chat_response", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = "I'm great darling!"
            await chat_handler(update, mock_context)
        db = mock_context.bot_data["db"]
        history = db.get_chat_history(1000)
        assert any(m["content"] == "How are you?" for m in history)
        assert any(m["content"] == "I'm great darling!" for m in history)

    async def test_rate_limited(self, make_update, mock_context):
        for _ in range(AI_RATE_LIMIT):
            _ai_call_timestamps[1000].append(time.monotonic())
        update = make_update(chat_id=1000, text="hello")
        await chat_handler(update, mock_context)
        reply = update.message.reply_text.call_args[0][0]
        assert "breath" in reply.lower()
