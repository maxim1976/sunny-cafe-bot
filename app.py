"""
app.py - Flask webhook handler for LINE Messaging API
"""

import logging
import os
import time
from collections import defaultdict

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, abort, request
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

import bot
import printer

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)

# ── LINE SDK setup ────────────────────────────────────────────────────────────
LINE_CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Initialize DB on startup (works with both gunicorn and direct run)
bot.init_db()

# ── Rate limiter ──────────────────────────────────────────────────────────────
# Tracks per-user message timestamps (in-memory, resets on redeploy)
MAX_MESSAGES_PER_WINDOW = int(os.getenv("RATE_LIMIT_MESSAGES", "10"))
RATE_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "500"))

_rate_store: dict = defaultdict(list)  # user_id → [timestamps]


def _is_rate_limited(user_id: str) -> bool:
    now = time.time()
    window_start = now - RATE_WINDOW_SECONDS
    timestamps = _rate_store[user_id]
    # Drop timestamps outside the window
    _rate_store[user_id] = [t for t in timestamps if t > window_start]
    if len(_rate_store[user_id]) >= MAX_MESSAGES_PER_WINDOW:
        return True
    _rate_store[user_id].append(now)
    return False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _reply(reply_token: str, text: str) -> None:
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)],
            )
        )


def _handle_confirmed_order(user_id: str) -> None:
    """
    Called after Claude signals ORDER_CONFIRMED.
    Parses the last assistant message and sends a ticket to the printer.
    """
    last_msg = bot.get_last_order_context(user_id)
    order_details = printer.parse_order_from_text(last_msg)

    result = printer.print_order_ticket(
        customer_name=order_details["customer_name"],
        items=order_details["items"],
        total=order_details["total"],
        fulfillment=order_details["fulfillment"],
    )

    if result["success"]:
        logger.info(
            "Order #%s printed for user %s (name: %s)",
            result["order_number"],
            user_id,
            order_details["customer_name"],
        )
    else:
        logger.warning(
            "Order #%s – printer fallback for user %s: %s",
            result["order_number"],
            user_id,
            result["message"],
        )


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return {"status": "ok"}, 200


@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    logger.debug("Webhook body: %s", body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.warning("Invalid LINE signature – request rejected")
        abort(400)

    return "OK"


# ── Event handler ─────────────────────────────────────────────────────────────

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event: MessageEvent):
    user_id: str = event.source.user_id
    user_text: str = event.message.text.strip()
    reply_token: str = event.reply_token

    logger.info("Message from %s: %s", user_id, user_text[:80])

    # ── Rate limit check ──────────────────────────────────────────────────────
    if _is_rate_limited(user_id):
        logger.warning("Rate limit hit for user %s", user_id)
        _reply(reply_token, "Please slow down a little. Try again in a minute.")
        return

    # ── Input length check ────────────────────────────────────────────────────
    if len(user_text) > MAX_MESSAGE_LENGTH:
        logger.warning("Oversized message from %s (%d chars)", user_id, len(user_text))
        _reply(reply_token, "Your message is too long. Please keep it under 500 characters.")
        return

    # Get Claude reply
    reply_text, order_confirmed = bot.get_reply(user_id, user_text)

    # Send reply to user first (keep response time snappy)
    _reply(reply_token, reply_text)

    # Print ticket asynchronously-ish (same process; printer errors don't block)
    if order_confirmed:
        logger.info("ORDER_CONFIRMED signal detected for user %s", user_id)
        _handle_confirmed_order(user_id)


# ── Startup ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    bot.init_db()
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
