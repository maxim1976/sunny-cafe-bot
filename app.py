"""
app.py - Flask webhook handler for Sunny Cafe LINE Bot.
"""

import json
import logging
import os
import time
import urllib.error
import urllib.request
from collections import defaultdict

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, abort, request, send_from_directory
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import ApiClient, Configuration, MessagingApi
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent

import db
import bot
import printer
import flex_menu
from liff.routes import liff_bp
from admin.routes import admin_bp

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24))
app.register_blueprint(liff_bp)
app.register_blueprint(admin_bp)

# ── LINE SDK setup ────────────────────────────────────────────────────────────
LINE_CHANNEL_SECRET      = os.environ["LINE_CHANNEL_SECRET"]
LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ── DB init ───────────────────────────────────────────────────────────────────
db.init_pool()
db.init_schema()

# ── Rate limiter ──────────────────────────────────────────────────────────────
MAX_MESSAGES   = int(os.getenv("RATE_LIMIT_MESSAGES", "10"))
RATE_WINDOW    = int(os.getenv("RATE_LIMIT_WINDOW",   "60"))
MAX_MSG_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH",  "500"))
_rate_store: dict = defaultdict(list)


def _is_rate_limited(user_id: str) -> bool:
    now = time.time()
    cutoff = now - RATE_WINDOW
    _rate_store[user_id] = [t for t in _rate_store[user_id] if t > cutoff]
    if len(_rate_store[user_id]) >= MAX_MESSAGES:
        return True
    _rate_store[user_id].append(now)
    return False


# ── LINE API helpers ──────────────────────────────────────────────────────────

