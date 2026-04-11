# Sunny Cafe Bot — Claude Code Guide

## Project overview

**Product**: 花蓮Vibe數位工作室 sells custom LINE ordering bots to F&B businesses in Taiwan.
**Demo**: Sunny Cafe Bot (`@839efdgh`) is the live demo — a fully working café ordering system.
**Sales channel**: The LINE bot itself acts as the sales AI — prospects chat with it, it explains
the product, collects client intake (menu, brand, operations), and notifies the owner when ready.
**Website**: hualienbot.com — product marketing page with pricing, features, live demo QR code.

Stack: Flask webhook on Railway, PostgreSQL, LIFF mini-app for ordering,
Claude AI sales assistant in LINE chat, admin web panel per client.

## Stack

| Layer         | Technology                                           |
| ------------- | ---------------------------------------------------- |
| Platform      | LINE Messaging API (line-bot-sdk 3.11.0)             |
| Backend       | Flask + Gunicorn on Railway                          |
| CSRF          | Flask-WTF CSRFProtect (admin forms)                  |
| Database      | PostgreSQL (Railway managed plugin)                  |
| Checkout UI   | LIFF page (HTML form served from same Railway app)   |
| AI (optional) | Anthropic Claude API — FAQ only, toggled by env var  |
| Printer       | Epson ESC/POS over TCP (optional, graceful fallback) |
| Admin UI      | Flask + Jinja2 + Bootstrap 5 (no build step)         |
| Landing page  | Static HTML served from `/` on the same Railway app  |

## Key files

| File                | Purpose                                                                        |
| ------------------- | ------------------------------------------------------------------------------ |
| `db.py`             | All PostgreSQL access — connection pool, every query lives here                |
| `flex_menu.py`      | Flex Message JSON builders — welcome, open-menu button, order confirmation     |
| `app.py`            | Flask webhook + message routing                                                |
| `bot.py`            | Claude sales AI — bilingual sales agent, intake collector, lead notifier       |
| `printer.py`        | Order ticket formatting + ESC/POS printing                                     |
| `admin/`            | Flask blueprint — owner admin panel at /admin/                                 |
| `liff/`             | LIFF mini-app — menu at /liff/menu, submit at /liff/submit                     |
| `landing/`          | Static landing page at /                                                       |
| `setup_richmenu.py` | One-time script to register LINE rich menu (left button opens LIFF URI)        |
| `seed_item_images.py` | One-time script to assign Unsplash photo URLs to menu items                  |
| `images/`           | Static images — category photos + store photos, served from /images/           |

## PostgreSQL schema

```sql
-- ── Menu ─────────────────────────────────────────────────────────────────────
CREATE TABLE categories (
    id         SERIAL PRIMARY KEY,
    name_en    TEXT    NOT NULL,
    name_zh    TEXT    NOT NULL,
    emoji      TEXT    DEFAULT '•',
    image_file TEXT,                    -- filename in /images/
    sort_order INTEGER DEFAULT 0,
    available  BOOLEAN DEFAULT TRUE
);

CREATE TABLE items (
    id          SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
    name_en     TEXT    NOT NULL,
    name_zh     TEXT    NOT NULL,
    price       INTEGER NOT NULL,       -- NT$
    available   BOOLEAN DEFAULT TRUE,
    sort_order  INTEGER DEFAULT 0,
    image_file  TEXT                    -- full Unsplash URL (seeded by seed_item_images.py)
);

-- ── Discounts ────────────────────────────────────────────────────────────────
CREATE TABLE discounts (
    id         SERIAL PRIMARY KEY,
    name       TEXT    NOT NULL,
    type       TEXT    NOT NULL CHECK (type IN ('percent', 'fixed')),
    value      INTEGER NOT NULL,        -- % or NT$
    active     BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMPTZ
);

-- ── Store info ───────────────────────────────────────────────────────────────
-- Editable key/value pairs: address, phone, hours, wifi_password, etc.
CREATE TABLE store_info (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- ── Posts / disclaimers ──────────────────────────────────────────────────────
CREATE TABLE posts (
    id         SERIAL PRIMARY KEY,
    title      TEXT,
    body       TEXT    NOT NULL,
    active     BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Orders ───────────────────────────────────────────────────────────────────
CREATE TABLE orders (
    id            SERIAL PRIMARY KEY,
    user_id       TEXT    NOT NULL,
    display_name  TEXT,                 -- LINE profile name (greeting only)
    customer_name TEXT,                 -- collected via LIFF form
    phone         TEXT,                 -- collected via LIFF form
    fulfillment   TEXT CHECK (fulfillment IN ('dine-in','takeaway','delivery')),
    address       TEXT,                 -- delivery only
    pickup_time   TEXT,                 -- takeaway only
    total         INTEGER,
    discount_amt  INTEGER DEFAULT 0,
    status        TEXT DEFAULT 'pending'
                       CHECK (status IN ('pending','ready','done','cancelled')),
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE order_items (
    id       SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
    name_en  TEXT    NOT NULL,
    name_zh  TEXT    NOT NULL,
    price    INTEGER NOT NULL,
    qty      INTEGER NOT NULL
);

-- ── Cart ─────────────────────────────────────────────────────────────────────
CREATE TABLE carts (
    user_id  TEXT    NOT NULL,
    item_id  INTEGER REFERENCES items(id) ON DELETE CASCADE,
    qty      INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id, item_id)
);

-- ── User preferences ─────────────────────────────────────────────────────────
CREATE TABLE user_prefs (
    user_id TEXT PRIMARY KEY,
    lang    TEXT DEFAULT 'zh'           -- 'zh' | 'en'
);

-- ── Claude FAQ history (only used when CLAUDE_ENABLED=true) ──────────────────
CREATE TABLE messages (
    id         SERIAL PRIMARY KEY,
    user_id    TEXT NOT NULL,
    role       TEXT NOT NULL,           -- 'user' | 'assistant'
    content    TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON messages(user_id);
```

