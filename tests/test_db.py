from datetime import date

from src.db import Database


# -- Schema --

class TestSchema:
    def test_all_tables_exist(self, db):
        conn = db._get_conn()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {r["name"] for r in tables}
        expected = {
            "cycle_config", "mood_logs",
            "users", "user_cycle_config", "user_mood_logs", "chat_history",
            "period_logs",
        }
        assert expected.issubset(table_names)

    def test_wal_mode(self, db):
        result = db._get_conn().execute("PRAGMA journal_mode").fetchone()
        assert result[0] == "wal"

    def test_foreign_keys_enabled(self, db):
        result = db._get_conn().execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1

    def test_user_cycle_config_has_new_columns(self, db):
        conn = db._get_conn()
        cols = conn.execute("PRAGMA table_info(user_cycle_config)").fetchall()
        col_names = {c["name"] for c in cols}
        assert "period_duration" in col_names
        assert "year_of_birth" in col_names


# -- User management --

class TestUserManagement:
    def test_add_user(self, db):
        db.add_user(100, added_by=1)
        assert db.is_user_authorized(100)

    def test_reactivate_removed_user(self, db):
        db.add_user(100, added_by=1)
        db.remove_user(100)
        assert not db.is_user_authorized(100)
        db.add_user(100, added_by=1)
        assert db.is_user_authorized(100)

    def test_remove_user(self, db):
        db.add_user(100, added_by=1)
        db.remove_user(100)
        assert not db.is_user_authorized(100)

    def test_is_admin_true(self, db):
        db.bootstrap_admin(100, 28, "2026-02-01")
        assert db.is_admin(100)

    def test_is_admin_false_for_regular_user(self, db):
        db.add_user(100, added_by=1)
        assert not db.is_admin(100)

    def test_is_user_authorized_true(self, db):
        db.add_user(100, added_by=1)
        assert db.is_user_authorized(100)

    def test_is_user_authorized_false_unknown(self, db):
        assert not db.is_user_authorized(9999)

    def test_get_all_active_users(self, db):
        db.add_user(100, added_by=1)
        db.add_user(200, added_by=1)
        db.remove_user(200)
        active = db.get_all_active_users()
        ids = [u["chat_id"] for u in active]
        assert 100 in ids
        assert 200 not in ids

    def test_get_all_whitelisted_users(self, db):
        db.add_user(100, added_by=1)
        db.add_user(200, added_by=1)
        users = db.get_all_whitelisted_users()
        assert len(users) == 2


# -- Cycle config --

