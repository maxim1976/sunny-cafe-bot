"""
flex_menu.py - Builds LINE Flex Message JSON for the café menu.
Data source: menu.py (single source of truth — never duplicate menu data here).
"""

import os
import urllib.parse

from menu import MENU, MENU_ZH, RESTAURANT_INFO

# Base URL for serving static images — set BASE_URL in Railway environment variables
_BASE_URL = os.getenv("BASE_URL", "https://web-production-22461.up.railway.app").rstrip("/")

# Image file per category (served from /images/)
_CATEGORY_IMAGE = {
    "Coffee & Espresso":   "coffee.jpg",
    "Non-Coffee":          "non-coffee.jpg",
    "Food":                "food.jpg",
    "Pastries & Desserts": "pastries.jpg",
    "Add-ons":             "addons.jpg",
}

# ── Warm café color palette ───────────────────────────────────────────────────
_HEADER_BG    = "#C8A165"   # amber gold
_HEADER_TEXT  = "#FFFFFF"
_PRICE_COLOR  = "#8B6914"   # golden brown
_BUTTON_COLOR = "#6B4226"   # dark coffee brown
_SEPARATOR    = "#E8D5B7"   # cream

_CATEGORY_EMOJI = {
    "Coffee & Espresso":   "☕",
    "Non-Coffee":          "🍵",
    "Food":                "🍽️",
    "Pastries & Desserts": "🥐",
    "Add-ons":             "✨",
}

# Chinese name shown in the card header (under the English category name)
_CATEGORY_ZH = {
    "Coffee & Espresso":   "咖啡 & 濃縮",
    "Non-Coffee":          "非咖啡飲品",
    "Food":                "餐點",
    "Pastries & Desserts": "麵包 & 甜點",
    "Add-ons":             "加點選項",
}

# Button label: Chinese first, max 20 chars
_BUTTON_LABEL = {
    "Coffee & Espresso":   "☕ 點咖啡 / Coffee",
    "Non-Coffee":          "🍵 點飲品 / Drinks",
    "Food":                "🍽️ 點餐 / Food",
    "Pastries & Desserts": "🥐 點甜點 / Pastries",
    "Add-ons":             "✨ 加點 / Add-ons",
}


# ── Private helpers ───────────────────────────────────────────────────────────

def _item_row(name: str, price: int) -> dict:
    """One horizontal row: Chinese name + English name left, price right."""
    zh_name = MENU_ZH.get(name, name)
    return {
        "type": "box",
        "layout": "horizontal",
        "margin": "sm",
        "contents": [
            {
                "type": "box",
                "layout": "vertical",
                "flex": 3,
                "contents": [
                    {
                        "type": "text",
                        "text": zh_name,
                        "size": "sm",
                        "color": "#333333",
                        "weight": "bold",
                        "wrap": True,
                    },
                    {
                        "type": "text",
                        "text": name,
                        "size": "xxs",
                        "color": "#AAAAAA",
                        "wrap": True,
                    },
                ],
            },
            {
                "type": "text",
                "text": f"NT${price}",
                "size": "sm",
                "color": _PRICE_COLOR,
                "align": "end",
                "flex": 2,
                "weight": "bold",
                "gravity": "center",
            },
        ],
    }


def _category_bubble(category: str, items: dict) -> dict:
    """One Flex bubble card for a single menu category."""
    emoji = _CATEGORY_EMOJI.get(category, "•")
    label = _BUTTON_LABEL.get(category, "點餐 / Order")
    zh_name = _CATEGORY_ZH.get(category, category)

    body_contents = []
    for i, (name, price) in enumerate(items.items()):
        if i > 0:
            body_contents.append(
                {"type": "separator", "color": _SEPARATOR, "margin": "sm"}
            )
        body_contents.append(_item_row(name, price))

    img_file = _CATEGORY_IMAGE.get(category)
    bubble: dict = {"type": "bubble", "size": "mega"}

    if img_file:
        bubble["hero"] = {
            "type": "image",
            "url": f"{_BASE_URL}/images/{img_file}",
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover",
            "action": {
                "type": "message",
                "label": zh_name,
                "text": f"I'd like to order from {category}",
            },
        }

    bubble.update({
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": _HEADER_BG,
            "paddingAll": "16px",
            "contents": [
                {
                    "type": "text",
                    "text": f"{emoji}  {zh_name}",
                    "color": _HEADER_TEXT,
                    "weight": "bold",
                    "size": "md",
                    "wrap": True,
                },
                {
                    "type": "text",
                    "text": category,
                    "color": "#F5E6CC",
                    "size": "xs",
                    "margin": "xs",
                },
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "12px",
            "spacing": "none",
            "contents": body_contents,
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "10px",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": _BUTTON_COLOR,
                    "height": "sm",
                    "action": {
                        "type": "message",
                        "label": label,
                        "text": f"I'd like to order from {category}",
                    },
                }
            ],
        },
    })
    return bubble


