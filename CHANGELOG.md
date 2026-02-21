# Changelog

## 1.1.0 — 2026-02-21

### Added
- Proportional phase boundaries based on cycle length and period duration (medical model: fixed 14-day luteal phase)
- Period duration setting (2-7 days) in `/setup` and `/settings period`
- Birth year / age tracking in `/setup` and `/settings age`
- Period history log (`period_logs` table) for adaptive cycle length computation
- Adaptive cycle length: median of recent inter-period gaps when 2+ periods logged
- Age context in AI tips, reminders, and chat responses
- Dynamic phase detail text with proportional day ranges via `get_phase_detail()`
- CI/CD deploy workflow with DB backup and health check
- GitHub sponsor funding (Buy Me a Coffee)

### Changed
- `/setup` now accepts optional period duration and birth year: `/setup 28 2026-02-15 5 1995`
- `/settings` supports subcommands: `/settings period 4`, `/settings age 1995`
- `get_phase()` and `get_phase_info()` use proportional boundaries instead of fixed 28-day ranges
- `predict_dates()` ovulation calculation fixed: `cycle_length - 15` instead of hardcoded day 14
- Scheduler PMS warning uses proportional boundary instead of hardcoded day 20
- `get_cycle_info()` returns 3-tuple `(last_period_start, cycle_length, period_duration)`
- Test suite expanded from 127 to 174 tests

## 1.0.0 — 2026-02-21

### Added
- Cycle engine with phase detection (menstruation, follicular, ovulation, luteal, PMS)
- Telegram commands: /start, /status, /tip, /log, /history, /next, /phase, /adjust, /settings
- `/about` command showing bot info and version
- Multi-user whitelist with `/adduser`, `/removeuser`, `/users`
- Per-user cycle tracking with independent config and mood logs
- `/setup` command for new users to configure their cycle
- Free-form AI chat with cycle-aware women's health advisor (Claude Sonnet)
- `/clearchat` command to reset AI conversation history
- 3-tier authorization: whitelisted, authorized (setup done), admin-only
- Admin commands hidden from non-admin users in Telegram menu
- Claude AI integration (Haiku for reminders, Sonnet for tips and chat)
- APScheduler daily proactive reminders during PMS, period, and ovulation
- SQLite persistence with WAL mode, foreign keys, and indexed queries
- Per-user AI rate limiting (5 calls / 60 seconds)
- Input validation and markdown escaping
- PM2 ecosystem config with auto-restart and log rotation
- 127 pytest tests covering all modules
