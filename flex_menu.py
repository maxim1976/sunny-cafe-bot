"""
flex_menu.py - Builds LINE Flex Message JSON for the café menu.
Data source: menu.py (single source of truth — never duplicate menu data here).
"""

import os

from menu import MENU, MENU_ZH, RESTAURANT_INFO

# Base URL for serving static images — set BASE_URL in Railway environment variables
_BASE_URL = os.getenv("BASE_URL", "https://web-production-22461.up.railway.app").rstrip("/")

# Image file per category (served from /images/)
_CATEGORY_IMAGE = {
    "Coffee & Espresso":   "coffee.jpg",
    "Non-Coffee":          "non-coffee.jpg",
    "Food":                "food.jpg",
    "Pastries & Desserts": "pastries.jpg",
    "Add-ons":             None,   # no hero image for add-ons
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
    }


# ── Public API ────────────────────────────────────────────────────────────────

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
