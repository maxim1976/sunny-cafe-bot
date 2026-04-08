"""
liff/routes.py - LIFF checkout form served inside LINE browser.
"""

import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from flask import Blueprint, request, jsonify, render_template

import db
import printer

logger = logging.getLogger(__name__)

liff_bp = Blueprint("liff", __name__, template_folder="templates")

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
LIFF_CHANNEL_ID = os.environ.get("LIFF_CHANNEL_ID", "")


def _verify_line_token(access_token: str) -> str | None:
    """Verify a LINE access token and return the user_id, or None on failure."""
    try:
        url = f"https://api.line.me/oauth2/v2.1/verify?access_token={urllib.parse.quote(access_token)}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
        if str(data.get("client_id")) != LIFF_CHANNEL_ID:
            logger.warning("Token client_id mismatch: got %s, expected %s",
                           data.get("client_id"), LIFF_CHANNEL_ID)
            return None
        if data.get("expires_in", 0) <= 0:
            return None
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as exc:
        logger.warning("LINE token verify failed: %s", exc)
        return None

    # Token is valid — get the user profile to extract user_id
    try:
        req = urllib.request.Request(
            "https://api.line.me/v2/profile",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            profile = json.loads(resp.read())
        return profile.get("userId")
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        logger.warning("LINE profile fetch failed: %s", exc)
        return None


# ── LIFF checkout page ────────────────────────────────────────────────────────


@liff_bp.route("/liff/checkout")
def checkout():
    user_id = request.args.get("user_id", "")

    # LIFF wraps query params in liff.state when redirecting:
    # /liff/checkout?liff.state=%3Fuser_id%3D{id}
    if not user_id:
        from urllib.parse import parse_qs, unquote

        liff_state = request.args.get("liff.state", "")
        if liff_state:
            state_params = parse_qs(unquote(liff_state).lstrip("?"))
            user_id = state_params.get("user_id", [""])[0]

    if not user_id:
        return "Missing user_id", 400

    lang = db.get_lang(user_id)
    cart = db.cart_get(user_id)
    if not cart:
        return render_template("liff/empty_cart.html", lang=lang)

    total = sum(i["price"] * i["qty"] for i in cart)
    discounts = db.get_active_discounts()
    info = db.get_store_info()

    return render_template(
        "liff/checkout.html",
        user_id=user_id,
        lang=lang,
        cart=cart,
        total=total,
        discounts=discounts,
        info=info,
        liff_id=os.getenv("LIFF_ID", ""),
    )


# ── LIFF form submission ──────────────────────────────────────────────────────


@liff_bp.route("/liff/submit", methods=["POST"])
def submit():
    data = request.get_json(force=True)

    # Verify LINE identity server-side
    line_token = data.get("access_token", "")
    if not line_token:
        return jsonify({"ok": False, "error": "Missing access token"}), 401
    user_id = _verify_line_token(line_token)
    if not user_id:
        return jsonify({"ok": False, "error": "Invalid or expired token"}), 401

    display_name = data.get("display_name", "")
    customer_name = data.get("customer_name", "").strip()
    phone = data.get("phone", "").strip()
    fulfillment = data.get("fulfillment", "")
    address = data.get("address", "").strip() or None
    pickup_time = data.get("pickup_time", "").strip() or None
    discount_id = data.get("discount_id")
    lang = data.get("lang", "zh")

    # Validate
    _PHONE_RE = re.compile(r"^[\d\-\+\(\)\s]{7,20}$")
    if not all([user_id, customer_name, phone, fulfillment]):
        return jsonify({"ok": False, "error": "Missing required fields"}), 400
    if not _PHONE_RE.match(phone):
        return jsonify({"ok": False, "error": "Invalid phone number"}), 400
    if fulfillment not in ("dine-in", "takeaway", "delivery"):
        return jsonify({"ok": False, "error": "Invalid fulfillment type"}), 400
    if fulfillment == "delivery" and not address:
        return jsonify({"ok": False, "error": "Address required for delivery"}), 400
    if fulfillment in ("dine-in", "takeaway") and not pickup_time:
        return jsonify({"ok": False, "error": "Time is required"}), 400

    cart = db.cart_get(user_id)
    if not cart:
        return jsonify({"ok": False, "error": "Cart is empty"}), 400

    # Calculate total + discount
    subtotal = sum(i["price"] * i["qty"] for i in cart)
    discount_amt = 0
    if discount_id:
        discount = next(
            (d for d in db.get_active_discounts() if d["id"] == int(discount_id)), None
        )
        if discount:
            if discount["type"] == "percent":
                discount_amt = int(subtotal * discount["value"] / 100)
            else:
                discount_amt = min(discount["value"], subtotal)
    total = subtotal - discount_amt

    # Save order
    order = db.create_order(
        user_id=user_id,
        display_name=display_name,
        customer_name=customer_name,
        phone=phone,
        fulfillment=fulfillment,
        address=address,
        pickup_time=pickup_time,
        total=total,
        discount_amt=discount_amt,
    )
    db.add_order_items(
        order["id"],
        [
            {
                "name_en": i["name_en"],
                "name_zh": i["name_zh"],
                "price": i["price"],
                "qty": i["qty"],
            }
            for i in cart
        ],
    )
    db.cart_clear(user_id)

    # Print ticket
    order_items = db.get_order_items(order["id"])
    printer.print_order_ticket(
        order_number=order["id"],
        customer_name=customer_name,
        phone=phone,
        items=[
            {"name": i["name_en"], "qty": i["qty"], "price": i["price"]}
            for i in order_items
        ],
        total=total,
        fulfillment=fulfillment,
    )

    # Send LINE confirmation push message
    _send_confirmation(order, order_items, lang)

    return jsonify({"ok": True, "order_id": order["id"]})


def _send_confirmation(order: dict, items: list[dict], lang: str) -> None:
    import flex_menu

    confirm_bubble = flex_menu.build_order_confirmation_bubble(order, items, lang)
    confirm_qr = flex_menu.build_confirm_quick_reply()

    message = {
        "type": "flex",
        "altText": "Order Confirmation / 訂單確認",
        "contents": confirm_bubble,
        "quickReply": confirm_qr,
    }

    body = json.dumps(
        {
            "to": order["user_id"],
            "messages": [message],
        },
        ensure_ascii=False,
    ).encode("utf-8")

    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/push",
        data=body,
        headers={
            "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            logger.info(
                "Order confirmation sent to %s (status %s)",
                order["user_id"],
                resp.status,
            )
    except urllib.error.HTTPError as exc:
        logger.error(
            "Failed to send confirmation: %s %s", exc.code, exc.read().decode()
        )
