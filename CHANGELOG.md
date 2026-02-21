# Changelog

All notable changes to Lunaris will be documented in this file.

## 1.0.0 — 2026-02-21

Initial public release.

### Features

- **Cycle Engine** — 5-phase detection (menstruation, follicular, ovulation, luteal, PMS) with auto-wrapping cycle days, date predictions, and cycle length learning via exponential smoothing
- **Multi-User Support** — Admin-managed whitelist with 3-tier authorization (whitelisted, authorized, admin-only); each user has independent cycle config, mood logs, and chat history
- **AI Integration** — Claude-powered cycle-aware health advisor with free-form chat (Sonnet), on-demand tips (Sonnet), and daily proactive reminders (Haiku) — all async and rate-limited
- **Telegram Bot** — 16 commands with inline keyboard navigation, callback query handlers, and a catch-all chat handler for natural conversation
- **Scoped Command Menus** — Admin commands (`/adduser`, `/removeuser`, `/users`) hidden from non-admin users in the Telegram command menu
- **`/about` Command** — Displays bot version, description, and author info
- **Daily Reminders** — APScheduler-driven reminders during PMS, menstruation, ovulation, and pre-PMS (luteal day 20) with AI-generated phase-specific messages
- **SQLite Database** — WAL mode, foreign keys, persistent connection, busy timeout, indexed queries, and automatic legacy data migration
- **Test Suite** — 127 pytest tests covering cycle engine, database layer, AI integration, handler decorators, command handlers, and scheduler
- **Production Ready** — PM2 ecosystem config, rotating log files, input validation, markdown escaping, and environment-based configuration
