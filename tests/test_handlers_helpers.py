import time
from datetime import date
from unittest.mock import AsyncMock, MagicMock

from src.handlers import (
    _escape_markdown,
    _check_ai_rate_limit,
    _ai_call_timestamps,
    get_cycle_info,
    whitelisted,
    authorized,
    authorized_callback,
    admin_only,
    AI_RATE_LIMIT,
)


# -- _escape_markdown --

class TestEscapeMarkdown:
    def test_asterisks(self):
        assert _escape_markdown("*bold*") == "\\*bold\\*"

    def test_underscores(self):
        assert _escape_markdown("_italic_") == "\\_italic\\_"

    def test_backticks(self):
        assert _escape_markdown("`code`") == "\\`code\\`"

    def test_brackets(self):
        assert _escape_markdown("[link]") == "\\[link]"

    def test_plain_text(self):
        assert _escape_markdown("hello world") == "hello world"

    def test_multiple_chars(self):
        assert _escape_markdown("*_`[") == "\\*\\_\\`\\["


# -- _check_ai_rate_limit --

class TestCheckAiRateLimit:
    def setup_method(self):
        _ai_call_timestamps.clear()

    def test_allows_first_call(self):
        assert _check_ai_rate_limit(100) is True

    def test_allows_up_to_limit(self):
        for _ in range(AI_RATE_LIMIT):
            assert _check_ai_rate_limit(100) is True

    def test_blocks_after_limit(self):
        for _ in range(AI_RATE_LIMIT):
            _check_ai_rate_limit(100)
        assert _check_ai_rate_limit(100) is False

    def test_per_user(self):
        for _ in range(AI_RATE_LIMIT):
            _check_ai_rate_limit(100)
        assert _check_ai_rate_limit(200) is True

    def test_expires_old_timestamps(self):
        for _ in range(AI_RATE_LIMIT):
            _check_ai_rate_limit(100)
        # Manually backdate all timestamps beyond the rate window
        _ai_call_timestamps[100] = [time.monotonic() - 120 for _ in range(AI_RATE_LIMIT)]
        assert _check_ai_rate_limit(100) is True


# -- get_cycle_info --

class TestGetCycleInfo:
    def test_returns_correct_tuple(self, db_with_user):
        last_period, cycle_length, period_duration = get_cycle_info(db_with_user, 1000)
        assert last_period == date(2026, 2, 1)
        assert cycle_length == 28
        assert period_duration == 5


# -- @whitelisted --

class TestWhitelistedDecorator:
    async def test_allows_authorized_user(self, make_update, mock_context):
        update = make_update(chat_id=1000)

        @whitelisted
        async def handler(update, context):
            return "ok"

        result = await handler(update, mock_context)
        assert result == "ok"

    async def test_blocks_unauthorized_user(self, make_update, mock_context):
        update = make_update(chat_id=9999)

        @whitelisted
        async def handler(update, context):
            return "ok"

        result = await handler(update, mock_context)
        assert result is None
        update.message.reply_text.assert_called_once()


# -- @authorized --

class TestAuthorizedDecorator:
    async def test_blocks_without_config(self, make_update, mock_context):
        db = mock_context.bot_data["db"]
        db.add_user(3000, added_by=1000)
        update = make_update(chat_id=3000)

        @authorized
        async def handler(update, context):
            return "ok"

        result = await handler(update, mock_context)
        assert result is None
        update.message.reply_text.assert_called_once()

    async def test_allows_with_config(self, make_update, mock_context):
        update = make_update(chat_id=1000)

        @authorized
        async def handler(update, context):
            return "ok"

        result = await handler(update, mock_context)
        assert result == "ok"


# -- @authorized_callback --

class TestAuthorizedCallbackDecorator:
    async def test_blocks_unauthorized(self, make_update, mock_context):
        update = make_update(chat_id=9999)

        @authorized_callback
        async def handler(update, context):
            return "ok"

        result = await handler(update, mock_context)
        assert result is None
        update.callback_query.answer.assert_called()


# -- @admin_only --

class TestAdminOnlyDecorator:
    async def test_allows_admin(self, make_update, mock_context):
        update = make_update(chat_id=1000)

        @admin_only
        async def handler(update, context):
            return "ok"

        result = await handler(update, mock_context)
        assert result == "ok"

    async def test_blocks_non_admin(self, make_update, mock_context):
        update = make_update(chat_id=2000)

        @admin_only
        async def handler(update, context):
            return "ok"

        result = await handler(update, mock_context)
        assert result is None
        update.message.reply_text.assert_called_once()
