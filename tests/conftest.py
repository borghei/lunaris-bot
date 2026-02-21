import os

# Set test environment variables before any source imports
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-api-key")
os.environ.setdefault("ADMIN_CHAT_ID", "1000")

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.db import Database


@pytest.fixture
def db(tmp_path):
    """Fresh Database instance using temp file (real SQLite, WAL mode)."""
    return Database(tmp_path / "test.db")


@pytest.fixture
def db_with_user(db):
    """Pre-populated: admin (chat_id=1000) + regular user (chat_id=2000) with configs."""
    with db._get_conn() as conn:
        conn.execute(
            "INSERT INTO users (chat_id, is_admin, is_active) VALUES (?, 1, 1)",
            (1000,),
        )
    db.upsert_user_config(1000, 28, "2026-02-01", period_duration=5)

    db.add_user(2000, added_by=1000)
    db.upsert_user_config(2000, 30, "2026-02-05", period_duration=4)
    return db


@pytest.fixture
def mock_anthropic_response():
    """Factory returning mock Anthropic response with given text."""
    def _factory(text="Test response"):
        response = MagicMock()
        block = MagicMock()
        block.text = text
        response.content = [block]
        return response
    return _factory


@pytest.fixture
def mock_context(db_with_user):
    """Mock Telegram context with bot_data['db'] pointing to test DB."""
    context = MagicMock()
    context.bot_data = {"db": db_with_user}
    context.args = []
    context.bot = AsyncMock()
    return context


@pytest.fixture
def make_update():
    """Factory creating mock Telegram Update with given chat_id and text."""
    def _factory(chat_id=1000, text="/start"):
        update = MagicMock()
        update.effective_chat.id = chat_id
        update.message = MagicMock()
        update.message.text = text
        update.message.reply_text = AsyncMock()
        update.callback_query = MagicMock()
        update.callback_query.answer = AsyncMock()
        update.callback_query.data = ""
        update.callback_query.message.chat_id = chat_id
        update.callback_query.edit_message_text = AsyncMock()
        return update
    return _factory