# ── Item selection (sent when customer taps a category order button) ──────────

def build_item_selection_bubble(category: str) -> dict:
    """
    A Flex bubble listing all items in a category with prices.
    Sent together with quick reply buttons — customer taps to select an item.
    """
    emoji   = _CATEGORY_EMOJI.get(category, "•")
    zh_name = _CATEGORY_ZH.get(category, category)
    items   = MENU.get(category, {})

    body_contents = []
    for i, (name, price) in enumerate(items.items()):
        if i > 0:
            body_contents.append(
                {"type": "separator", "color": _SEPARATOR, "margin": "sm"}
            )
        body_contents.append(_item_row(name, price))

    bubble: dict = {"type": "bubble", "size": "mega"}

    img_file = _CATEGORY_IMAGE.get(category)
    if img_file:
        bubble["hero"] = {
            "type": "image",
            "url": f"{_BASE_URL}/images/{img_file}",
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover",
        }

    bubble["header"] = {
        "type": "box",
        "layout": "vertical",
        "backgroundColor": _HEADER_BG,
        "paddingAll": "16px",
        "contents": [
            {
                "type": "text",
                "text": f"{emoji}  {zh_name}",
                "color": _HEADER_TEXT,
                "weight": "bold",
                "size": "md",
                "wrap": True,
            },
            {
                "type": "text",
                "text": "👇 點下方按鈕選擇品項",
                "color": "#F5E6CC",
                "size": "xs",
                "margin": "xs",
            },
        ],
    }

    bubble["body"] = {
        "type": "box",
        "layout": "vertical",
        "paddingAll": "12px",
        "spacing": "none",
        "contents": body_contents,
    }

    return bubble


def build_item_quick_replies(category: str) -> dict:
    """
    Quick reply buttons — one per item in the category.
    Label shows Chinese name + price; tapping sends "我要點 {zh_name}".
    """
    items = MENU.get(category, {})
    quick_reply_items = []
    for name, price in items.items():
        zh_name = MENU_ZH.get(name, name)
        label = f"{zh_name} NT${price}"
        if len(label) > 20:
            label = label[:19] + "…"
        quick_reply_items.append({
            "type": "action",
            "action": {
                "type": "message",
                "label": label,
                "text": f"我要點 {zh_name}",
            },
        })
    # Always allow going back to browse other categories
    quick_reply_items.append({
        "type": "action",
        "action": {
            "type": "message",
            "label": "← 返回菜單",
            "text": "menu",
        },
    })
    return {"items": quick_reply_items}


# ── Cart UI ───────────────────────────────────────────────────────────────────

