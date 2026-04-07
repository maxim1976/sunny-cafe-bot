# Sunny Cafe Bot — Claude Code Guide

## Project overview
LINE ordering bot for a café in Hualien, Taiwan.
Flask webhook on Railway, PostgreSQL database, Flex Message UI for ordering,
Claude (claude-sonnet-4-6) used ONLY for FAQ / free-text questions.
Admin web panel for owner to manage menu, discounts, posts, and store info.

## Stack
| Layer | Technology |
|-------|-----------|
| Platform | LINE Messaging API (line-bot-sdk 3.11.0) |
| Backend | Flask + Gunicorn on Railway |
| Database | PostgreSQL (Railway managed) |
| AI | Anthropic Claude API — FAQ only, not order flow |
| Printer | Epson ESC/POS over TCP (optional, graceful fallback) |
| Admin UI | Flask + Jinja2 + Bootstrap 5 (no build step) |

## Key files
| File | Purpose |
|------|---------|
| `db.py` | All PostgreSQL access — connection pool, every query |
| `flow.py` | Order state machine — drives structured ordering without Claude |
| `flex_menu.py` | Builds all Flex Message JSON (reads live data from DB) |
| `app.py` | Flask webhook + message routing |
| `bot.py` | Claude API calls for FAQ only |
| `printer.py` | Order ticket parsing + ESC/POS printing |
| `admin/` | Flask blueprint — owner admin panel |
| `setup_richmenu.py` | One-time script to register LINE rich menu |

## PostgreSQL schema

```sql
-- ── Menu ─────────────────────────────────────────────────────────────────────
CREATE TABLE categories (
    id         SERIAL PRIMARY KEY,
    name_en    TEXT    NOT NULL,
    name_zh    TEXT    NOT NULL,
    emoji      TEXT    DEFAULT '•',
    image_file TEXT,                    -- served from /images/
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
    sort_order  INTEGER DEFAULT 0
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
-- key/value pairs: address, phone, hours, wifi_password, etc.
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
    customer_name TEXT,                 -- real name collected during order
    phone         TEXT,
    fulfillment   TEXT CHECK (fulfillment IN ('dine-in', 'takeaway', 'delivery')),
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

-- ── Order state machine ───────────────────────────────────────────────────────
-- Drives structured data collection — replaces Claude for ordering
CREATE TABLE order_sessions (
    user_id    TEXT PRIMARY KEY,
    state      TEXT NOT NULL DEFAULT 'idle',
    order_id   INTEGER REFERENCES orders(id),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
-- Valid states: idle → cart → fulfillment → name → phone
--               → pickup_time (takeaway) | address (delivery) | confirm (dine-in)
--               → confirming → done

-- ── User preferences ─────────────────────────────────────────────────────────
CREATE TABLE user_prefs (
    user_id TEXT PRIMARY KEY,
    lang    TEXT DEFAULT 'zh'           -- 'zh' | 'en'
);

-- ── Claude FAQ history ───────────────────────────────────────────────────────
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
  ├─ Language toggle ("切換語言")        → toggle user_prefs.lang
  ├─ Menu triggers ("menu", "菜單" …)   → show menu carousel (no Claude)
  ├─ Category selected                  → show item picker (no Claude)
  ├─ Item selected ("我要點 {zh}")       → cart_add → show cart bubble
  ├─ "繼續點餐"                          → show menu carousel
  ├─ "結帳"                             → show cart + Confirm/Edit/Cancel
  ├─ "確認結帳"                          → create order row, set state=fulfillment
  ├─ "重新點餐"                          → clear cart
  ├─ "取消訂單"                          → clear cart + cancel order session
  ├─ State machine (flow.py):
  │   state=fulfillment  → save fulfillment → state=name
  │   state=name         → save name        → state=phone
  │   state=phone        → save phone       → state=address | pickup_time | confirming
  │   state=address      → save address     → state=confirming
  │   state=pickup_time  → save time        → state=confirming
  │   state=confirming   → show summary + Confirm/Edit/Cancel quick replies
  │   "確認" / "confirm" → finalize order, print ticket, clear session
  └─ Everything else     → bot.get_reply() → Claude (FAQ only)
```

## Order flow (structured — no Claude)

1. Customer browses menu carousel → taps category → taps item → cart bubble
2. Can add more or go to checkout
3. Checkout → cart summary → Confirm / Edit / Cancel
4. Confirm → state machine takes over:
   - Fulfillment quick replies (內用 / 外帶 / 外送)
   - Type your real name
   - Type your phone number
   - Takeaway: type pickup time / Delivery: type address
   - Show order summary Flex bubble → Confirm / Edit / Cancel
5. Confirm → order saved to DB, ticket printed, cart cleared

## Claude's role (FAQ only)
- Only invoked when no state machine step is active AND message is free text
- Has access to: menu (from DB), store info, active posts/disclaimers
- Does NOT collect order data — never asks for name, phone, fulfillment
- System prompt built dynamically from DB (menu, store_info, active posts)

## Admin panel (admin/ blueprint)
- Protected by HTTP Basic Auth (ADMIN_USER / ADMIN_PASSWORD env vars)
- Routes:
  - `/admin/` — dashboard: today's orders, summary stats
  - `/admin/menu` — CRUD categories and items, toggle available
  - `/admin/discounts` — create/edit/delete discounts
  - `/admin/posts` — create/publish/archive disclaimers & announcements
  - `/admin/store` — edit store_info key/value pairs
  - `/admin/orders` — order history, update status
- UI: Bootstrap 5 via CDN, server-rendered Jinja2 templates, no JS framework

## Flex Message conventions
- Color palette: amber gold `#C8A165`, coffee brown `#6B4226`, cream `#E8D5B7`
- Chinese primary label, English subtitle (always bilingual in card UI)
- Quick reply button labels always bilingual: "✅ 確認 / Confirm"
- Item picker buttons use user's language preference for label text
- Images served from `/images/` on Railway (`BASE_URL` env var)
- Always send Flex via raw `urllib.request` — never SDK serialization

## Environment variables (Railway dashboard)
```
LINE_CHANNEL_SECRET
LINE_CHANNEL_ACCESS_TOKEN
ANTHROPIC_API_KEY
DATABASE_URL          # PostgreSQL URL — injected by Railway Postgres plugin
BASE_URL              # e.g. https://web-production-22461.up.railway.app
ADMIN_USER            # admin panel username
ADMIN_PASSWORD        # admin panel password
PRINTER_IP            # optional
PRINTER_PORT          # optional, default 9100
PORT                  # injected by Railway
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
# copy .env with real keys including local postgres or Railway postgres URL
python app.py
# expose with: ngrok http 5000
```

## Rules
- Menu data lives in PostgreSQL — never hardcode items or prices in Python
- `db.py` is the only file that touches the database — no raw SQL elsewhere
- State machine lives in `flow.py` — app.py only calls flow functions
- Claude never participates in the order flow — only FAQ
- Never commit `.env` — secrets in Railway environment only
- Admin panel uses Basic Auth — never expose without ADMIN_USER/ADMIN_PASSWORD set
