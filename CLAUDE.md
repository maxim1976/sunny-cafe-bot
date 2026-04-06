# CLAUDE.md — Sunny Cafe Bot

Developer guide for AI assistants working in this repository.

---

## Project Overview

LINE chatbot for cafe ordering, powered by Claude AI (`claude-sonnet-4-6`). Customers message the bot in Traditional Chinese or English, build their order through conversation, and receive a printed kitchen ticket on an ESC/POS thermal printer.

**Stack:** Python 3.12 · Flask · LINE Messaging API v3 · Anthropic SDK · SQLite · Gunicorn · Railway

---

## Repository Structure

```
sunny-cafe-bot/
├── app.py              # Flask app: webhook handler, route definitions, rate limiting
├── bot.py              # Claude API integration, SQLite conversation history
├── menu.py             # SINGLE SOURCE OF TRUTH for menu items, prices, cafe info
├── flex_menu.py        # LINE Flex Message UI builder (imports from menu.py)
├── printer.py          # ESC/POS ticket printing via TCP socket
├── setup_richmenu.py   # One-time script: create LINE Rich Menu (run locally)
├── requirements.txt    # Python dependencies
├── Procfile            # Gunicorn entry for Railway: `web: gunicorn app:app ...`
├── .env.example        # Environment variable template (copy to .env)
├── .python-version     # Pins Python 3.12
└── images/             # Menu category hero photos served at /images/<filename>
    ├── coffee.jpg
    ├── non-coffee.jpg
    ├── food.jpg
    ├── pastries.jpg
    ├── addons.jpg
    └── welcome.jpg
```

---

## Architecture

### Request Flow

```
LINE user → LINE server → POST /webhook
    → signature validation (app.py)
    → rate limit check (app.py)
    → input length check (app.py)
    → menu keyword detection (app.py) → Flex carousel reply
    └── Claude API call (bot.py)
           → load last 10 messages from SQLite
           → call claude-sonnet-4-6 with system prompt
           → persist exchange to SQLite
           → return (reply_text, order_confirmed: bool)
    → strip ORDER_CONFIRMED token (app.py)
    → inject Quick Reply buttons if order summary detected
    → LINE reply API
    → if order_confirmed: printer.print_order_ticket() (app.py)
```

### Key Architectural Patterns

