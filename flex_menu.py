"""
flex_menu.py - Builds all LINE Flex Message JSON for Sunny Cafe Bot.
All menu data is read live from PostgreSQL via db.py.
"""

import os
import urllib.parse

import db

_BASE_URL = os.getenv("BASE_URL", "https://web-production-22461.up.railway.app").rstrip(
    "/"
)
_LIFF_ID = os.getenv("LIFF_ID", "")

# ── Palette ───────────────────────────────────────────────────────────────────
_AMBER = "#C8A165"
_COFFEE = "#6B4226"
_CREAM_LIGHT = "#F5E6CC"
_CREAM = "#E8D5B7"
_PRICE_COLOR = "#8B6914"
_WHITE = "#FFFFFF"


# ── Private helpers ───────────────────────────────────────────────────────────


def _item_row(name_en: str, name_zh: str, price: int) -> dict:
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
                        "text": name_zh,
                        "size": "sm",
                        "color": "#333333",
                        "weight": "bold",
                        "wrap": True,
                    },
                    {
                        "type": "text",
                        "text": name_en,
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


def _separator() -> dict:
    return {"type": "separator", "color": _CREAM, "margin": "sm"}


# ── Menu carousel ─────────────────────────────────────────────────────────────


def build_menu_carousel() -> dict:
    categories = db.get_categories(available_only=True)
    bubbles = [_category_bubble(cat) for cat in categories]
    return {"type": "carousel", "contents": bubbles}


def _category_bubble(cat: dict) -> dict:
    items = db.get_items(cat["id"], available_only=True)
    body_contents = []
    for i, item in enumerate(items):
        if i > 0:
            body_contents.append(_separator())
        body_contents.append(_item_row(item["name_en"], item["name_zh"], item["price"]))

    bubble: dict = {"type": "bubble", "size": "mega"}

    if cat.get("image_file"):
        bubble["hero"] = {
            "type": "image",
            "url": f"{_BASE_URL}/images/{cat['image_file']}",
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover",
            "action": {
                "type": "message",
                "label": cat["name_zh"],
                "text": f"I'd like to order from {cat['name_en']}",
            },
        }

    bubble["header"] = {
        "type": "box",
        "layout": "vertical",
        "backgroundColor": _AMBER,
        "paddingAll": "16px",
        "contents": [
            {
                "type": "text",
                "text": f"{cat['emoji']}  {cat['name_zh']}",
                "color": _WHITE,
                "weight": "bold",
                "size": "md",
                "wrap": True,
            },
            {
                "type": "text",
                "text": cat["name_en"],
                "color": _CREAM_LIGHT,
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
    bubble["footer"] = {
        "type": "box",
        "layout": "vertical",
        "paddingAll": "10px",
        "contents": [
            {
                "type": "button",
                "style": "primary",
                "color": _COFFEE,
                "height": "sm",
                "action": {
                    "type": "message",
                    "label": f"{cat['emoji']} 點餐 / Order",
                    "text": f"I'd like to order from {cat['name_en']}",
                },
            }
        ],
    }
    return bubble


def build_menu_header_bubble() -> dict:
    info = db.get_store_info()
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
                    "text": f"☀️  {info.get('name', 'Sunny Cafe')}",
                    "weight": "bold",
                    "size": "xl",
                    "color": _COFFEE,
                },
                {
                    "type": "text",
                    "text": "花蓮 · Hualien",
                    "size": "xs",
                    "color": "#AAAAAA",
                    "margin": "xs",
                },
                {"type": "separator", "margin": "md", "color": _CREAM},
                {
                    "type": "text",
                    "text": f"🕐  {info.get('hours', '')}",
                    "size": "sm",
                    "color": "#888888",
                    "margin": "md",
                    "wrap": True,
                },
                {
                    "type": "text",
                    "text": f"📍  {info.get('address', '')}",
                    "size": "sm",
                    "color": "#888888",
                    "margin": "sm",
                    "wrap": True,
                },
                {
                    "type": "text",
                    "text": f"📞  {info.get('phone', '')}",
                    "size": "sm",
                    "color": "#888888",
                    "margin": "sm",
                },
                {"type": "separator", "margin": "md", "color": _CREAM},
                {
                    "type": "text",
                    "text": "左滑瀏覽菜單  Swipe to browse →",
                    "size": "sm",
                    "color": "#AAAAAA",
                    "margin": "md",
                    "align": "center",
                },
            ],
        },
    }


