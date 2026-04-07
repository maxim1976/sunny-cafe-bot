"""
app.py - Flask webhook handler for LINE Messaging API
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

import bot
import printer
import flex_menu
from menu import MENU, MENU_ZH

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

# Phrase injected by the system prompt into every order summary
_ORDER_SUMMARY_MARKER = "確認請回覆「確認」或 confirm"

_CONFIRM_QUICK_REPLY = {
    "items": [
        {
            "type": "action",
            "action": {"type": "message", "label": "✅ 確認 Confirm", "text": "確認"},
        },
        {
            "type": "action",
            "action": {"type": "message", "label": "✏️ 修改 Modify",  "text": "我想修改訂單"},
        },
        {
            "type": "action",
            "action": {"type": "message", "label": "❌ 取消 Cancel",  "text": "取消訂單"},
        },
    ]
}

_FULFILLMENT_QUICK_REPLY = {
    "items": [
        {
            "type": "action",
            "action": {"type": "message", "label": "🏠 內用 Dine-in",    "text": "內用"},
        },
        {
            "type": "action",
            "action": {"type": "message", "label": "🛍 外帶 Takeaway",   "text": "外帶"},
        },
        {
            "type": "action",
            "action": {"type": "message", "label": "🛵 外送 Delivery",   "text": "外送"},
        },
    ]
}


def _is_fulfillment_question(text: str) -> bool:
    """True when Claude is asking the customer to choose a fulfillment method."""
    return "內用" in text and "外帶" in text and "外送" in text


def _reply_text_raw(reply_token: str, text: str, quick_reply: dict | None = None) -> None:
    """Send a text message via raw LINE API, with optional Quick Reply buttons."""
    message: dict = {"type": "text", "text": text}
    if quick_reply:
        message["quickReply"] = quick_reply
    body = json.dumps(
        {"replyToken": reply_token, "messages": [message]},
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
            logger.info("Text reply sent (status %s)", resp.status)
    except urllib.error.HTTPError as exc:
        logger.error("LINE API error sending text: %s %s", exc.code, exc.read().decode())
        raise


def _reply_flex(reply_token: str, payloads: list[tuple[str, dict]]) -> None:
    """
    Send Flex Messages via raw LINE reply API.
    Bypasses the SDK's FlexMessage serialization which doesn't handle plain dicts.
    payloads: list of (alt_text, flex_contents_dict)
    """
    messages = [
        {"type": "flex", "altText": alt_text, "contents": contents}
        for alt_text, contents in payloads
    ]
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
            logger.info("Flex reply sent (status %s)", resp.status)
    except urllib.error.HTTPError as exc:
        logger.error("LINE API error sending Flex: %s %s", exc.code, exc.read().decode())
        raise


def _reply_messages(reply_token: str, messages: list[dict]) -> None:
    """Send up to 5 mixed messages (text, flex, etc.) in a single LINE reply."""
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
            logger.info("Reply sent (%d message(s), status %s)", len(messages), resp.status)
    except urllib.error.HTTPError as exc:
        logger.error("LINE API error: %s %s", exc.code, exc.read().decode())
        raise


def _reply_menu(reply_token: str) -> None:
    """Send the visual menu: welcome bubble + category carousel."""
    _reply_flex(reply_token, [
        ("☀️ Sunny Cafe Menu", flex_menu.build_menu_header_bubble()),
        ("瀏覽菜單 Browse our menu →", flex_menu.build_menu_carousel()),
    ])


# ── Language preference ───────────────────────────────────────────────────────
# Stores per-user language lock: "zh" (default) or "en"
_LANG_PREF: dict[str, str] = {}


def _get_lang(user_id: str) -> str:
    return _LANG_PREF.get(user_id, "zh")


# ── Cart ──────────────────────────────────────────────────────────────────────
# Reverse lookup: zh_name → {"name": str, "price": int}
_ZH_TO_ITEM: dict[str, dict] = {
    MENU_ZH.get(name, name): {"name": name, "price": price}
    for cat_items in MENU.values()
    for name, price in cat_items.items()
}


def _cart_add(user_id: str, zh_name: str) -> bool:
    """Add one of zh_name to the cart. Returns False if item not found."""
    item_info = _ZH_TO_ITEM.get(zh_name)
    if not item_info:
        return False
    bot.cart_add(user_id, item_info["name"], zh_name, item_info["price"])
    return True


def _cart_clear(user_id: str) -> None:
    bot.cart_clear(user_id)


def _cart_to_order_text(user_id: str, lang: str = "zh") -> str:
    """Build the order string passed to Claude after cart confirmation."""
    cart = bot.cart_get(user_id)
    if lang == "en":
        items_str = ", ".join(f"{e['name']} x{e['qty']}" for e in cart)
        return f"I'd like to order: {items_str}"
    items_str = "、".join(f"{e['zh_name']} x{e['qty']}" for e in cart)
    return f"我要點：{items_str}"


# ── Keywords that trigger the visual menu (exact match, case-insensitive)
_MENU_TRIGGERS = {
    "menu", "เมนู", "show menu", "see menu", "view menu", "our menu",
    "菜單", "看菜單", "點餐", "我想點", "我要點菜",
}


def _is_menu_request(text: str) -> bool:
    return text.lower().strip() in _MENU_TRIGGERS


# Category selection — sent by Flex Message buttons in the menu carousel
_CATEGORY_ORDER_TRIGGER = "I'd like to order from "
_CATEGORY_FROM_TRIGGER = {
    f"I'd like to order from {cat}": cat
    for cat in MENU
}


def _get_ordered_category(text: str) -> str | None:
    """Return the category name if the text is a category-order trigger, else None."""
    return _CATEGORY_FROM_TRIGGER.get(text)


def _reply_item_selection(reply_token: str, category: str, lang: str = "zh") -> None:
    """Send item selection bubble + quick reply buttons for a category."""
    bubble = flex_menu.build_item_selection_bubble(category)
    quick_reply = flex_menu.build_item_quick_replies(category, lang)
    zh_name = flex_menu._CATEGORY_ZH.get(category, category)

    message = {
        "type": "flex",
        "altText": f"{zh_name} — 請點選您想要的品項 👇",
        "contents": bubble,
        "quickReply": quick_reply,
    }
    body = json.dumps(
        {"replyToken": reply_token, "messages": [message]},
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
            logger.info("Item selection sent for category '%s' (status %s)", category, resp.status)
    except urllib.error.HTTPError as exc:
        logger.error("LINE API error sending item selection: %s %s", exc.code, exc.read().decode())
        raise


def _handle_confirmed_order(user_id: str) -> None:
    """
    Called after Claude signals ORDER_CONFIRMED.
    Parses the last assistant message and sends a ticket to the printer.
    """
    last_msg = bot.get_last_order_context(user_id)
    order_details = printer.parse_order_from_text(last_msg)

    result = printer.print_order_ticket(
        customer_name=order_details["customer_name"],
        phone=order_details["phone"],
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


def _get_line_display_name(user_id: str) -> str | None:
    """Fetch the user's LINE display name via the Messaging API."""
    try:
        with ApiClient(configuration) as api_client:
            profile = MessagingApi(api_client).get_profile(user_id)
            return profile.display_name
    except Exception as exc:
        logger.warning("Could not fetch LINE profile for %s: %s", user_id, exc)
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
    logger.debug("Webhook body: %s", body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.warning("Invalid LINE signature – request rejected")
        abort(400)

    return "OK"


# ── Event handlers ────────────────────────────────────────────────────────────

@handler.add(FollowEvent)
def handle_follow(event: FollowEvent):
    """Sent when a user adds the bot — welcome message + menu carousel."""
    _reply_flex(event.reply_token, [
        ("歡迎來到 Sunny Cafe！Welcome!", flex_menu.build_welcome_flex()),
        ("☀️ Sunny Cafe Menu", flex_menu.build_menu_carousel()),
    ])
    logger.info("Follow event — welcome sent")


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event: MessageEvent):
    user_id: str = event.source.user_id
    user_text: str = event.message.text.strip()
    reply_token: str = event.reply_token

    logger.info("Message from %s: %s", user_id, user_text[:80])

    # ── Rate limit check ──────────────────────────────────────────────────────
    if _is_rate_limited(user_id):
        logger.warning("Rate limit hit for user %s", user_id)
        _reply_text_raw(reply_token, "請稍慢一點，一分鐘後再試。\nPlease slow down. Try again in a minute.")
        return

    # ── Input length check ────────────────────────────────────────────────────
    if len(user_text) > MAX_MESSAGE_LENGTH:
        logger.warning("Oversized message from %s (%d chars)", user_id, len(user_text))
        _reply_text_raw(reply_token, "訊息太長了，請保持在500字以內。\nMessage too long. Please keep it under 500 characters.")
        return

    # ── Menu shortcut ─────────────────────────────────────────────────────────
    if _is_menu_request(user_text):
        _reply_menu(reply_token)
        return

    # ── Language switch ───────────────────────────────────────────────────────
    if user_text in ("切換語言", "切換英文", "Switch to English", "English", "EN"):
        if _get_lang(user_id) == "zh":
            _LANG_PREF[user_id] = "en"
            _reply_text_raw(reply_token, "Switched to English 🇬🇧 — I'll reply in English from now on.\nTap the language button again to switch back to Chinese.")
        else:
            _LANG_PREF[user_id] = "zh"
            _reply_text_raw(reply_token, "已切換為中文 🇹🇼 — 之後將以中文回覆。")
        return

    # ── Category selected → show item picker (never reaches Claude) ───────────
    category = _get_ordered_category(user_text)
    if category:
        _reply_item_selection(reply_token, category, _get_lang(user_id))
        return

    # ── Cart: item added via quick reply ("我要點 {zh_name}") ─────────────────
    if user_text.startswith("我要點 "):
        zh_name = user_text[4:].strip()
        if _cart_add(user_id, zh_name):
            cart = bot.cart_get(user_id)
            lang = _get_lang(user_id)
            msg = {
                "type": "flex",
                "altText": f"Added: {zh_name}",
                "contents": flex_menu.build_cart_bubble(cart, lang),
                "quickReply": flex_menu.build_cart_actions_quick_reply(),
            }
            _reply_messages(reply_token, [msg])
        else:
            _reply_text_raw(reply_token, f"Item not found. Please select from the menu.")
        return

    # ── Cart: add more items ──────────────────────────────────────────────────
    if user_text == "繼續點餐":
        _reply_menu(reply_token)
        return

    # ── Cart: go to checkout — show cart + confirm/edit/cancel ────────────────
    if user_text == "結帳":
        cart = bot.cart_get(user_id)
        if not cart:
            _reply_text_raw(reply_token, "Your cart is empty. Please select items first.\n購物車是空的，請先選擇品項。")
            return
        msg = {
            "type": "flex",
            "altText": "Confirm your order / 確認您的訂單",
            "contents": flex_menu.build_cart_bubble(cart, _get_lang(user_id)),
            "quickReply": flex_menu.build_checkout_quick_reply(),
        }
        _reply_messages(reply_token, [msg])
        return

    # ── Cart: confirmed → hand order to Claude for fulfillment ────────────────
    if user_text == "確認結帳":
        cart = bot.cart_get(user_id)
        if not cart:
            _reply_text_raw(reply_token, "Your cart is empty. Please select items first.\n購物車是空的，請先選擇品項。")
            return
        order_text = _cart_to_order_text(user_id, _get_lang(user_id))
        display_name = _get_line_display_name(user_id)
        reply_text, order_confirmed = bot.get_reply(user_id, order_text, display_name, _get_lang(user_id))
        text_msg: dict = {"type": "text", "text": reply_text}
        if _ORDER_SUMMARY_MARKER in reply_text:
            text_msg["quickReply"] = _CONFIRM_QUICK_REPLY
        elif _is_fulfillment_question(reply_text):
            text_msg["quickReply"] = _FULFILLMENT_QUICK_REPLY
        _reply_messages(reply_token, [text_msg])
        if order_confirmed:
            _cart_clear(user_id)
            _handle_confirmed_order(user_id)
        return

    # ── Cart: edit → clear cart and show menu ─────────────────────────────────
    if user_text == "重新點餐":
        _cart_clear(user_id)
        _reply_menu(reply_token)
        return

    # ── Cart: cancel ──────────────────────────────────────────────────────────
    if user_text == "取消訂單":
        _cart_clear(user_id)
        _reply_text_raw(
            reply_token,
            "Order cancelled. Tap the menu button to start again.\n訂單已取消。如需重新點餐，請點選下方菜單。",
        )
        return

    # Check if this is the user's first message before history is written
    is_first_message = not bot.has_history(user_id)

    display_name = _get_line_display_name(user_id)

    # Get Claude reply
    reply_text, order_confirmed = bot.get_reply(user_id, user_text, display_name, _get_lang(user_id))

    messages = []

    # Dine-in: prepend store info card with address, hours, and map link
    if user_text.strip() == "內用":
        messages.append({
            "type": "flex",
            "altText": "☀️ Sunny Cafe — 店內資訊",
            "contents": flex_menu.build_dine_in_info_bubble(),
        })

    # Build text message and attach the right quick replies
    text_msg: dict = {"type": "text", "text": reply_text}
    if _ORDER_SUMMARY_MARKER in reply_text:
        text_msg["quickReply"] = _CONFIRM_QUICK_REPLY
    elif _is_fulfillment_question(reply_text):
        text_msg["quickReply"] = _FULFILLMENT_QUICK_REPLY

    messages.append(text_msg)

    # First-time users get the menu carousel so they know what's available
    # (especially desktop users who don't see the rich menu)
    if is_first_message:
        messages.append({
            "type": "flex",
            "altText": "☀️ Sunny Cafe Menu",
            "contents": flex_menu.build_menu_carousel(),
        })

    _reply_messages(reply_token, messages)

    # Print ticket asynchronously-ish (same process; printer errors don't block)
    if order_confirmed:
        _cart_clear(user_id)
        logger.info("ORDER_CONFIRMED signal detected for user %s", user_id)
        _handle_confirmed_order(user_id)


# ── Startup ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    bot.init_db()
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