## Architecture — message routing in app.py

```
Incoming LINE message
  ├─ Language toggle ("切換語言")       → toggle user_prefs.lang
  ├─ Menu triggers ("menu", "菜單" …)  → send "Open Menu" Flex bubble (URI → LIFF)
  ├─ "重新點餐" / "取消訂單"             → cancel message
  ├─ "確認" / "confirm"                → acknowledge (order already saved by LIFF)
  └─ Everything else:
      ├─ CLAUDE_ENABLED=true           → bot.get_reply() → Claude sales AI
      └─ CLAUDE_ENABLED=false          → static invite to try demo / contact us
```

All browsing, cart management, and checkout happen inside the LIFF mini-app.
Chat is only used for the entry point (menu button) and post-order confirmation.

## LIFF mini-app flow (primary ordering UI)

A single LIFF web app replaces the Flex carousel and all chat-based ordering.
Served at `/liff/menu`, opened via rich menu button or "Open Menu" bubble in chat.

### Three screens (one page, JS-managed transitions)

**Screen 1 — Menu**
- Sticky category tabs + scrollable 2-column item grid
- Each card: photo, bilingual name, price, ➕ button
- Quantity ➖/number/➕ controls appear inline after first tap
- Floating cart bar at bottom (hidden when cart empty)

**Screen 2 — Cart**
- Full cart with per-item ➖/➕ and remove
- Live discount selector (if active discounts exist)
- Running total updated in real time
- "Continue Shopping" + "Checkout" buttons

**Screen 3 — Checkout**
- Fulfillment tap-cards (🏠 Dine-in / 🛍 Takeaway / 🛵 Delivery)
- Conditional fields: time for dine-in/takeaway, address for delivery
- Name + phone with inline validation
- Submit → POST `/liff/submit` → LIFF closes → confirmation in chat

### Cart architecture
- **Pure JS cart** — lives only in the LIFF session (no DB writes while browsing)
- On submit, cart payload `[{item_id, qty}]` sent to server
- Server re-fetches all prices from DB — client prices are never trusted
- No `db.cart_clear()` needed (cart was never written to DB)

### Key route
- `/liff/menu` — serves the full 3-screen app (replaces `/liff/checkout` as primary)
- `/liff/checkout` — kept for backwards compatibility but no longer the main flow
- `/liff/submit` — unchanged endpoint, now accepts `cart` array in payload

## Claude sales AI module

- Enabled by setting `CLAUDE_ENABLED=true` in Railway env vars
- Disabled by default — bot works without Anthropic API key (returns a static invite)
- When enabled: acts as a **bilingual sales agent** for 花蓮Vibe數位工作室
- Explains product, pricing, tech stack (plain language), setup process
- Directs prospects to type "菜單" to try the live LIFF ordering demo
- Collects client intake conversationally: business name, city, type, menu categories,
  item list, brand colors, vibe/style, store photos, fulfillment needs, LINE Pay, AI add-on
- Handoff: when prospect is ready, includes `[[NOTIFY_OWNER]]` marker in reply
  → `get_reply()` strips marker, fires LINE push to `OWNER_LINE_USER_ID`