- **Single source of truth:** All menu data lives in `menu.py`. `flex_menu.py` and `bot.py` both import from it — never duplicate menu items.
- **Per-user conversation isolation:** SQLite `messages` table keyed by `user_id` (LINE's unique per-user ID). History capped at 10 messages (`MAX_HISTORY` in `bot.py`).
- **ORDER_CONFIRMED sentinel:** Claude appends literal `ORDER_CONFIRMED` to its response when an order is finalized. `app.py` detects this, strips it from the user-facing message, then calls the printer.
- **Graceful degradation:** Printer offline → logs error, order still accepted. Claude error → generic apology sent. Invalid LINE signature → 400, request dropped.
- **Configuration over code:** To deploy for a new client, only `menu.py` needs editing; all downstream modules auto-update.

---

## Module Reference

### `app.py` — Webhook Handler

- `/webhook` (POST): Main LINE event receiver. Validates `X-Line-Signature` header.
- `/health` (GET): Railway health probe.
- `/images/<filename>` (GET): Serves menu photos referenced in Flex Messages.
- `_is_menu_request(text)`: Detects menu trigger keywords in English/Chinese.
- `_handle_confirmed_order(reply, user_id)`: Parses order details and calls printer.
- `_is_rate_limited(user_id)`: In-memory per-user throttle (10 msgs / 60s by default).
- `_reply_flex(reply_token, flex_json)`: Sends Flex via raw `requests` call — bypasses LINE SDK serialization quirks.

### `bot.py` — Claude Integration

- `init_db()`: Creates SQLite `messages` table (called at module import; safe for Gunicorn multi-worker startup).
- `get_reply(user_id, user_message)`: Core function. Returns `(str, bool)` — (reply text, order_confirmed).
- `_build_system_prompt()`: Dynamically injects current menu, date, cafe info, and ordering rules into Claude's context.
- `_load_history(user_id)`: Fetches last `MAX_HISTORY` (10) messages for the user.
- `_save_message(user_id, role, content)`: Persists message; prunes oldest when over limit.
- **Model:** `claude-sonnet-4-6` — do not downgrade without testing order flow.

### `menu.py` — Configuration

- `RESTAURANT_INFO`: Name, address, phone, hours, currency.
- `MENU`: `{category: {item_name: price_int}}` — 5 categories, 38 items, prices in TWD.
- `MENU_ZH`: Traditional Chinese translations for all items/categories.
- `FULFILLMENT_OPTIONS`: `["dine-in", "takeaway", "delivery"]`
- `format_menu_for_prompt()`: Returns plain-text menu string for Claude's system prompt.
- `calculate_total(items)`: Sums `[{name, qty}]` list against menu prices.

### `flex_menu.py` — LINE UI

- Color palette constants at the top: amber `#C8A165`, coffee brown `#6B4226`.
- `build_welcome_flex()`: Welcome bubble sent on `FollowEvent`.
- `build_menu_carousel()`: One bubble per category, hero image, bilingual item rows.
- All data driven from `menu.py` — adding a category there auto-adds it to the carousel.
- `BASE_URL` env var must be set (e.g. Railway URL) for hero images to load.

### `printer.py` — ESC/POS Printing

- Connects via TCP socket to `PRINTER_IP:PRINTER_PORT` (default 9100), 5s timeout.
- `print_order_ticket(order_data)`: Main entry point. Returns `{success, order_number, message}`.
- `parse_order_from_text(text)`: Regex parser extracts name, fulfillment, items, total from Claude's order summary message.
- `_next_order_number()`: Reads/increments `order_counter.txt`. **Note:** This file is excluded from git; it persists only on the host. Not safe for multi-instance deployments.
- Compatible with Epson TM-T20 and similar ESC/POS printers.

---

## Database Schema

```sql
CREATE TABLE messages (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    TEXT NOT NULL,
  role       TEXT NOT NULL,   -- 'user' | 'assistant'
  content    TEXT NOT NULL,
  created_at TEXT NOT NULL    -- ISO 8601 timestamp
);
CREATE INDEX idx_messages_user_id ON messages(user_id);
```

- SQLite file path from `DATABASE_URL` env var (default `sqlite:///chat.db`).
- For Railway persistence: mount a Volume at `/data` and set `DATABASE_URL=sqlite:////data/chat.db` (4 slashes = absolute path).
- `order_counter.txt` is a separate plain-text file (integer) in the working directory.

---

## Environment Variables

All required variables are documented in `.env.example`:

| Variable | Required | Description |
|---|---|---|
| `LINE_CHANNEL_SECRET` | Yes | For webhook signature validation |
| `LINE_CHANNEL_ACCESS_TOKEN` | Yes | For sending replies |
| `ANTHROPIC_API_KEY` | Yes | Claude API access |
| `PRINTER_IP` | No | Thermal printer LAN IP |
| `PRINTER_PORT` | No | Printer TCP port (default 9100) |
| `DATABASE_URL` | No | SQLite URL (default `sqlite:///chat.db`) |
| `BASE_URL` | Yes | Public URL for image serving (e.g. Railway app URL) |
| `RATE_LIMIT_MESSAGES` | No | Max messages per window (default 10) |
| `RATE_LIMIT_WINDOW` | No | Window in seconds (default 60) |
| `MAX_MESSAGE_LENGTH` | No | Input cap in characters (default 500) |
| `PORT` | No | Flask port (default 5000) |

---

## Development Workflows

### Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN, ANTHROPIC_API_KEY
python app.py
# Expose via ngrok: ngrok http 5000
# Set LINE webhook to: https://<ngrok-id>.ngrok.io/webhook
```

### Deploy to Railway

```bash
railway login
railway init
# Set env vars in Railway dashboard (same as .env)
# Add a Volume mounted at /data, set DATABASE_URL=sqlite:////data/chat.db
railway up
```

### Rich Menu Setup (one-time, run locally)

```bash
python setup_richmenu.py
```

Creates two-button persistent menu at the bottom of the chat. Requires `LINE_CHANNEL_ACCESS_TOKEN` in `.env`.

---

## Common Modification Tasks

### Add/Change Menu Items

Edit `menu.py` only:
1. Add item to `MENU[category]` with integer price in TWD.
2. Add Traditional Chinese name to `MENU_ZH`.
3. Flex carousel and Claude system prompt update automatically on next deploy.

### Add a New Menu Category

1. Add category key to `MENU` dict in `menu.py`.
2. Add Chinese name to `MENU_ZH`.
3. Add hero image to `images/<category>.jpg`.
4. Update `_category_bubble()` in `flex_menu.py` if image filename doesn't follow the existing pattern.

### Change Cafe Info

Edit `RESTAURANT_INFO` in `menu.py`. The system prompt in `bot.py` picks this up via `_build_system_prompt()`.

### Update Claude's Ordering Instructions

Edit `_build_system_prompt()` in `bot.py`. Keep the `ORDER_CONFIRMED` sentinel instruction intact — removing it breaks the confirmation flow.

### Modify Ticket Layout

Edit `build_ticket()` in `printer.py`. ESC/POS commands are in the `escpos` library; see python-escpos docs for codes.

### Change Rate Limits or Input Cap

Set `RATE_LIMIT_MESSAGES`, `RATE_LIMIT_WINDOW`, and `MAX_MESSAGE_LENGTH` env vars. No code change needed.

---

## Conventions

- **No duplicated menu data.** Always read from `menu.py`; never hardcode item names or prices elsewhere.
- **Bilingual by default.** Every user-facing string needs Traditional Chinese + English. Match the pattern in `flex_menu.py` (Chinese label + English sublabel).
- **Env vars for all secrets and deployment config.** Never commit `.env`.
- **Flex Messages via raw HTTP, not SDK.** The LINE Bot SDK v3 has serialization issues with nested Flex JSON. Use `_reply_flex()` in `app.py` which calls the API directly with `requests`.
- **Printer failures are non-fatal.** The order is always acknowledged to the customer; printer errors only surface in logs.
- **Keep conversation history lean.** `MAX_HISTORY = 10` in `bot.py`. Do not raise this without considering token cost per Claude call.

---

## Security Notes

- LINE signature validation is enforced in `/webhook` — do not remove or bypass it.
- Claude system prompt includes prompt-injection defenses; keep those instructions when editing `_build_system_prompt()`.
- Rate limiting is **in-memory and per-process** — resets on redeploy and is not shared across Gunicorn workers. For stricter enforcement, replace with Redis.
- `order_counter.txt` is gitignored; do not commit it.

---

## Known Limitations

- **Order counter** (`order_counter.txt`) is a local file; conflicts occur with multiple Railway instances. Migrate to a DB sequence if scaling horizontally.
- **In-memory rate limiting** not shared across Gunicorn workers (2 workers by default in `Procfile`).
- **No automated test suite.** Test manually via ngrok + LINE testbot or add pytest with mocked LINE/Anthropic clients.
- **SQLite on ephemeral filesystem** without a Railway Volume means conversation history is lost on every redeploy.
