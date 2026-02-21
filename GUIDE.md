# Lunaris — Setup & Configuration Guide

Complete guide to installing, configuring, and running Lunaris.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Environment Variables](#environment-variables)
  - [Configuration Reference](#configuration-reference)
- [Running the Bot](#running-the-bot)
  - [Development](#development)
  - [Production with PM2](#production-with-pm2)
- [First-Time Setup](#first-time-setup)
- [User Management](#user-management)
- [Bot Commands Reference](#bot-commands-reference)
- [AI Features](#ai-features)
  - [Free-Form Chat](#free-form-chat)
  - [Tips](#tips)
  - [Daily Reminders](#daily-reminders)
- [Cycle Phases](#cycle-phases)
- [Database](#database)
- [Running Tests](#running-tests)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

- **Python 3.11** or newer
- A **Telegram bot token** — create one via [@BotFather](https://t.me/BotFather) on Telegram
- An **Anthropic API key** — sign up at [console.anthropic.com](https://console.anthropic.com)
- Your **Telegram user ID** — message [@userinfobot](https://t.me/userinfobot) on Telegram to get it

---

## Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/borghei/lunaris-bot.git
   cd lunaris-bot
   ```

2. **Create a virtual environment**

   ```bash
   python3 -m venv venv
   source venv/bin/activate    # Linux/macOS
   venv\Scripts\activate       # Windows
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Create your configuration file**

   ```bash
   cp .env.example .env
   ```

5. **Edit `.env`** with your values (see [Configuration](#configuration) below).

---

## Configuration

### Environment Variables

Edit the `.env` file in the project root:

```env
# Required
TELEGRAM_BOT_TOKEN=your-bot-token-from-botfather
ANTHROPIC_API_KEY=your-anthropic-api-key
ADMIN_CHAT_ID=your-telegram-user-id

# Optional (defaults shown)
CYCLE_LENGTH=28
LAST_PERIOD_START=2026-01-28
REMINDER_HOUR=9
TIMEZONE=Asia/Tehran
CHAT_MODEL=claude-sonnet-4-6
MAX_CHAT_HISTORY=20
```

### Configuration Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | — | Bot token from [@BotFather](https://t.me/BotFather) |
| `ANTHROPIC_API_KEY` | Yes | — | API key from [Anthropic Console](https://console.anthropic.com) |
| `ADMIN_CHAT_ID` | Yes | — | Your Telegram user ID (the bot admin) |
| `CYCLE_LENGTH` | No | `28` | Default cycle length in days (used for initial admin setup) |
| `LAST_PERIOD_START` | No | `2026-01-28` | Default last period date for admin bootstrap (YYYY-MM-DD) |
| `REMINDER_HOUR` | No | `9` | Hour of day (0–23) to send daily reminders |
| `TIMEZONE` | No | `Asia/Tehran` | IANA timezone for the reminder scheduler (e.g. `America/New_York`, `Europe/London`) |
| `CHAT_MODEL` | No | `claude-sonnet-4-6` | Claude model for free-form chat |
| `MAX_CHAT_HISTORY` | No | `20` | Number of chat messages to include as context |

> **Note:** `CYCLE_LENGTH` and `LAST_PERIOD_START` are only used for the admin's initial bootstrap. Each user configures their own cycle via the `/setup` command. You can update these values later through the bot itself.

---

## Running the Bot

### Development

```bash
source venv/bin/activate
python run.py
```

The bot will start polling for messages. Press `Ctrl+C` to stop.

### Production with PM2

The included `ecosystem.config.js` configures [PM2](https://pm2.keymetrics.io/) for production:

```bash
# Install PM2 (if not already installed)
npm install -g pm2

# Start the bot
pm2 start ecosystem.config.js

# Monitor
pm2 logs lunaris
pm2 monit

# Restart / Stop
pm2 restart lunaris
pm2 stop lunaris
```

PM2 features enabled:
- Auto-restart on crash (max 15 restarts)
- Memory limit (256MB)
- Rotating log files
- Minimum uptime check (10 seconds)

> **Note:** Edit `ecosystem.config.js` to update the `cwd` and file paths to match your server.

---

## First-Time Setup

1. **Start the bot** — Run `python run.py`. The admin user (your `ADMIN_CHAT_ID`) is automatically created.

2. **Open Telegram** — Find your bot and send `/start`.

3. **Configure your cycle** — If this is your first time, the bot will prompt you:

   ```
   /setup 28 2026-02-15
   ```

   Replace `28` with your cycle length (20–45 days) and `2026-02-15` with the start date of your last period.

4. **You're all set!** Use the inline keyboard or type commands to interact.

---

## User Management

Lunaris supports multiple users, managed by the admin.

**Adding a user:**
```
/adduser 123456789
```
The new user can then message the bot and run `/setup` to configure their cycle.

**Removing a user:**
```
/removeuser 123456789
```
This deactivates the user (their data is preserved). They can be re-added later.

**Listing users:**
```
/users
```
Shows all whitelisted users with their status (active/inactive) and role.

> **Note:** The admin cannot be removed. Each user's data (cycle config, mood logs, chat history) is fully isolated.

---

## Bot Commands Reference

### For All Users

| Command | Usage | Description |
|---------|-------|-------------|
| `/start` | `/start` | Shows welcome message with inline keyboard menu |
| `/setup` | `/setup 28 2026-02-15` | Configure cycle length and last period date |
| `/status` | `/status` | Shows current cycle day and phase |
| `/tip` | `/tip` | Get an AI-generated tip for your current phase |
| `/period` | `/period` or `/period 2026-02-20` | Log that your period started (today or on a specific date) |
| `/log` | `/log feeling tired and crampy` | Log a mood note or symptom |
| `/history` | `/history` | View your 10 most recent log entries |
| `/next` | `/next` | See predicted dates for next period, PMS, and ovulation |
| `/phase` | `/phase` | Detailed information about your current cycle phase |
| `/adjust` | `/adjust 2026-02-10` | Correct your last period start date |
| `/settings` | `/settings` or `/settings 30` | View settings or update cycle length |
| `/clearchat` | `/clearchat` | Clear your AI conversation history |

### Admin Only

| Command | Usage | Description |
|---------|-------|-------------|
| `/adduser` | `/adduser 123456789` | Whitelist a Telegram user |
| `/removeuser` | `/removeuser 123456789` | Deactivate a user |
| `/users` | `/users` | List all whitelisted users |

### Free-Form Chat

Any message that isn't a command triggers the AI chat. Just type naturally:

> "I've been having really bad cramps today, any advice?"

The AI responds as a caring, knowledgeable women's health advisor with context about your current cycle phase and recent logs.

---

## AI Features

Lunaris uses Anthropic's Claude models for three types of AI interactions.

### Free-Form Chat

- **Model:** Claude Sonnet (configurable via `CHAT_MODEL`)
- **Context:** Includes your cycle day, phase, recent logs, and conversation history
- **History:** Stored per-user, up to `MAX_CHAT_HISTORY` messages
- **Clear with:** `/clearchat`

### Tips

- **Model:** Claude Sonnet
- **Triggered by:** `/tip` command or the Tip button
- **Context:** Current phase and recent mood logs

### Daily Reminders

- **Model:** Claude Haiku (cost-efficient)
- **Schedule:** Daily at `REMINDER_HOUR` in your configured `TIMEZONE`
- **Sent during:** PMS, menstruation, ovulation, and luteal day 20 (PMS heads-up)
- **Skipped during:** Follicular and most luteal days

### Rate Limiting

AI calls are rate-limited to **5 requests per 60 seconds** per user. If you hit the limit, the bot will ask you to wait.

---

## Cycle Phases

Lunaris divides the menstrual cycle into 5 phases (based on a default 28-day cycle):

| Phase | Days | Description |
|-------|------|-------------|
| **Menstruation** | 1–5 | Period is active. Rest, hydrate, use heating pads. |
| **Follicular** | 6–13 | Energy and creativity returning. Great for new projects. |
| **Ovulation** | 14 | Peak energy, confidence, and fertility. |
| **Luteal** | 15–21 | Progesterone rising, energy dipping. Slow down. |
| **PMS** | 22–28 | Hormone shifts cause mood swings, fatigue, cravings. Be kind to yourself. |

### Cycle Length Learning

When you log a new period with `/period`, Lunaris calculates the actual gap between periods. If it falls within 18–45 days, the bot updates your cycle length using exponential smoothing:

```
new_length = round(actual_gap * 0.7 + previous_length * 0.3)
```

This gradually adapts to your real cycle pattern over time.

---

## Database

Lunaris uses SQLite with the following optimizations:

- **WAL mode** — Allows concurrent reads during writes
- **Foreign keys** — Enforced for data integrity
- **Busy timeout** — 5-second wait instead of immediate failure
- **Indexed queries** — Fast lookups on chat history and mood logs

The database file is stored at `data/lunaris.db` (created automatically on first run).

### Tables

| Table | Purpose |
|-------|---------|
| `users` | User accounts with admin flag and active status |
| `user_cycle_config` | Per-user cycle length and last period date |
| `user_mood_logs` | Per-user mood/symptom log entries |
| `chat_history` | Per-user AI conversation history |
| `cycle_config` | Legacy single-user config (kept for migration) |
| `mood_logs` | Legacy single-user logs (kept for migration) |

---

## Running Tests

Install test dependencies:

```bash
pip install pytest pytest-asyncio
```

Run the full suite:

```bash
pytest -v
```

**125 tests** covering:

| File | Tests | What It Covers |
|------|-------|----------------|
| `test_cycle.py` | 34 | Pure cycle functions, constants, date predictions |
| `test_db.py` | 32 | Real SQLite — schema, CRUD, bootstrap, migration |
| `test_ai.py` | 14 | Mocked Anthropic client, all AI functions |
| `test_handlers_helpers.py` | 19 | Decorators, rate limiter, markdown escaping |
| `test_handlers_commands.py` | 20 | Command handlers with real DB |
| `test_scheduler.py` | 6 | Daily reminder logic |

No external services needed. Database tests use real SQLite via temporary files. AI tests use mocked clients.

---

## Troubleshooting

**Bot doesn't respond**
- Check that `TELEGRAM_BOT_TOKEN` is correct
- Make sure no other instance is running (only one polling connection allowed)
- Check logs in `logs/lunaris.log`

**"Sorry darling, this bot isn't for you"**
- The user isn't whitelisted. The admin needs to run `/adduser <user_id>`

**"You need to set up your cycle first"**
- The user is whitelisted but hasn't configured their cycle yet. Run `/setup`

**AI responses fail**
- Verify `ANTHROPIC_API_KEY` is valid and has credits
- Check rate limit — wait 60 seconds and try again

**Reminders not sending**
- Verify `REMINDER_HOUR` and `TIMEZONE` in `.env`
- Reminders only go out during PMS, menstruation, ovulation, and luteal day 20
- Check `logs/lunaris.log` for scheduler errors

**Database errors**
- The `data/` directory must be writable
- If the DB is corrupted, stop the bot, delete `data/lunaris.db`, and restart (all data will be lost)