class TestCycleConfig:
    def test_has_config_true(self, db):
        db.add_user(100, added_by=1)
        db.upsert_user_config(100, 28, "2026-02-01")
        assert db.user_has_config(100)

    def test_has_config_false(self, db):
        db.add_user(100, added_by=1)
        assert not db.user_has_config(100)

    def test_upsert_creates_new(self, db):
        db.add_user(100, added_by=1)
        db.upsert_user_config(100, 28, "2026-02-01")
        config = db.get_user_config(100)
        assert config["cycle_length"] == 28
        assert config["last_period_date"] == "2026-02-01"

    def test_upsert_updates_existing(self, db):
        db.add_user(100, added_by=1)
        db.upsert_user_config(100, 28, "2026-02-01")
        db.upsert_user_config(100, 30, "2026-02-10")
        config = db.get_user_config(100)
        assert config["cycle_length"] == 30
        assert config["last_period_date"] == "2026-02-10"

    def test_update_cycle_length(self, db):
        db.add_user(100, added_by=1)
        db.upsert_user_config(100, 28, "2026-02-01")
        db.update_user_cycle_length(100, 32)
        assert db.get_user_config(100)["cycle_length"] == 32

    def test_update_last_period_date(self, db):
        db.add_user(100, added_by=1)
        db.upsert_user_config(100, 28, "2026-02-01")
        db.update_user_last_period_date(100, "2026-02-20")
        assert db.get_user_config(100)["last_period_date"] == "2026-02-20"

    def test_get_user_config_none_for_unconfigured(self, db):
        assert db.get_user_config(9999) is None

    def test_upsert_with_period_duration(self, db):
        db.add_user(100, added_by=1)
        db.upsert_user_config(100, 28, "2026-02-01", period_duration=4)
        config = db.get_user_config(100)
        assert config["period_duration"] == 4

    def test_upsert_with_year_of_birth(self, db):
        db.add_user(100, added_by=1)
        db.upsert_user_config(100, 28, "2026-02-01", year_of_birth=1995)
        config = db.get_user_config(100)
        assert config["year_of_birth"] == 1995

    def test_get_user_config_returns_new_fields(self, db):
        db.add_user(100, added_by=1)
        db.upsert_user_config(100, 28, "2026-02-01", period_duration=6, year_of_birth=1990)
        config = db.get_user_config(100)
        assert config["period_duration"] == 6
        assert config["year_of_birth"] == 1990

    def test_update_period_duration(self, db):
        db.add_user(100, added_by=1)
        db.upsert_user_config(100, 28, "2026-02-01")
        db.update_user_period_duration(100, 3)
        assert db.get_user_config(100)["period_duration"] == 3

    def test_update_year_of_birth(self, db):
        db.add_user(100, added_by=1)
        db.upsert_user_config(100, 28, "2026-02-01")
        db.update_user_year_of_birth(100, 1998)
        assert db.get_user_config(100)["year_of_birth"] == 1998

    def test_default_period_duration(self, db):
        db.add_user(100, added_by=1)
        db.upsert_user_config(100, 28, "2026-02-01")
        config = db.get_user_config(100)
        assert config["period_duration"] == 5

    def test_default_year_of_birth_is_none(self, db):
        db.add_user(100, added_by=1)
        db.upsert_user_config(100, 28, "2026-02-01")
        config = db.get_user_config(100)
        assert config["year_of_birth"] is None


# -- Period logs --

class TestPeriodLogs:
    def test_add_and_get_history(self, db):
        db.add_user(100, added_by=1)
        db.add_period_log(100, "2026-01-01")
        db.add_period_log(100, "2026-01-29")
        history = db.get_period_history(100)
        assert len(history) == 2
        # Most recent first
        assert history[0] == "2026-01-29"
        assert history[1] == "2026-01-01"

    def test_history_limit(self, db):
        db.add_user(100, added_by=1)
        for i in range(10):
            db.add_period_log(100, f"2026-{i+1:02d}-01")
        history = db.get_period_history(100, limit=3)
        assert len(history) == 3

    def test_computed_cycle_length_basic(self, db):
        db.add_user(100, added_by=1)
        db.add_period_log(100, "2026-01-01")
        db.add_period_log(100, "2026-01-29")
        db.add_period_log(100, "2026-02-26")
        result = db.get_computed_cycle_length(100)
        assert result == 28  # median of [28, 28]

    def test_computed_cycle_length_none_with_single_entry(self, db):
        db.add_user(100, added_by=1)
        db.add_period_log(100, "2026-01-01")
        assert db.get_computed_cycle_length(100) is None

    def test_computed_cycle_length_none_with_no_entries(self, db):
        db.add_user(100, added_by=1)
        assert db.get_computed_cycle_length(100) is None

    def test_computed_cycle_length_filters_outliers(self, db):
        db.add_user(100, added_by=1)
        db.add_period_log(100, "2026-01-01")
        db.add_period_log(100, "2026-01-29")  # 28-day gap
        db.add_period_log(100, "2026-02-26")  # 28-day gap
        db.add_period_log(100, "2026-06-01")  # 95-day gap (outlier)
        result = db.get_computed_cycle_length(100)
        assert result == 28  # outlier filtered out

    def test_per_user_isolation(self, db):
        db.add_user(100, added_by=1)
        db.add_user(200, added_by=1)
        db.add_period_log(100, "2026-01-01")
        db.add_period_log(200, "2026-02-01")
        assert len(db.get_period_history(100)) == 1
        assert len(db.get_period_history(200)) == 1


# -- Mood logs --

