# Changelog

## 2026-04-10 — Sales AI bot (LINE chat becomes sales channel)

Pivot: Sunny Cafe bot is now a demo for selling LINE bots to F&B businesses.
The LINE chat (`@839efdgh`) acts as a bilingual sales AI — explains the product,
collects client intake, and notifies the owner when a prospect is ready to proceed.
The LIFF mini-app ordering system stays live as the demo experience.

### What changed

- **`bot.py`** — full rewrite as sales agent:
  - `SALES_PROMPT` replaces café FAQ system prompt — covers product overview, pricing
    (setup NT$3k–5k, monthly NT$800–1.5k, AI add-on, LINE Pay), tech explanation in
    plain language, setup process, intake checklist, handoff rule
  - `_build_prompt()` simplified — static prompt, no DB queries needed
  - `_notify_owner()` — pushes LINE message to `OWNER_LINE_USER_ID` when lead is ready
  - Handoff detection: AI includes `[[NOTIFY_OWNER]]` + summary in reply;
    `get_reply()` strips marker and fires owner push notification
  - `max_tokens` raised 512 → 1024
  - Static fallback reply (CLAUDE_ENABLED=false) updated to sales invite

- **`app.py`** — two changes:
  - Follow event: replaced café Flex welcome with bilingual sales intro text
    directing new contacts to type 菜單 for the live demo
  - Removed first-message menu carousel (not relevant for prospects)

- **`CLAUDE.md`** — updated project overview, `bot.py` description, Claude module
  section, architecture diagram, env vars, rules

### New env var

| Variable | Purpose |
|---|---|
| `OWNER_LINE_USER_ID` | Your personal LINE user ID — receives lead notifications |

### No schema changes

`messages` table continues to store conversation history per `user_id` unchanged.

### LIFF demo unchanged

`/liff/menu`, `/liff/submit`, all ordering logic, admin panel — untouched.
Prospects type "菜單" → full ordering experience as before.

## 2026-04-10 — LIFF mini-app menu (replaces Flex carousel)

Complete replacement of the chat-based ordering flow with a single LIFF web app.

### What changed

- **New primary ordering UI** — `/liff/menu` is a 3-screen LIFF mini-app:
  - Screen 1 (Menu): sticky category tabs, 2-column item grid with photos, inline ➕/➖ qty controls, floating cart bar
  - Screen 2 (Cart): full cart review, qty adjustments, live discount calculation
  - Screen 3 (Checkout): fulfillment tap-cards, conditional fields, name/phone, submit

- **Pure JS cart** — cart lives in the LIFF session only, never written to DB during browsing. On submit, `[{item_id, qty}]` is sent to the server which re-fetches all prices from DB (client prices never trusted).

- **Product images** — `image_file TEXT` column added to `items` table (auto-migrated on startup). Seeded with Unsplash photo URLs via `seed_item_images.py`.

- **Rich menu updated** — left button now opens LIFF URI directly instead of sending a `"menu"` text message. Requires `LIFF_ID` in `.env` when running `setup_richmenu.py`.

- **Chat simplified** — removed carousel, category picker, ADD: item handler, 結帳, 繼續點餐 handlers from `app.py`. Menu triggers now send a single "Open Menu" Flex bubble with a LIFF URI button.

- **`/liff/submit` updated** — accepts `cart` array in payload instead of reading from `carts` table. `db.cart_clear()` call removed.

### New files

| File | Purpose |
|---|---|
| `liff/templates/liff/menu.html` | 3-screen LIFF mini-app |
| `seed_item_images.py` | One-time script to assign Unsplash URLs to items |

### Files changed

| File | What changed |
|---|---|
| `db.py` | `image_file` column on `items`, `get_menu_for_liff()`, `create_item`/`update_item` support images |
| `liff/routes.py` | New `/liff/menu` route; submit accepts JS cart payload |
| `app.py` | Menu → LIFF button; removed all chat-based ordering handlers |
| `flex_menu.py` | Added `build_open_menu_bubble(liff_url)` |
| `setup_richmenu.py` | Left button uses URI action (LIFF) when `LIFF_ID` is set |
| `CLAUDE.md` | Updated to reflect new architecture |

## 2026-04-08 — Security hardening

Security audit and fixes across the entire codebase.

### CRITICAL fixes

- **CSRF protection on admin panel** — Added `flask-wtf` with `CSRFProtect`.
  All admin POST forms now require a CSRF token (auto-injected via JS in
  `admin/templates/admin/base.html`). The LINE webhook and LIFF blueprint
  are exempt (they use their own auth mechanisms).

- **LIFF submit authentication** — `/liff/submit` no longer trusts the
  client-supplied `user_id`. The LIFF JS now sends `liff.getAccessToken()`,
  and the server verifies it via `api.line.me/oauth2/v2.1/verify` +
  `/v2/profile` before extracting the real user ID. Requires `LINE_CHANNEL_ID`
  env var to validate the token's `client_id`.

- **Admin credentials required** — `ADMIN_USER` and `ADMIN_PASSWORD` now use
  `os.environ[]` (hard crash if missing) instead of `os.getenv()` with
  fallback defaults like `"changeme"`.

### HIGH fixes

- **`FLASK_SECRET_KEY` required** — App crashes on startup if the env var is
  missing, instead of silently generating a random key per worker/restart.

- **Rate limiter memory leak fixed** — `_rate_store` now has periodic cleanup
  of stale user entries (every `RATE_WINDOW` seconds) and a hard cap of 10K
  tracked users to prevent OOM under sustained traffic.

- **Path traversal surface reduced** — `/images/<path:filename>` changed to
  `/images/<filename>` (no sub-path segments).

- **PII no longer logged** — User message content was logged at INFO level;
  now only logs `user_id` and message length.

### MEDIUM fixes

- **Phone number validation** — LIFF submit now validates phone against
  `^[\d\-\+\(\)\s]{7,20}$` regex. Fulfillment type is also whitelisted
  against the three valid values.

### New dependency

- `flask-wtf==1.2.1` (added to `requirements.txt`)

### New required env vars

- `FLASK_SECRET_KEY` — stable secret for Flask sessions and CSRF tokens
- `LINE_CHANNEL_ID` — was already documented but is now actively used for
  LIFF token verification

### Files changed

| File                                | What changed                                                                                                         |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `app.py`                            | CSRF init, secret key required, rate limiter cleanup, PII logging removed, image route narrowed, webhook CSRF-exempt |
| `admin/routes.py`                   | `os.environ[]` for credentials (no fallback)                                                                         |
| `admin/templates/admin/base.html`   | JS auto-injects CSRF token into all POST forms                                                                       |
| `liff/routes.py`                    | `_verify_line_token()` added, submit uses access token, phone + fulfillment validation                               |
| `liff/templates/liff/checkout.html` | JS sends `liff.getAccessToken()` instead of hardcoded `user_id`                                                      |
| `requirements.txt`                  | Added `flask-wtf==1.2.1`                                                                                             |
| `CLAUDE.md`                         | Updated to reflect security measures                                                                                 |
