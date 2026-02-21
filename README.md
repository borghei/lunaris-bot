<p align="center">
  <img src="Lunaris-header.png" alt="Lunaris" width="200">
</p>

<h1 align="center">Lunaris</h1>

<p align="center">
  A private Telegram bot for menstrual cycle tracking with an AI-powered, cycle-aware health companion.
</p>

<p align="center">
  <a href="#features">Features</a> &bull;
  <a href="#quick-start">Quick Start</a> &bull;
  <a href="GUIDE.md">Full Guide</a> &bull;
  <a href="#commands">Commands</a> &bull;
  <a href="#tech-stack">Tech Stack</a> &bull;
  <a href="#license">License</a>
</p>

---

## Features

**Cycle Tracking**
- 5-phase detection: menstruation, follicular, ovulation, luteal, PMS
- Predicts next period, PMS start, and ovulation dates
- Learns your actual cycle length over time (exponential smoothing)
- Mood and symptom logging tied to cycle phases

**AI Companion**
- Free-form chat with a cycle-aware women's health advisor (Claude Sonnet)
- On-demand tips tailored to your current phase
- Daily proactive reminders during PMS, period, and ovulation (Claude Haiku)
- Persistent conversation history per user

**Multi-User**
- Admin-managed whitelist — invite others via Telegram user ID
- Each user has independent cycle config, logs, and chat history
- 3-tier authorization: whitelisted, authorized (setup complete), admin-only

**Production Quality**
- SQLite with WAL mode, foreign keys, and indexed queries
- Per-user AI rate limiting (5 calls / 60 seconds)
- Input validation and markdown escaping
- 125 tests covering all modules
- PM2-ready with rotating logs

---

## Quick Start

```bash
# Clone
git clone https://github.com/borghei/lunaris-bot.git
cd lunaris-bot

# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your tokens (see GUIDE.md for details)

# Run
python run.py
```

You need three things in your `.env`:
1. **Telegram bot token** from [@BotFather](https://t.me/BotFather)
2. **Anthropic API key** from [console.anthropic.com](https://console.anthropic.com)
3. **Your Telegram user ID** (use [@userinfobot](https://t.me/userinfobot) to find it)

See the **[Full Setup & Configuration Guide](GUIDE.md)** for detailed instructions.

---

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and main menu |
| `/setup <length> <date>` | Configure your cycle (e.g. `/setup 28 2026-02-15`) |
| `/status` | Current cycle day and phase |
| `/tip` | AI-generated tip for your current phase |
| `/period [date]` | Log period start (learns cycle length) |
| `/log <note>` | Log a mood or symptom |
| `/history` | View recent logs |
| `/next` | Predicted upcoming dates |
| `/phase` | Detailed info about your current phase |
| `/adjust <date>` | Correct your last period start date |
| `/settings [length]` | View or update cycle length |
| `/clearchat` | Clear AI conversation history |
| `/adduser <id>` | Whitelist a user (admin only) |
| `/removeuser <id>` | Remove a user (admin only) |
| `/users` | List all whitelisted users (admin only) |

Any non-command text message starts a free-form AI chat conversation.

---

## Cycle Phases

| Phase | Days | What Happens |
|-------|------|-------------|
| Menstruation | 1–5 | Period — rest and recovery |
| Follicular | 6–13 | Energy rising, creativity peaks |
| Ovulation | 14 | Peak energy, confidence, fertility |
| Luteal | 15–21 | Slowing down, progesterone rising |
| PMS | 22–28 | Hormone shifts, mood changes |

---

## Project Structure

```
lunaris-bot/
├── config/
│   ├── __init__.py
│   └── settings.py          # Environment-based configuration
├── src/
│   ├── __init__.py
│   ├── ai.py                # Claude AI integration
│   ├── bot.py                # Application setup and handler registration
│   ├── cycle.py              # Cycle calculation engine
│   ├── db.py                 # SQLite database layer
│   ├── handlers.py           # Command and callback handlers
│   └── scheduler.py          # Daily reminder scheduler
├── tests/
│   ├── conftest.py           # Shared test fixtures
│   ├── test_ai.py            # AI integration tests (14)
│   ├── test_cycle.py         # Cycle engine tests (34)
│   ├── test_db.py            # Database tests (32)
│   ├── test_handlers_commands.py  # Command handler tests (20)
│   ├── test_handlers_helpers.py   # Helper/decorator tests (19)
│   └── test_scheduler.py     # Scheduler tests (6)
├── .env.example
├── ecosystem.config.js       # PM2 production config
├── pyproject.toml            # Pytest configuration
├── requirements.txt
└── run.py                    # Entry point
```

---

## Tech Stack

- **Python 3.11+**
- **[python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)** — Telegram Bot API
- **[Anthropic Claude](https://www.anthropic.com)** — AI chat, tips, and reminders
- **[APScheduler](https://github.com/agronholm/apscheduler)** — Daily reminder scheduling
- **SQLite** — Persistent storage (WAL mode)
- **[pytest](https://pytest.org)** + **pytest-asyncio** — Test suite

---

## Testing

```bash
pip install pytest pytest-asyncio
pytest -v
```

125 tests, all passing. No external services needed — database tests use real SQLite via temp files, AI tests use mocked clients.

---

## License

[MIT](LICENSE) — Amin Borghei
