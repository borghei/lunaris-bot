from unittest.mock import AsyncMock, MagicMock, patch

from src.ai import (
    _extract_text,
    _format_logs_context,
    generate_tip,
    generate_reminder,
    generate_chat_response,
)


# ── _extract_text ────────────────────────────────────────────────

class TestExtractText:
    def test_with_content(self, mock_anthropic_response):
        response = mock_anthropic_response("Hello darling!")
        assert _extract_text(response) == "Hello darling!"

    def test_empty_content_fallback(self):
        response = MagicMock()
        response.content = []
        result = _extract_text(response)
        assert "try again" in result.lower()


# ── _format_logs_context ─────────────────────────────────────────

class TestFormatLogsContext:
    def test_with_logs(self):
        logs = [{"note": "feeling tired"}, {"note": "cramps"}]
        result = _format_logs_context(logs)
        assert "feeling tired" in result
        assert "cramps" in result

    def test_empty_logs(self):
        assert _format_logs_context([]) == ""

    def test_none_logs(self):
        assert _format_logs_context(None) == ""

    def test_truncation_to_3(self):
        logs = [{"note": f"note {i}"} for i in range(5)]
        result = _format_logs_context(logs)
        assert "note 0" in result
        assert "note 2" in result
        assert "note 3" not in result


# ── generate_tip ─────────────────────────────────────────────────

class TestGenerateTip:
    async def test_calls_api(self, mock_anthropic_response):
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=mock_anthropic_response("Stay warm darling!")
        )
        with patch("src.ai.client", mock_client):
            result = await generate_tip("menstruation", 3)
        assert result == "Stay warm darling!"
        mock_client.messages.create.assert_called_once()

    async def test_passes_logs_in_prompt(self, mock_anthropic_response):
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=mock_anthropic_response("tip")
        )
        logs = [{"note": "tired today"}]
        with patch("src.ai.client", mock_client):
            await generate_tip("pms", 25, recent_logs=logs)
        call_args = mock_client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert "tired today" in user_msg

    async def test_uses_specified_model(self, mock_anthropic_response):
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=mock_anthropic_response("tip")
        )
        with patch("src.ai.client", mock_client):
            await generate_tip("follicular", 10, model="claude-haiku-4-5-20251001")
        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["model"] == "claude-haiku-4-5-20251001"


# ── generate_reminder ────────────────────────────────────────────

class TestGenerateReminder:
    async def test_uses_haiku_model(self, mock_anthropic_response):
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=mock_anthropic_response("Good morning!")
        )
        with patch("src.ai.client", mock_client):
            await generate_reminder("pms", 25)
        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["model"] == "claude-haiku-4-5-20251001"

    async def test_pms_specific_prompt(self, mock_anthropic_response):
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=mock_anthropic_response("cheer up!")
        )
        with patch("src.ai.client", mock_client):
            await generate_reminder("pms", 25)
        call_args = mock_client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert "PMS" in user_msg


# ── generate_chat_response ───────────────────────────────────────

class TestGenerateChatResponse:
    async def test_appends_user_message(self, mock_anthropic_response):
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=mock_anthropic_response("reply")
        )
        with patch("src.ai.client", mock_client):
            await generate_chat_response(
                "How are you?", [], cycle_day=5, phase="menstruation"
            )
        call_args = mock_client.messages.create.call_args
        messages = call_args.kwargs["messages"]
        assert messages[-1]["content"] == "How are you?"

    async def test_includes_cycle_context_in_system(self, mock_anthropic_response):
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=mock_anthropic_response("reply")
        )
        with patch("src.ai.client", mock_client):
            await generate_chat_response(
                "hi", [], cycle_day=5, phase="menstruation"
            )
        call_args = mock_client.messages.create.call_args
        system = call_args.kwargs["system"]
        assert "Day 5" in system
        assert "menstruation" in system

    async def test_handles_no_cycle_context(self, mock_anthropic_response):
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=mock_anthropic_response("reply")
        )
        with patch("src.ai.client", mock_client):
            result = await generate_chat_response("hi", [])
        assert result == "reply"
