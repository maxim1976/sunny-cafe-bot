# Sunny Cafe LINE Bot

A LINE chatbot for cafe ordering powered by Claude AI, with kitchen ticket printing via ESC/POS (Epson TM-T20 over WiFi/TCP).

## Stack

| Layer | Tech |
|---|---|
| Web framework | Python + Flask |
| LINE integration | line-bot-sdk-python v3 |
| AI | Anthropic Claude (claude-sonnet-4-6) |
| Conversation history | SQLite |
| Printer | python-escpos via raw TCP |
| Deployment | Railway (Gunicorn) |

---

## Quick Start (Local)

### 1. Clone & install

```bash
git clone <your-repo>
cd sunny-cafe-bot
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your keys
```

### 3. Expose localhost with a tunnel

LINE requires a public HTTPS URL. Use [ngrok](https://ngrok.com) or [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/):

```bash
ngrok http 5000
# Note the https://xxxx.ngrok.io URL
```

### 4. Run the bot

```bash
python app.py
```

---

## Configuring for a New Client

### Menu (`menu.py`)

Edit the `RESTAURANT_INFO` dict and `MENU` dict at the top of `menu.py`:

```python
RESTAURANT_INFO = {
    "name": "Beachside Bistro",
    "address": "...",
    ...
}

MENU = {
    "Mains": {
        "Grilled Salmon": 350,
        "Pasta Carbonara": 280,
    },
    ...
}
```

No other code changes needed – the system prompt auto-generates from the menu.

### Environment (`.env`)

Copy `.env.example` to `.env` and fill in:
- `LINE_CHANNEL_SECRET` and `LINE_CHANNEL_ACCESS_TOKEN` from the LINE Developer Console
- `ANTHROPIC_API_KEY` from console.anthropic.com
- `PRINTER_IP` / `PRINTER_PORT` matching your printer's network settings

---

## Deploy on Railway

### 1. Create a Railway project

```bash
npm install -g @railway/cli
railway login
railway init
```

### 2. Set environment variables

In the Railway dashboard → your service → **Variables**, add all keys from `.env.example`.

> **Tip:** Railway injects `PORT` automatically. Do not set it manually.

### 3. Deploy

```bash
railway up
```

Or connect your GitHub repo in the Railway dashboard for auto-deploys on push.

### 4. Persistent SQLite (optional but recommended)

By default, Railway's filesystem is ephemeral (resets on redeploy). To persist chat history:

- Add a Railway **Volume** and mount it at `/data`
- Set `DATABASE_URL=sqlite:////data/chat.db` (four slashes = absolute path)

Alternatively, swap SQLite for Railway's managed **PostgreSQL** plugin and update `bot.py` to use `psycopg2`.

---

## Setting the LINE Webhook URL

1. Go to [LINE Developers Console](https://developers.line.biz/console/)
2. Select your channel → **Messaging API** tab
3. Under **Webhook settings**, set the URL to:
   ```
   https://<your-railway-domain>.railway.app/webhook
   ```
   or your ngrok URL for local testing
4. Click **Verify** – you should see a success message
5. Enable **Use webhook**

---

## Project Structure

```
sunny-cafe-bot/
├── app.py          # Flask app + LINE webhook handler
├── bot.py          # Claude API logic + conversation history (SQLite)
├── printer.py      # ESC/POS ticket printing via TCP
├── menu.py         # Restaurant menu config (easy to edit per client)
├── requirements.txt
├── Procfile        # Gunicorn entrypoint for Railway
├── .env.example    # Environment variable template
└── README.md
```

---

## Printer Setup (Epson TM-T20)

1. Connect the printer to your WiFi network (use the Epson utility or button sequence in the manual)
2. Print a self-test page to find its IP address
3. Ensure TCP port **9100** is open (this is the default raw print port)
4. Set `PRINTER_IP` in your `.env` to the printer's IP

If the printer is offline when an order is confirmed, the error is logged and the bot continues normally – no crash.

---

## How It Works

```
Customer (LINE) → Webhook → app.py → bot.py (Claude) → reply to customer
                                           │
                              ORDER_CONFIRMED in reply?
                                           │
                                        printer.py → TCP → Epson TM-T20
```

1. Customer sends a text message on LINE
2. `app.py` verifies the LINE signature and routes the event
3. `bot.py` loads the last 10 messages for that `userId` from SQLite, calls Claude, saves the new exchange
4. Claude's system prompt contains the full menu and instructions to append `ORDER_CONFIRMED` when an order is finalized
5. `app.py` strips the trigger, sends the clean reply to the customer, then calls `printer.py`
6. `printer.py` builds an ESC/POS byte string and sends it to the printer over TCP

---

## License

MIT
