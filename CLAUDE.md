# Sunny Cafe Bot — Claude Code Guide

## Project overview
LINE ordering bot for a café in Hualien, Taiwan. Flask webhook on Railway,
conversational ordering handled by Claude (claude-sonnet-4-6), Flex Message UI
built in `flex_menu.py`.

## Stack
- **Platform:** LINE Messaging API (line-bot-sdk 3.11.0)
- **Backend:** Flask + Gunicorn on Railway
- **AI:** Anthropic Claude API (`anthropic` SDK)
- **DB:** SQLite (chat history per user)
- **Printer:** Epson ESC/POS over TCP (optional, falls back gracefully)

## Key files
| File | Purpose |
|------|---------|
| `menu.py` | **Single source of truth** for all menu data — never duplicate here |
| `flex_menu.py` | Builds all Flex Message JSON (menu carousel, item picker, welcome) |
| `app.py` | Flask webhook, message routing, intercept logic |
| `bot.py` | Claude API calls, SQLite conversation history |
| `printer.py` | Order ticket parsing + ESC/POS printing |
| `setup_richmenu.py` | One-time script to register the LINE rich menu |

## Architecture — message routing in app.py
```
Incoming message
  ├─ rate limit / length check
  ├─ exact match in _MENU_TRIGGERS           → show menu carousel (no Claude)
  ├─ "I'd like to order from {category}"    → show item picker + quick replies (no Claude)
  ├─ "我要點 {zh_name}"                      → add to cart, show cart bubble (no Claude)
  ├─ "繼續點餐"                               → show menu carousel (no Claude)
  ├─ "結帳"                                  → show cart + Confirm/Edit/Cancel (no Claude)
  ├─ "確認結帳"                               → pass cart to Claude for fulfillment
  ├─ "重新點餐"                               → clear cart, show menu (no Claude)
  ├─ "取消訂單"                               → clear cart, cancel message (no Claude)
  ├─ "切換語言" / language triggers           → toggle EN/ZH preference (no Claude)
  └─ everything else                         → bot.get_reply() → Claude
```

## Cart flow (in-memory, resets on redeploy)
- `_CARTS` in `app.py`: user_id → list of `{name, zh_name, price, qty}`
- `_ZH_TO_ITEM`: reverse lookup zh_name → item info (built from `MENU` + `MENU_ZH`)
- Items added via quick reply buttons; same item tapped twice increments qty
- Cart is cleared on order confirmed (`ORDER_CONFIRMED`) or cancel

## Language preference
- `_LANG_PREF` in `app.py`: user_id → `"zh"` (default) or `"en"`
- Rich menu language button toggles between zh/en per user
- Preference passed to `bot.get_reply()` → Claude system prompt locks the language

## Claude's role (post-cart)
Claude is only invoked after cart confirmation (`確認結帳`) or for free-text messages.
It handles: fulfillment type → real name → phone → pickup time/address → order summary.
LINE display name is used for greeting only — never on the ticket.

## Flex Message conventions
- Color palette: amber gold `#C8A165`, coffee brown `#6B4226`, cream `#E8D5B7`
- Always Traditional Chinese labels; English as subtitle/secondary
- Images served from `/images/` on Railway (`BASE_URL` env var)
- Pass Flex dicts directly via raw `urllib.request` (SDK serialization bypassed)

## Environment variables (set in Railway dashboard)
```
LINE_CHANNEL_SECRET
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_ID
ANTHROPIC_API_KEY
BASE_URL               # e.g. https://web-production-22461.up.railway.app
DATABASE_URL           # sqlite:///chat.db
PRINTER_IP             # optional, kitchen printer TCP IP
PRINTER_PORT           # optional, default 9100
PORT                   # injected by Railway automatically
```

## Deploy
Push to `main` → Railway auto-deploys.
```bash
git add <files>
git commit -m "..."
git push origin main
```

## Local dev
```bash
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
# copy .env with real keys
python app.py
# expose with: ngrok http 5000
```

## Rules
- `menu.py` is the only place to add/edit menu items or prices
- `MENU_ZH` in `menu.py` must have a Chinese translation for every item
- Category button text `"I'd like to order from {category}"` is intercepted in
  `app.py` — do not change it without updating `_CATEGORY_FROM_TRIGGER`
- Never commit `.env` — secrets live in Railway environment only