- System prompt: static `SALES_PROMPT` constant (no DB queries needed)
- Conversation history stored in `messages` table (per LINE user_id)

## Admin panel (`/admin/` blueprint)

- HTTP Basic Auth — `ADMIN_USER` / `ADMIN_PASSWORD` env vars (required, no fallback)
- CSRF protection on all POST forms via Flask-WTF (token auto-injected in base.html)
- Routes:
  - `/admin/` — dashboard: today's orders, counts by status
  - `/admin/menu` — CRUD categories + items, toggle available on/off
  - `/admin/discounts` — create/edit/deactivate discounts
  - `/admin/posts` — write/publish/archive announcements & disclaimers
  - `/admin/store` — edit store_info (address, hours, phone, etc.)
  - `/admin/orders` — order history, update status (pending→ready→done)
- UI: Bootstrap 5 CDN, server-rendered Jinja2, minimal JavaScript

## Landing page (`/`)

- Static HTML + CSS served by Flask from `landing/`
- Café name, description, hours, address, Google Maps link
- "Order on LINE" button → deep link to the bot
- Optional: exterior/interior photos

## Flex Message conventions

- Color palette: amber gold `#C8A165`, coffee brown `#6B4226`, cream `#E8D5B7`
- Chinese primary label, English subtitle — always bilingual in card UI
- Quick reply button labels bilingual: "✅ 確認 / Confirm"
- Item picker buttons use user_prefs.lang for label language
- Images served from `/images/` (`BASE_URL` env var)
- Always send Flex via raw `urllib.request` — never SDK serialization

## Static images

Stored in `/images/`, committed to git, never change at runtime.

```
images/
  coffee.jpg          ← Coffee & Espresso category
  non-coffee.jpg      ← Non-Coffee category
  food.jpg            ← Food category
  pastries.jpg        ← Pastries & Desserts category
  addons.jpg          ← Add-ons category
  exterior.jpg        ← Store street view
  interior.jpg        ← Store interior
  welcome.jpg         ← Hero / welcome image
```

## Environment variables (Railway dashboard)

```
LINE_CHANNEL_SECRET
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_ID           # needed for LIFF token verification + push messages
LIFF_ID                   # from LINE Developers console
DATABASE_URL              # injected by Railway Postgres plugin
BASE_URL                  # e.g. https://web-production-22461.up.railway.app
FLASK_SECRET_KEY          # required — stable secret for sessions + CSRF
ADMIN_USER                # required — app crashes without it
ADMIN_PASSWORD            # required — app crashes without it
CLAUDE_ENABLED            # optional — 'true' to enable sales AI module
ANTHROPIC_API_KEY         # optional — only needed if CLAUDE_ENABLED=true
OWNER_LINE_USER_ID        # optional — your personal LINE user ID for lead notifications
PRINTER_IP                # optional
PRINTER_PORT              # optional, default 9100
PORT                      # injected by Railway
```

## Deploy

```
Push to main → Railway auto-deploys
Procfile: web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 60
```

## Local dev

```bash
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
# copy .env with real keys
python app.py
# expose with: ngrok http 5000
# register ngrok URL as LINE webhook + LIFF endpoint
```

## Security

- **CSRF**: Flask-WTF `CSRFProtect` enabled globally; admin forms auto-inject tokens;
  LINE webhook and LIFF blueprint are exempt (own auth mechanisms)
- **LIFF auth**: `/liff/submit` verifies LINE access token server-side via
  `oauth2/v2.1/verify` + `/v2/profile` — never trust client-supplied `user_id`
- **Admin auth**: HTTP Basic Auth, credentials required via `os.environ[]` (no fallback)
- **Input validation**: phone regex `^[\d\-\+\(\)\s]{7,20}$`, fulfillment whitelist
- **Rate limiting**: per-user with periodic cleanup, max 10K tracked users
- **PII**: user message content is not logged — only user_id and message length

## Rules

- `db.py` is the ONLY file that touches the database — no raw SQL elsewhere
- Menu data lives in PostgreSQL — never hardcode items or prices in Python
- LIFF mini-app handles all ordering — no chat-based cart or checkout state machine
- Cart is pure JS in the LIFF session — never written to DB during browsing
- Server always re-fetches item prices from DB on submit — never trust client prices
- Claude is a sales agent, not an ordering assistant — never collects food orders in chat
- Admin panel requires Basic Auth — never run without ADMIN_USER/ADMIN_PASSWORD
- Never commit `.env` — all secrets in Railway environment
- `FLASK_SECRET_KEY`, `ADMIN_USER`, `ADMIN_PASSWORD` must be set — app crashes without them

```

```
