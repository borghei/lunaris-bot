# Changelog

## 2.3.0 — 2026-02-21

### Added
- Proportional phase boundaries based on cycle length and period duration (medical model: fixed 14-day luteal phase)
- Period duration setting (2-7 days) in `/setup` and `/settings period`
- Birth year / age tracking in `/setup` and `/settings age`
- Period history log (`period_logs` table) for adaptive cycle length computation
- Adaptive cycle length: median of recent inter-period gaps replaces 70/30 formula when 2+ periods logged
- Age context in AI tips, reminders, and chat responses
- Dynamic phase detail text with proportional day ranges via `get_phase_detail()`
- New DB methods: `add_period_log`, `get_period_history`, `get_computed_cycle_length`, `update_user_period_duration`, `update_user_year_of_birth`

### Changed
- `/setup` now accepts optional period duration and birth year: `/setup 28 2026-02-15 5 1995`
- `/settings` supports subcommands: `/settings period 4`, `/settings age 1995`
- `get_phase()` and `get_phase_info()` use proportional boundaries instead of fixed 28-day ranges
- `predict_dates()` ovulation calculation fixed: `cycle_length - 15` instead of hardcoded day 14
- Scheduler PMS warning uses proportional boundary (`cycle_length - 8`) instead of hardcoded day 20
- `get_cycle_info()` returns 3-tuple `(last_period_start, cycle_length, period_duration)`

## 2.2.0 — 2026-02-21

### Added
- `/about` command showing bot info and version
- Hide admin commands from non-admin users in Telegram menu

## 2.1.1 — 2026-02-21

### Added
- Full pytest test suite (125 tests) covering all modules
  - `test_cycle.py` — 34 tests for pure cycle engine functions and constants
  - `test_db.py` — 32 tests with real SQLite via `tmp_path` (schema, CRUD, bootstrap, migration)
  - `test_ai.py` — 14 tests with mocked Anthropic client
  - `test_handlers_helpers.py` — 19 tests for decorators, rate limiter, markdown escaping
  - `test_handlers_commands.py` — 20 tests for command handlers with real DB
  - `test_scheduler.py` — 6 tests for daily reminder logic
- `pyproject.toml` with pytest configuration (`asyncio_mode = "auto"`)
- Shared test fixtures in `conftest.py` (db, mock context, mock update factory)

## 2.1.0 — 2026-02-21

### Fixed
- `/adduser` now properly re-activates previously removed users
- Admin can no longer be removed via `/removeuser`
- Markdown special characters in user notes no longer crash history display
- Chat history ordering stable (by id instead of timestamp)
- Future dates rejected in `/period`, `/adjust`, `/setup`
- Consistent cycle length validation (20–45 days) across all commands

### Changed
- Switched to `AsyncAnthropic` — AI calls no longer block the event loop for all users
- SQLite: WAL mode, persistent connection, busy timeout (5s), indexes on frequently queried columns
- `RotatingFileHandler` (10MB, 5 backups) replaces unbounded log file
- PM2 config: memory limit (256MB), min uptime, log rotation
- Deploy: pre-deploy DB backup, syntax check, post-deploy health check, `.env` chmod 600
- Server IP moved from hardcoded to `DEPLOY_HOST` secret
- Per-user AI rate limiting (5 calls per 60 seconds)
- Input length limits: log notes (500 chars), chat messages (2000 chars)
- Auth decorators use `functools.wraps`
- `PHASE_DETAILS` extracted to `cycle.py` (eliminated duplication)
- Safe API response extraction (handles empty content)

### Added
- `prune_chat_history()` method for database cleanup
- Chat button in main menu keyboard
- Bot commands auto-registered with Telegram on startup
- Claude Code skills: senior-qa, senior-devops, senior-fullstack

## 2.0.0 — 2026-02-21

### Added
- Multi-user whitelist: admin can `/adduser`, `/removeuser`, `/users` to manage access
- Per-user cycle tracking with independent config and mood logs
- `/setup` command for new users to configure their cycle
- Free-form AI chat: any non-command text triggers a cycle-aware women's health advisor (Sonnet)
- `/clearchat` command to reset AI conversation history
- 3-tier authorization: whitelisted, authorized (setup done), admin-only
- `chat_history` table for persistent AI conversation context

### Changed
- All handlers now operate per-user via `chat_id` instead of singleton
- Scheduler iterates all active users for daily reminders
- Renamed `TELEGRAM_CHAT_ID` → `ADMIN_CHAT_ID` in config, .env, and deploy workflow
- Legacy single-user data auto-migrated to admin's per-user tables on startup

## 1.0.0 — 2026-02-21

### Added
- Cycle engine with phase detection (menstruation, follicular, ovulation, luteal, PMS)
- Telegram commands: /start, /status, /tip, /log, /history, /next, /phase, /adjust, /settings
- Claude AI integration for Persian tips (Haiku for reminders, Sonnet for on-demand tips)
- APScheduler daily proactive reminders during PMS, period, and ovulation
- SQLite persistence for cycle config and mood logs
- Single-user authorization
- PM2 ecosystem config
- GitHub Actions CI/CD auto-deploy
