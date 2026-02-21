from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from src.scheduler import send_daily_reminder, setup_scheduler


class TestSendDailyReminder:
    async def test_sends_reminder_during_pms(self, db_with_user):
        app = MagicMock()
        app.bot_data = {"db": db_with_user}
        app.bot = AsyncMock()

        # Set user 1000 to PMS phase: last period Jan 28, today Feb 21 → day 25 = PMS
        db_with_user.update_user_last_period_date(1000, "2026-01-28")

        with patch("src.scheduler.date") as mock_date, \
             patch("src.scheduler.generate_reminder", new_callable=AsyncMock) as mock_ai:
            mock_date.today.return_value = date(2026, 2, 21)
            mock_date.fromisoformat = date.fromisoformat
            mock_ai.return_value = "Take care darling!"
            await send_daily_reminder(app)

        app.bot.send_message.assert_called()

    async def test_skips_follicular_phase(self, db_with_user):
        app = MagicMock()
        app.bot_data = {"db": db_with_user}
        app.bot = AsyncMock()

        # Set user 1000 to follicular: last period Feb 13, today Feb 20 → day 8
        db_with_user.update_user_last_period_date(1000, "2026-02-13")
        # Set user 2000 to follicular too
        db_with_user.update_user_last_period_date(2000, "2026-02-13")

        with patch("src.scheduler.date") as mock_date:
            mock_date.today.return_value = date(2026, 2, 20)
            mock_date.fromisoformat = date.fromisoformat
            await send_daily_reminder(app)

        app.bot.send_message.assert_not_called()

    async def test_skips_users_without_config(self, db_with_user):
        app = MagicMock()
        app.bot_data = {"db": db_with_user}
        app.bot = AsyncMock()

        # Add user without config
        db_with_user.add_user(3000, added_by=1000)

        # Put configured users in follicular (no reminder) so only user 3000 is relevant
        db_with_user.update_user_last_period_date(1000, "2026-02-13")
        db_with_user.update_user_last_period_date(2000, "2026-02-13")

        with patch("src.scheduler.date") as mock_date:
            mock_date.today.return_value = date(2026, 2, 20)
            mock_date.fromisoformat = date.fromisoformat
            # Should not raise even though user 3000 has no config
            await send_daily_reminder(app)

        app.bot.send_message.assert_not_called()

    async def test_handles_ai_error(self, db_with_user):
        app = MagicMock()
        app.bot_data = {"db": db_with_user}
        app.bot = AsyncMock()

        # Set user 1000 to PMS phase
        db_with_user.update_user_last_period_date(1000, "2026-01-28")

        with patch("src.scheduler.date") as mock_date, \
             patch("src.scheduler.generate_reminder", new_callable=AsyncMock) as mock_ai:
            mock_date.today.return_value = date(2026, 2, 21)
            mock_date.fromisoformat = date.fromisoformat
            mock_ai.side_effect = Exception("API error")
            # Should not raise
            await send_daily_reminder(app)

    async def test_sends_on_ovulation_day(self, db_with_user):
        app = MagicMock()
        app.bot_data = {"db": db_with_user}
        app.bot = AsyncMock()

        # Set user 1000 to ovulation: last period Feb 7, today Feb 20 → day 14
        db_with_user.update_user_last_period_date(1000, "2026-02-07")
        # Put user 2000 in follicular to avoid extra calls
        db_with_user.update_user_last_period_date(2000, "2026-02-13")

        with patch("src.scheduler.date") as mock_date, \
             patch("src.scheduler.generate_reminder", new_callable=AsyncMock) as mock_ai:
            mock_date.today.return_value = date(2026, 2, 20)
            mock_date.fromisoformat = date.fromisoformat
            mock_ai.return_value = "You're glowing!"
            await send_daily_reminder(app)

        app.bot.send_message.assert_called()


class TestSetupScheduler:
    def test_creates_job(self):
        app = MagicMock()
        scheduler = setup_scheduler(app)
        jobs = scheduler.get_jobs()
        assert any(j.id == "daily_reminder" for j in jobs)