def build_cart_bubble(cart_items: list[dict]) -> dict:
    """
    Flex bubble showing the current cart contents and running total.
    cart_items: [{"name": str, "zh_name": str, "price": int, "qty": int}, ...]
    """
    total = sum(item["price"] * item["qty"] for item in cart_items)

    rows: list[dict] = []
    for i, item in enumerate(cart_items):
        if i > 0:
            rows.append({"type": "separator", "color": _SEPARATOR, "margin": "sm"})
        subtotal = item["price"] * item["qty"]
        rows.append({
            "type": "box",
            "layout": "horizontal",
            "margin": "sm",
            "contents": [
                {
                    "type": "box",
                    "layout": "vertical",
                    "flex": 3,
                    "contents": [
                        {
                            "type": "text",
                            "text": item["zh_name"],
                            "size": "sm",
                            "color": "#333333",
                            "weight": "bold",
                            "wrap": True,
                        },
                        {
                            "type": "text",
                            "text": f"NT${item['price']} × {item['qty']}",
                            "size": "xxs",
                            "color": "#AAAAAA",
                        },
                    ],
                },
                {
                    "type": "text",
                    "text": f"NT${subtotal}",
                    "size": "sm",
                    "color": _PRICE_COLOR,
                    "align": "end",
                    "flex": 2,
                    "weight": "bold",
                    "gravity": "center",
                },
            ],
        })

    rows.append({"type": "separator", "color": _SEPARATOR, "margin": "md"})
    rows.append({
        "type": "box",
        "layout": "horizontal",
        "margin": "md",
        "contents": [
            {
                "type": "text",
                "text": "合計 Total",
                "size": "sm",
                "weight": "bold",
                "color": "#333333",
                "flex": 3,
            },
            {
                "type": "text",
                "text": f"NT${total}",
                "size": "sm",
                "weight": "bold",
                "color": _PRICE_COLOR,
                "align": "end",
                "flex": 2,
            },
        ],
    })

    return {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": _HEADER_BG,
            "paddingAll": "16px",
            "contents": [
                {
                    "type": "text",
                    "text": "🛒 您的購物車",
                    "color": _HEADER_TEXT,
                    "weight": "bold",
                    "size": "md",
                },
                {
                    "type": "text",
                    "text": "Your Cart",
                    "color": "#F5E6CC",
                    "size": "xs",
                    "margin": "xs",
                },
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "12px",
            "spacing": "none",
            "contents": rows,
        },
    }


def build_cart_actions_quick_reply() -> dict:
    """Quick replies shown after adding an item: Add More / Checkout / Cancel."""
    return {
        "items": [
            {
                "type": "action",
                "action": {"type": "message", "label": "➕ 繼續點餐", "text": "繼續點餐"},
            },
            {
                "type": "action",
                "action": {"type": "message", "label": "✅ 去結帳", "text": "結帳"},
            },
            {
                "type": "action",
                "action": {"type": "message", "label": "❌ 取消", "text": "取消訂單"},
            },
        ]
    }


def build_checkout_quick_reply() -> dict:
    """Quick replies shown at checkout: Confirm / Edit / Cancel."""
    return {
        "items": [
            {
                "type": "action",
                "action": {"type": "message", "label": "✅ 確認 Confirm", "text": "確認結帳"},
            },
            {
                "type": "action",
                "action": {"type": "message", "label": "✏️ 修改 Edit", "text": "重新點餐"},
            },
            {
                "type": "action",
                "action": {"type": "message", "label": "❌ 取消 Cancel", "text": "取消訂單"},
            },
        ]
    }


# ── Public API ────────────────────────────────────────────────────────────────

def build_dine_in_info_bubble() -> dict:
    """
    Info card sent when a customer selects dine-in.
    Shows address, hours, phone and a Google Maps button.
    """
    maps_url = "https://maps.google.com/?q=" + urllib.parse.quote(RESTAURANT_INFO["address"])
    return {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": _HEADER_BG,
            "paddingAll": "16px",
            "contents": [
                {
                    "type": "text",
                    "text": "🏠 歡迎內用！",
                    "color": _HEADER_TEXT,
                    "weight": "bold",
                    "size": "lg",
                },
                {
                    "type": "text",
                    "text": "Welcome, we'll have your order ready soon",
                    "color": "#F5E6CC",
                    "size": "xs",
                    "margin": "xs",
                    "wrap": True,
                },
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "16px",
            "spacing": "md",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "sm",
                    "contents": [
                        {"type": "text", "text": "📍", "size": "sm", "flex": 1, "gravity": "top"},
                        {
                            "type": "text",
                            "text": RESTAURANT_INFO["address"],
                            "size": "sm",
                            "color": "#333333",
                            "wrap": True,
                            "flex": 5,
                        },
                    ],
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "sm",
                    "contents": [
                        {"type": "text", "text": "🕐", "size": "sm", "flex": 1, "gravity": "top"},
                        {
                            "type": "text",
                            "text": RESTAURANT_INFO["hours"],
                            "size": "sm",
                            "color": "#333333",
                            "wrap": True,
                            "flex": 5,
                        },
                    ],
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "sm",
                    "contents": [
                        {"type": "text", "text": "📞", "size": "sm", "flex": 1},
                        {
                            "type": "text",
                            "text": RESTAURANT_INFO["phone"],
                            "size": "sm",
                            "color": "#333333",
                            "flex": 5,
                        },
                    ],
                },
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "10px",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": _BUTTON_COLOR,
                    "height": "sm",
                    "action": {
                        "type": "uri",
                        "label": "📍 開啟地圖 Google Maps",
                        "uri": maps_url,
                    },
                }
            ],
        },
    }