# ── Item picker ───────────────────────────────────────────────────────────────


def build_item_selection_bubble(cat: dict) -> dict:
    items = db.get_items(cat["id"], available_only=True)
    body_contents = []
    for i, item in enumerate(items):
        if i > 0:
            body_contents.append(_separator())
        body_contents.append(_item_row(item["name_en"], item["name_zh"], item["price"]))

    bubble: dict = {"type": "bubble", "size": "mega"}

    if cat.get("image_file"):
        bubble["hero"] = {
            "type": "image",
            "url": f"{_BASE_URL}/images/{cat['image_file']}",
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover",
        }

    bubble["header"] = {
        "type": "box",
        "layout": "vertical",
        "backgroundColor": _AMBER,
        "paddingAll": "16px",
        "contents": [
            {
                "type": "text",
                "text": f"{cat['emoji']}  {cat['name_zh']}",
                "color": _WHITE,
                "weight": "bold",
                "size": "md",
                "wrap": True,
            },
            {
                "type": "text",
                "text": "👇 點下方按鈕選擇品項 / Tap to select",
                "color": _CREAM_LIGHT,
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


def build_item_quick_replies(cat: dict, lang: str = "zh") -> dict:
    items = db.get_items(cat["id"], available_only=True)
    qr_items = []
    for item in items:
        display = item["name_en"] if lang == "en" else item["name_zh"]
        label = f"{display} NT${item['price']}"
        if len(label) > 20:
            label = label[:19] + "…"
        qr_items.append(
            {
                "type": "action",
                "action": {
                    "type": "message",
                    "label": label,
                    "text": f"ADD:{item['id']}",
                },
            }
        )
    qr_items.append(
        {
            "type": "action",
            "action": {"type": "message", "label": "← 返回 / Back", "text": "menu"},
        }
    )
    return {"items": qr_items}


# ── Cart bubble ───────────────────────────────────────────────────────────────


def build_cart_bubble(cart_items: list[dict], lang: str = "zh") -> dict:
    total = sum(i["price"] * i["qty"] for i in cart_items)
    rows: list[dict] = []
    for i, item in enumerate(cart_items):
        if i > 0:
            rows.append(_separator())
        display = item["name_en"] if lang == "en" else item["name_zh"]
        subtotal = item["price"] * item["qty"]
        rows.append(
            {
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
                                "text": display,
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
            }
        )

    rows += [
        {"type": "separator", "color": _CREAM, "margin": "md"},
        {
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
        },
    ]

    return {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": _AMBER,
            "paddingAll": "16px",
            "contents": [
                {
                    "type": "text",
                    "text": "🛒 您的購物車",
                    "color": _WHITE,
                    "weight": "bold",
                    "size": "md",
                },
                {
                    "type": "text",
                    "text": "Your Cart",
                    "color": _CREAM_LIGHT,
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
    return {
        "items": [
            {
                "type": "action",
                "action": {
                    "type": "message",
                    "label": "➕ 繼續 / Add More",
                    "text": "繼續點餐",
                },
            },
            {
                "type": "action",
                "action": {
                    "type": "message",
                    "label": "✅ 結帳 / Checkout",
                    "text": "結帳",
                },
            },
            {
                "type": "action",
                "action": {
                    "type": "message",
                    "label": "❌ 取消 / Cancel",
                    "text": "取消訂單",
                },
            },
        ]
    }


# ── Checkout button (opens LIFF) ──────────────────────────────────────────────


def build_checkout_bubble(
    cart_items: list[dict], user_id: str, lang: str = "zh"
) -> dict:
    total = sum(i["price"] * i["qty"] for i in cart_items)
    liff_url = f"https://liff.line.me/{_LIFF_ID}?user_id={urllib.parse.quote(user_id)}"
    label = (
        "Fill in details / 填寫資料" if lang == "en" else "填寫資料 / Fill in details"
    )

    cart_bubble = build_cart_bubble(cart_items, lang)
    cart_bubble["footer"] = {
        "type": "box",
        "layout": "vertical",
        "paddingAll": "10px",
        "contents": [
            {
                "type": "button",
                "style": "primary",
                "color": _COFFEE,
                "action": {"type": "uri", "label": label, "uri": liff_url},
            }
        ],
    }
    return cart_bubble


# ── Order confirmation bubble ─────────────────────────────────────────────────


def build_order_confirmation_bubble(
    order: dict, items: list[dict], lang: str = "zh"
) -> dict:
    fulfillment_map = {
        "dine-in": ("內用", "Dine-in"),
        "takeaway": ("外帶", "Takeaway"),
        "delivery": ("外送", "Delivery"),
    }
    ftype = order.get("fulfillment", "")
    fzh, fen = fulfillment_map.get(ftype, (ftype, ftype))
    fulfillment_label = f"{fzh} ({fen})"

    rows: list[dict] = []
    for i, item in enumerate(items):
        if i > 0:
            rows.append(_separator())
        display = item["name_en"] if lang == "en" else item["name_zh"]
        rows.append(
            {
                "type": "box",
                "layout": "horizontal",
                "margin": "sm",
                "contents": [
                    {
                        "type": "text",
                        "text": f"{display} ×{item['qty']}",
                        "size": "sm",
                        "color": "#333333",
                        "flex": 3,
                        "wrap": True,
                    },
                    {
                        "type": "text",
                        "text": f"NT${item['price'] * item['qty']}",
                        "size": "sm",
                        "color": _PRICE_COLOR,
                        "align": "end",
                        "flex": 2,
                        "weight": "bold",
                    },
                ],
            }
        )

    rows += [
        {"type": "separator", "color": _CREAM, "margin": "md"},
        {
            "type": "box",
            "layout": "horizontal",
            "margin": "sm",
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
                    "text": f"NT${order['total']}",
                    "size": "sm",
                    "weight": "bold",
                    "color": _PRICE_COLOR,
                    "align": "end",
                    "flex": 2,
                },
            ],
        },
        {"type": "separator", "color": _CREAM, "margin": "md"},
        {
            "type": "box",
            "layout": "vertical",
            "margin": "md",
            "spacing": "sm",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "姓名 Name",
                            "size": "xs",
                            "color": "#888888",
                            "flex": 2,
                        },
                        {
                            "type": "text",
                            "text": order.get("customer_name", ""),
                            "size": "xs",
                            "color": "#333333",
                            "flex": 3,
                            "wrap": True,
                        },
                    ],
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "電話 Phone",
                            "size": "xs",
                            "color": "#888888",
                            "flex": 2,
                        },
                        {
                            "type": "text",
                            "text": order.get("phone", ""),
                            "size": "xs",
                            "color": "#333333",
                            "flex": 3,
                        },
                    ],
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "取餐 Type",
                            "size": "xs",
                            "color": "#888888",
                            "flex": 2,
                        },
                        {
                            "type": "text",
                            "text": fulfillment_label,
                            "size": "xs",
                            "color": "#333333",
                            "flex": 3,
                        },
                    ],
                },
                *(
                    [
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "時間 Time",
                                    "size": "xs",
                                    "color": "#888888",
                                    "flex": 2,
                                },
                                {
                                    "type": "text",
                                    "text": order.get("pickup_time", ""),
                                    "size": "xs",
                                    "color": "#333333",
                                    "flex": 3,
                                },
                            ],
                        }
                    ]
                    if order.get("pickup_time")
                    else []
                ),
                *(
                    [
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "地址 Addr",
                                    "size": "xs",
                                    "color": "#888888",
                                    "flex": 2,
                                },
                                {
                                    "type": "text",
                                    "text": order.get("address", ""),
                                    "size": "xs",
                                    "color": "#333333",
                                    "flex": 3,
                                    "wrap": True,
                                },
                            ],
                        }
                    ]
                    if order.get("address")
                    else []
                ),
            ],
        },
    ]

    return {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": _AMBER,
            "paddingAll": "16px",
            "contents": [
                {
                    "type": "text",
                    "text": "🧾 訂單確認",
                    "color": _WHITE,
                    "weight": "bold",
                    "size": "md",
                },
                {
                    "type": "text",
                    "text": "Order Confirmation",
                    "color": _CREAM_LIGHT,
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


def build_confirm_quick_reply() -> dict:
    return {
        "items": [
            {
                "type": "action",
                "action": {
                    "type": "message",
                    "label": "✅ 確認 / Confirm",
                    "text": "確認",
                },
            },
            {
                "type": "action",
                "action": {
                    "type": "message",
                    "label": "❌ 取消 / Cancel",
                    "text": "取消訂單",
                },
            },
        ]
    }


# ── Open-menu button bubble ───────────────────────────────────────────────────


def build_open_menu_bubble(liff_url: str) -> dict:
    info = db.get_store_info()
    name    = info.get("name",    "Sunny Cafe")
    address = info.get("address", "")
    phone   = info.get("phone",   "")
    hours   = info.get("hours",   "")

    info_rows = []
    if address:
        info_rows.append({
            "type": "box", "layout": "baseline", "spacing": "sm",
            "contents": [
                {"type": "text", "text": "📍", "size": "sm", "flex": 0},
                {"type": "text", "text": address, "size": "sm", "color": "#555555", "wrap": True, "flex": 1},
            ],
        })
    if phone:
        info_rows.append({
            "type": "box", "layout": "baseline", "spacing": "sm", "margin": "sm",
            "contents": [
                {"type": "text", "text": "📞", "size": "sm", "flex": 0},
                {"type": "text", "text": phone, "size": "sm", "color": "#555555", "flex": 1},
            ],
        })
    if hours:
        info_rows.append({
            "type": "box", "layout": "baseline", "spacing": "sm", "margin": "sm",
            "contents": [
                {"type": "text", "text": "🕐", "size": "sm", "flex": 0},
                {"type": "text", "text": hours, "size": "sm", "color": "#555555", "wrap": True, "flex": 1},
            ],
        })

    body_contents = [
        {
            "type": "text",
            "text": f"☀️  {name}",
            "weight": "bold",
            "size": "lg",
            "color": _COFFEE,
        },
    ]
    if info_rows:
        body_contents.append({
            "type": "box", "layout": "vertical", "margin": "md",
            "contents": info_rows,
        })

    return {
        "type": "bubble",
        "size": "kilo",
        "hero": {
            "type": "image",
            "url": f"{_BASE_URL}/images/welcome.jpg",
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "16px",
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
                    "color": _COFFEE,
                    "action": {
                        "type": "uri",
                        "label": "☕ 瀏覽菜單 / Open Menu",
                        "uri": liff_url,
                    },
                }
            ],
        },
    }


# ── Welcome bubble ────────────────────────────────────────────────────────────


def build_welcome_flex() -> dict:
    info = db.get_store_info()
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
            "backgroundColor": _AMBER,
            "paddingAll": "20px",
            "contents": [
                {
                    "type": "text",
                    "text": f"☀️  {info.get('name', 'Sunny Cafe')}",
                    "color": _WHITE,
                    "weight": "bold",
                    "size": "xl",
                },
                {
                    "type": "text",
                    "text": "花蓮 · Hualien, Taiwan",
                    "color": _CREAM_LIGHT,
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
                {"type": "separator", "color": _CREAM, "margin": "md"},
                {
                    "type": "text",
                    "text": f"🕐  {info.get('hours', '')}",
                    "size": "sm",
                    "color": "#888888",
                    "margin": "md",
                    "wrap": True,
                },
                {
                    "type": "text",
                    "text": f"📍  {info.get('address', '')}",
                    "size": "sm",
                    "color": "#888888",
                    "margin": "sm",
                    "wrap": True,
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
                    "color": _COFFEE,
                    "action": {
                        "type": "message",
                        "label": "☕ 查看菜單 / View Menu",
                        "text": "menu",
                    },
                }
            ],
        },
    }


# ── Dine-in info bubble ───────────────────────────────────────────────────────


def build_dine_in_info_bubble() -> dict:
    info = db.get_store_info()
    maps_url = info.get("maps_url") or (
        "https://maps.google.com/?q=" + urllib.parse.quote(info.get("address", ""))
    )
    return {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": _AMBER,
            "paddingAll": "16px",
            "contents": [
                {
                    "type": "text",
                    "text": "🏠 歡迎內用！",
                    "color": _WHITE,
                    "weight": "bold",
                    "size": "lg",
                },
                {
                    "type": "text",
                    "text": "Welcome, dine with us!",
                    "color": _CREAM_LIGHT,
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
                        {
                            "type": "text",
                            "text": "📍",
                            "size": "sm",
                            "flex": 1,
                            "gravity": "top",
                        },
                        {
                            "type": "text",
                            "text": info.get("address", ""),
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
                        {
                            "type": "text",
                            "text": "🕐",
                            "size": "sm",
                            "flex": 1,
                            "gravity": "top",
                        },
                        {
                            "type": "text",
                            "text": info.get("hours", ""),
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
                            "text": info.get("phone", ""),
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
                    "color": _COFFEE,
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