def _send(reply_token: str, messages: list[dict]) -> None:
    body = json.dumps(
        {"replyToken": reply_token, "messages": messages},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/reply",
        data=body,
        headers={
            "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            logger.info("Reply sent (%d msg, status %s)", len(messages), resp.status)
    except urllib.error.HTTPError as exc:
        logger.error("LINE API error: %s %s", exc.code, exc.read().decode())
        raise


def _text(reply_token: str, text: str, quick_reply: dict | None = None) -> None:
    msg: dict = {"type": "text", "text": text}
    if quick_reply:
        msg["quickReply"] = quick_reply
    _send(reply_token, [msg])


def _flex(reply_token: str, alt_text: str, contents: dict,
          quick_reply: dict | None = None) -> None:
    msg: dict = {"type": "flex", "altText": alt_text, "contents": contents}
    if quick_reply:
        msg["quickReply"] = quick_reply
    _send(reply_token, [msg])


def _get_display_name(user_id: str) -> str | None:
    try:
        with ApiClient(configuration) as api_client:
            profile = MessagingApi(api_client).get_profile(user_id)
            return profile.display_name
    except Exception as exc:
        logger.warning("Could not fetch LINE profile for %s: %s", user_id, exc)
        return None


# ── Menu triggers ─────────────────────────────────────────────────────────────
_MENU_TRIGGERS = {
    "menu", "菜單", "show menu", "view menu", "see menu", "our menu",
    "看菜單", "點餐", "我想點", "เมนู",
}


def _is_menu_request(text: str) -> bool:
    return text.lower().strip() in _MENU_TRIGGERS


# ── Category triggers ─────────────────────────────────────────────────────────

def _get_category_from_trigger(text: str) -> dict | None:
    """Return category dict if text matches 'I'd like to order from {name_en}'."""
    if not text.startswith("I'd like to order from "):
        return None
    name_en = text[len("I'd like to order from "):]
    cats = db.get_categories(available_only=True)
    return next((c for c in cats if c["name_en"] == name_en), None)


# ── Item trigger ──────────────────────────────────────────────────────────────

def _get_item_id_from_trigger(text: str) -> int | None:
    """Return item_id if text matches 'ADD:{id}'."""
    if text.startswith("ADD:"):
        try:
            return int(text[4:])
        except ValueError:
            pass
    return None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/images/<path:filename>")
def serve_image(filename):
    return send_from_directory("images", filename)


@app.route("/health")
def health():
    return {"status": "ok"}, 200


@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.warning("Invalid LINE signature")
        abort(400)
    return "OK"


# ── Event handlers ────────────────────────────────────────────────────────────

@handler.add(FollowEvent)
def handle_follow(event: FollowEvent):
    _send(event.reply_token, [
        {"type": "flex", "altText": "歡迎來到 Sunny Cafe！",
         "contents": flex_menu.build_welcome_flex()},
        {"type": "flex", "altText": "☀️ Sunny Cafe Menu",
         "contents": flex_menu.build_menu_carousel()},
    ])
    logger.info("Follow event — welcome sent")


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event: MessageEvent):
    user_id    = event.source.user_id
    text       = event.message.text.strip()
    reply_token = event.reply_token

    logger.info("Message from %s: %s", user_id, text[:80])

    # ── Rate limit ────────────────────────────────────────────────────────────
    if _is_rate_limited(user_id):
        _text(reply_token, "請稍慢一點，一分鐘後再試。\nPlease slow down — try again in a minute.")
        return

    if len(text) > MAX_MSG_LENGTH:
        _text(reply_token, "訊息太長了。\nMessage too long.")
        return

    lang = db.get_lang(user_id)

    # ── Language toggle ───────────────────────────────────────────────────────
    if text in ("切換語言", "Switch to English", "English", "EN", "切換英文",
                "Switch to Chinese", "中文", "ZH", "切換中文"):
        new_lang = "en" if lang == "zh" else "zh"
        db.set_lang(user_id, new_lang)
        if new_lang == "en":
            _text(reply_token, "Switched to English 🇬🇧\nTap the language button again to switch back.")
        else:
            _text(reply_token, "已切換為中文 🇹🇼")
        return

    # ── Menu ──────────────────────────────────────────────────────────────────
    if _is_menu_request(text):
        _send(reply_token, [
            {"type": "flex", "altText": "☀️ Sunny Cafe Menu",
             "contents": flex_menu.build_menu_header_bubble()},
            {"type": "flex", "altText": "瀏覽菜單 Browse menu →",
             "contents": flex_menu.build_menu_carousel()},
        ])
        return

    # ── Category selected ─────────────────────────────────────────────────────
    cat = _get_category_from_trigger(text)
    if cat:
        bubble = flex_menu.build_item_selection_bubble(cat)
        qr     = flex_menu.build_item_quick_replies(cat, lang)
        msg = {
            "type": "flex",
            "altText": f"{cat['name_zh']} — 請選擇品項",
            "contents": bubble,
            "quickReply": qr,
        }
        _send(reply_token, [msg])
        return

    # ── Item added to cart ────────────────────────────────────────────────────
    item_id = _get_item_id_from_trigger(text)
    if item_id is not None:
        item = db.get_item(item_id)
        if item and item["available"]:
            db.cart_add(user_id, item_id)
            cart = db.cart_get(user_id)
            msg = {
                "type": "flex",
                "altText": f"Added: {item['name_en']}",
                "contents": flex_menu.build_cart_bubble(cart, lang),
                "quickReply": flex_menu.build_cart_actions_quick_reply(),
            }
            _send(reply_token, [msg])
        else:
            _text(reply_token, "Item not found / 找不到品項")
        return

    # ── Cart: add more ────────────────────────────────────────────────────────
    if text == "繼續點餐":
        _send(reply_token, [
            {"type": "flex", "altText": "☀️ Sunny Cafe Menu",
             "contents": flex_menu.build_menu_carousel()},
        ])
        return

    # ── Cart: checkout → open LIFF ────────────────────────────────────────────
    if text == "結帳":
        cart = db.cart_get(user_id)
        if not cart:
            _text(reply_token, "Your cart is empty.\n購物車是空的。")
            return
        bubble = flex_menu.build_checkout_bubble(cart, user_id, lang)
        _flex(reply_token, "Confirm your order / 確認訂單", bubble)
        return

    # ── Cart: clear / cancel ──────────────────────────────────────────────────
    if text in ("重新點餐", "取消訂單"):
        db.cart_clear(user_id)
        _text(reply_token,
              "Order cancelled. Tap the menu to start again.\n訂單已取消。")
        return

    # ── Order confirmed (from push message quick reply) ───────────────────────
    if text.lower() in ("確認", "confirm"):
        # Order was already saved by LIFF submit — just acknowledge
        if lang == "en":
            _text(reply_token, "Thank you! Your order is confirmed. We'll have it ready soon! ☀️")
        else:
            _text(reply_token, "感謝您的訂單！我們將盡快為您準備。☀️")
        return

    # ── First-time users get menu carousel alongside Claude reply ─────────────
    is_first = not db.has_history(user_id)
    display_name = _get_display_name(user_id)
    reply = bot.get_reply(user_id, text, display_name, lang)

    messages: list[dict] = [{"type": "text", "text": reply}]
    if is_first:
        messages.append({
            "type": "flex",
            "altText": "☀️ Sunny Cafe Menu",
            "contents": flex_menu.build_menu_carousel(),
        })
    _send(reply_token, messages)


# ── Startup ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