def build_welcome_flex() -> dict:
    """
    Welcome Flex bubble sent when a user first adds the bot.
    Explains how to interact in Chinese and English.
    """
    return {
        "type": "bubble",
        "hero": {
            "type": "image",
            "url": f"{_BASE_URL}/images/welcome.jpg",
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover",
            "action": {"type": "uri", "label": "store", "uri": _BASE_URL},
        },
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": _HEADER_BG,
            "paddingAll": "20px",
            "contents": [
                {
                    "type": "text",
                    "text": f"☀️  {RESTAURANT_INFO['name']}",
                    "color": "#FFFFFF",
                    "weight": "bold",
                    "size": "xl",
                },
                {
                    "type": "text",
                    "text": "花蓮 · Hualien, Taiwan",
                    "color": "#F5E6CC",
                    "size": "xs",
                    "margin": "xs",
                },
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "16px",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "歡迎！很高興為您服務 😊",
                    "weight": "bold",
                    "size": "md",
                    "color": "#333333",
                    "wrap": True,
                },
                {
                    "type": "text",
                    "text": "Welcome! We're happy to serve you.",
                    "size": "sm",
                    "color": "#888888",
                    "wrap": True,
                },
                {"type": "separator", "color": _SEPARATOR, "margin": "md"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "md",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "text",
                            "text": "💡 如何點餐 / How to order:",
                            "size": "sm",
                            "weight": "bold",
                            "color": _BUTTON_COLOR,
                        },
                        {
                            "type": "text",
                            "text": "• 點下方按鈕查看完整菜單",
                            "size": "sm",
                            "color": "#555555",
                            "wrap": True,
                        },
                        {
                            "type": "text",
                            "text": "  Tap the button below to browse our menu",
                            "size": "sm",
                            "color": "#999999",
                            "wrap": True,
                        },
                        {
                            "type": "text",
                            "text": "• 或直接告訴我您想點什麼",
                            "size": "sm",
                            "color": "#555555",
                            "wrap": True,
                            "margin": "sm",
                        },
                        {
                            "type": "text",
                            "text": "  Or just tell me what you'd like to order",
                            "size": "sm",
                            "color": "#999999",
                            "wrap": True,
                        },
                    ],
                },
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "12px",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": _BUTTON_COLOR,
                    "action": {
                        "type": "message",
                        "label": "☕ 查看菜單 / View Menu",
                        "text": "menu",
                    },
                }
            ],
        },
    }


def build_menu_carousel() -> dict:
    """
    Return a Flex carousel dict — one bubble per menu category.
    Pass this directly as the `contents` of a FlexMessage.
    """
    return {
        "type": "carousel",
        "contents": [
            _category_bubble(cat, items)
            for cat, items in MENU.items()
        ],
    }


def build_menu_header_bubble() -> dict:
    """
    A small welcome bubble displayed before the carousel.
    Shows café name, hours, and a swipe hint.
    """
    return {
        "type": "bubble",
        "size": "kilo",
        "hero": {
            "type": "image",
            "url": f"{_BASE_URL}/images/welcome.jpg",
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover",
            "action": {"type": "uri", "label": "store", "uri": _BASE_URL},
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "20px",
            "contents": [
                {
                    "type": "text",
                    "text": f"☀️  {RESTAURANT_INFO['name']}",
                    "weight": "bold",
                    "size": "xl",
                    "color": _BUTTON_COLOR,
                },
                {
                    "type": "text",
                    "text": "花蓮 · Hualien",
                    "size": "xs",
                    "color": "#AAAAAA",
                    "margin": "xs",
                },
                {
                    "type": "text",
                    "text": f"🕐  {RESTAURANT_INFO['hours']}",
                    "size": "sm",
                    "color": "#888888",
                    "margin": "md",
                    "wrap": True,
                },
                {
                    "type": "separator",
                    "margin": "lg",
                    "color": _SEPARATOR,
                },
                {
                    "type": "text",
                    "text": "左滑瀏覽菜單  Swipe to browse →",
                    "size": "sm",
                    "color": "#AAAAAA",
                    "margin": "lg",
                    "align": "center",
                },
            ],
        },
    }
