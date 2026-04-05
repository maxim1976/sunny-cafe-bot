"""
flex_menu.py - Builds LINE Flex Message JSON for the café menu.
Data source: menu.py (single source of truth — never duplicate menu data here).
"""

from menu import MENU, RESTAURANT_INFO

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

def _item_row(name: str, price: int, currency: str) -> dict:
    """One horizontal row: item name left, price right."""
    return {
        "type": "box",
        "layout": "horizontal",
        "margin": "sm",
        "contents": [
            {
                "type": "text",
                "text": name,
                "size": "sm",
                "color": "#333333",
                "flex": 3,
                "wrap": True,
            },
            {
                "type": "text",
                "text": f"NT$ {price}",
                "size": "sm",
                "color": _PRICE_COLOR,
                "align": "end",
                "flex": 2,
                "weight": "bold",
            },
        ],
    }


def _category_bubble(category: str, items: dict, currency: str) -> dict:
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
        body_contents.append(_item_row(name, price, currency))

    return {
        "type": "bubble",
        "size": "kilo",
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
    currency = RESTAURANT_INFO["currency"]
    return {
        "type": "carousel",
        "contents": [
            _category_bubble(cat, items, currency)
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