class TestMoodLogs:
    def test_add_and_get_recent(self, db):
        db.add_user(100, added_by=1)
        db.add_user_log(100, "feeling great", "follicular", date(2026, 2, 10))
        logs = db.get_user_recent_logs(100)
        assert len(logs) == 1
        assert logs[0]["note"] == "feeling great"

    def test_limit(self, db):
        db.add_user(100, added_by=1)
        for i in range(5):
            db.add_user_log(100, f"note {i}", "follicular")
        logs = db.get_user_recent_logs(100, limit=3)
        assert len(logs) == 3

    def test_filter_by_date(self, db):
        db.add_user(100, added_by=1)
        db.add_user_log(100, "note a", "follicular", date(2026, 2, 10))
        db.add_user_log(100, "note b", "follicular", date(2026, 2, 11))
        logs = db.get_user_logs_for_date(100, date(2026, 2, 10))
        assert len(logs) == 1
        assert logs[0]["note"] == "note a"

    def test_per_user_isolation(self, db):
        db.add_user(100, added_by=1)
        db.add_user(200, added_by=1)
        db.add_user_log(100, "user 100 note", "follicular")
        db.add_user_log(200, "user 200 note", "follicular")
        logs_100 = db.get_user_recent_logs(100)
        logs_200 = db.get_user_recent_logs(200)
        assert len(logs_100) == 1
        assert logs_100[0]["note"] == "user 100 note"
        assert len(logs_200) == 1
        assert logs_200[0]["note"] == "user 200 note"


# -- Chat history --

class TestChatHistory:
    def test_add_and_get(self, db):
        db.add_user(100, added_by=1)
        db.add_chat_message(100, "user", "hello")
        db.add_chat_message(100, "assistant", "hi darling")
        history = db.get_chat_history(100)
        assert len(history) == 2

    def test_chronological_order(self, db):
        db.add_user(100, added_by=1)
        db.add_chat_message(100, "user", "first")
        db.add_chat_message(100, "assistant", "second")
        history = db.get_chat_history(100)
        assert history[0]["content"] == "first"
        assert history[1]["content"] == "second"

    def test_clear(self, db):
        db.add_user(100, added_by=1)
        db.add_chat_message(100, "user", "hello")
        db.clear_chat_history(100)
        assert db.get_chat_history(100) == []

    def test_prune(self, db):
        db.add_user(100, added_by=1)
        for i in range(10):
            db.add_chat_message(100, "user", f"msg {i}")
        db.prune_chat_history(100, keep=5)
        history = db.get_chat_history(100)
        assert len(history) == 5
        assert history[-1]["content"] == "msg 9"

    def test_per_user_isolation(self, db):
        db.add_user(100, added_by=1)
        db.add_user(200, added_by=1)
        db.add_chat_message(100, "user", "user 100 msg")
        db.add_chat_message(200, "user", "user 200 msg")
        assert len(db.get_chat_history(100)) == 1
        assert len(db.get_chat_history(200)) == 1


# -- Bootstrap --

class TestBootstrap:
    def test_creates_user_and_config(self, db):
        db.bootstrap_admin(100, 28, "2026-02-01")
        assert db.is_admin(100)
        assert db.user_has_config(100)
        config = db.get_user_config(100)
        assert config["cycle_length"] == 28

    def test_idempotent(self, db):
        db.bootstrap_admin(100, 28, "2026-02-01")
        db.bootstrap_admin(100, 28, "2026-02-01")
        assert db.is_admin(100)
        config = db.get_user_config(100)
        assert config["cycle_length"] == 28

    def test_migrates_legacy_cycle_config(self, db):
        with db._get_conn() as conn:
            conn.execute(
                "INSERT INTO cycle_config (id, cycle_length, last_period_date) VALUES (1, 30, '2026-01-15')"
            )
        db.bootstrap_admin(100, 28, "2026-02-01")
        config = db.get_user_config(100)
        assert config["cycle_length"] == 30
        assert config["last_period_date"] == "2026-01-15"

    def test_migrates_legacy_mood_logs(self, db):
        with db._get_conn() as conn:
            conn.execute(
                "INSERT INTO mood_logs (date, note, phase) VALUES ('2026-02-01', 'legacy note', 'follicular')"
            )
        db.bootstrap_admin(100, 28, "2026-02-01")
        logs = db.get_user_recent_logs(100)
        assert len(logs) == 1
        assert logs[0]["note"] == "legacy note"
