import sqlite3
from datetime import date, datetime
from pathlib import Path


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        return self._conn

    def _init_db(self):
        with self._get_conn() as conn:
            # Legacy tables (kept for migration)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cycle_config (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    cycle_length INTEGER NOT NULL DEFAULT 28,
                    last_period_date TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mood_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    note TEXT NOT NULL,
                    phase TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

            # New multi-user tables
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    chat_id INTEGER PRIMARY KEY,
                    added_by INTEGER,
                    is_admin INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_cycle_config (
                    chat_id INTEGER PRIMARY KEY,
                    cycle_length INTEGER NOT NULL DEFAULT 28,
                    last_period_date TEXT NOT NULL,
                    FOREIGN KEY (chat_id) REFERENCES users(chat_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_mood_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    note TEXT NOT NULL,
                    phase TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (chat_id) REFERENCES users(chat_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (chat_id) REFERENCES users(chat_id)
                )
            """)

            # Indexes for per-user queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_mood_logs_chat
                ON user_mood_logs(chat_id, created_at DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_history_chat
                ON chat_history(chat_id, id DESC)
            """)

    # ── Admin bootstrap & legacy migration ──────────────────────────

    def bootstrap_admin(self, admin_id: int, cycle_length: int, last_period_start: str):
        """Ensure admin exists in users table and migrate legacy data if needed."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT 1 FROM users WHERE chat_id = ?", (admin_id,)).fetchone()
            if not row:
                conn.execute(
                    "INSERT INTO users (chat_id, is_admin) VALUES (?, 1)",
                    (admin_id,),
                )
            else:
                conn.execute(
                    "UPDATE users SET is_admin = 1, is_active = 1 WHERE chat_id = ?",
                    (admin_id,),
                )

        self._migrate_legacy_data(admin_id, cycle_length, last_period_start)

    def _migrate_legacy_data(self, admin_id: int, default_cycle_length: int, default_last_period: str):
        """Copy old singleton tables into per-user tables for the admin."""
        with self._get_conn() as conn:
            # Migrate cycle_config
            has_user_config = conn.execute(
                "SELECT 1 FROM user_cycle_config WHERE chat_id = ?", (admin_id,)
            ).fetchone()
            if not has_user_config:
                legacy = conn.execute("SELECT * FROM cycle_config WHERE id = 1").fetchone()
                if legacy:
                    conn.execute(
                        "INSERT INTO user_cycle_config (chat_id, cycle_length, last_period_date) VALUES (?, ?, ?)",
                        (admin_id, legacy["cycle_length"], legacy["last_period_date"]),
                    )
                else:
                    conn.execute(
                        "INSERT INTO user_cycle_config (chat_id, cycle_length, last_period_date) VALUES (?, ?, ?)",
                        (admin_id, default_cycle_length, default_last_period),
                    )

            # Migrate mood_logs
            has_user_logs = conn.execute(
                "SELECT 1 FROM user_mood_logs WHERE chat_id = ?", (admin_id,)
            ).fetchone()
            if not has_user_logs:
                legacy_logs = conn.execute("SELECT * FROM mood_logs").fetchall()
                for log in legacy_logs:
                    conn.execute(
                        "INSERT INTO user_mood_logs (chat_id, date, note, phase, created_at) VALUES (?, ?, ?, ?, ?)",
                        (admin_id, log["date"], log["note"], log["phase"], log["created_at"]),
                    )

    # ── User management ─────────────────────────────────────────────

    def add_user(self, chat_id: int, added_by: int):
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO users (chat_id, added_by) VALUES (?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET is_active = 1, added_by = excluded.added_by
            """, (chat_id, added_by))

    def remove_user(self, chat_id: int):
        with self._get_conn() as conn:
            conn.execute("UPDATE users SET is_active = 0 WHERE chat_id = ?", (chat_id,))

    def is_user_authorized(self, chat_id: int) -> bool:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM users WHERE chat_id = ? AND is_active = 1", (chat_id,)
            ).fetchone()
            return row is not None

    def is_admin(self, chat_id: int) -> bool:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM users WHERE chat_id = ? AND is_admin = 1 AND is_active = 1", (chat_id,)
            ).fetchone()
            return row is not None

    def get_all_active_users(self) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT chat_id, is_admin FROM users WHERE is_active = 1"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_whitelisted_users(self) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT chat_id, is_admin, is_active, created_at FROM users ORDER BY created_at"
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Per-user cycle config ───────────────────────────────────────

    def get_user_config(self, chat_id: int) -> dict | None:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM user_cycle_config WHERE chat_id = ?", (chat_id,)
            ).fetchone()
            return dict(row) if row else None

    def user_has_config(self, chat_id: int) -> bool:
        return self.get_user_config(chat_id) is not None

    def upsert_user_config(self, chat_id: int, cycle_length: int, last_period_date: str):
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO user_cycle_config (chat_id, cycle_length, last_period_date)
                VALUES (?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    cycle_length = excluded.cycle_length,
                    last_period_date = excluded.last_period_date
            """, (chat_id, cycle_length, last_period_date))

    def update_user_cycle_length(self, chat_id: int, cycle_length: int):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE user_cycle_config SET cycle_length = ? WHERE chat_id = ?",
                (cycle_length, chat_id),
            )

    def update_user_last_period_date(self, chat_id: int, last_period_date: str):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE user_cycle_config SET last_period_date = ? WHERE chat_id = ?",
                (last_period_date, chat_id),
            )

    # ── Per-user mood logs ──────────────────────────────────────────

    def add_user_log(self, chat_id: int, note: str, phase: str, log_date: date | None = None):
        log_date = log_date or date.today()
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO user_mood_logs (chat_id, date, note, phase) VALUES (?, ?, ?, ?)",
                (chat_id, log_date.isoformat(), note, phase),
            )

    def get_user_recent_logs(self, chat_id: int, limit: int = 10) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT date, note, phase, created_at FROM user_mood_logs WHERE chat_id = ? ORDER BY created_at DESC LIMIT ?",
                (chat_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_user_logs_for_date(self, chat_id: int, log_date: date) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT date, note, phase FROM user_mood_logs WHERE chat_id = ? AND date = ?",
                (chat_id, log_date.isoformat()),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Chat history ────────────────────────────────────────────────

    def add_chat_message(self, chat_id: int, role: str, content: str):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO chat_history (chat_id, role, content) VALUES (?, ?, ?)",
                (chat_id, role, content),
            )

    def get_chat_history(self, chat_id: int, limit: int = 20) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT role, content FROM chat_history WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
                (chat_id, limit),
            ).fetchall()
            return [dict(r) for r in reversed(rows)]

    def prune_chat_history(self, chat_id: int, keep: int = 50):
        """Remove old chat messages beyond the keep limit."""
        with self._get_conn() as conn:
            conn.execute("""
                DELETE FROM chat_history WHERE chat_id = ? AND id NOT IN (
                    SELECT id FROM chat_history WHERE chat_id = ?
                    ORDER BY id DESC LIMIT ?
                )
            """, (chat_id, chat_id, keep))

    def clear_chat_history(self, chat_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM chat_history WHERE chat_id = ?", (chat_id,))
