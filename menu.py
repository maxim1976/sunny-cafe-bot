"""
menu.py - Restaurant menu configuration
Easy to customize per client: just edit the MENU dict and RESTAURANT_INFO.
"""

RESTAURANT_INFO = {
    "name": "Sunny Cafe",
    "address": "花蓮市中正路 88 號",
    "phone": "03-888-8888",
    "hours": "每日 08:00 - 20:00 / Daily 08:00 - 20:00",
    "currency": "TWD",
}

# Structure: { "Category": { "Item Name": price, ... }, ... }
MENU = {
    "Coffee & Espresso": {
        "Espresso": 55,
        "Americano": 60,
        "Latte": 75,
        "Cappuccino": 75,
        "Mocha": 80,
        "Flat White": 80,
        "Cold Brew": 85,
    },
    "Non-Coffee": {
        "Matcha Latte": 80,
        "Thai Tea Latte": 70,
        "Chocolate": 75,
        "Strawberry Smoothie": 90,
        "Mango Smoothie": 90,
        "Fresh Orange Juice": 80,
    },
    "Food": {
        "Avocado Toast": 150,
        "Eggs Benedict": 180,
        "Croissant Sandwich": 130,
        "Club Sandwich": 160,
        "Caesar Salad": 140,
        "Overnight Oats": 110,
    },
    "Pastries & Desserts": {
        "Butter Croissant": 65,
        "Blueberry Muffin": 70,
        "Banana Bread": 65,
        "Cheesecake Slice": 120,
        "Chocolate Brownie": 90,
    },
    "Add-ons": {
        "Extra Shot": 20,
        "Oat Milk": 20,
        "Almond Milk": 20,
        "Vanilla Syrup": 15,
        "Caramel Syrup": 15,
        "Whipped Cream": 15,
    },
}

# Chinese display names for Flex Message UI (English keys stay as internal identifiers)
MENU_ZH = {
    # ── Categories ──────────────────────────────────────────────────────────
    "Coffee & Espresso":   "咖啡 & 濃縮",
    "Non-Coffee":          "非咖啡飲品",
    "Food":                "餐點",
    "Pastries & Desserts": "麵包 & 甜點",
    "Add-ons":             "加點選項",
    # ── Coffee ──────────────────────────────────────────────────────────────
    "Espresso":            "義式濃縮",
    "Americano":           "美式咖啡",
    "Latte":               "拿鐵",
    "Cappuccino":          "卡布奇諾",
    "Mocha":               "摩卡",
    "Flat White":          "馥列白",
    "Cold Brew":           "冷萃咖啡",
    # ── Non-Coffee ──────────────────────────────────────────────────────────
    "Matcha Latte":        "抹茶拿鐵",
    "Thai Tea Latte":      "泰奶拿鐵",
    "Chocolate":           "巧克力飲",
    "Strawberry Smoothie": "草莓思慕昔",
    "Mango Smoothie":      "芒果思慕昔",
    "Fresh Orange Juice":  "新鮮柳橙汁",
    # ── Food ────────────────────────────────────────────────────────────────
    "Avocado Toast":       "酪梨吐司",
    "Eggs Benedict":       "班尼迪克蛋",
    "Croissant Sandwich":  "可頌三明治",
    "Club Sandwich":       "總匯三明治",
    "Caesar Salad":        "凱薩沙拉",
    "Overnight Oats":      "隔夜燕麥",
    # ── Pastries ────────────────────────────────────────────────────────────
    "Butter Croissant":    "奶油可頌",
    "Blueberry Muffin":    "藍莓馬芬",
    "Banana Bread":        "香蕉蛋糕",
    "Cheesecake Slice":    "起司蛋糕",
    "Chocolate Brownie":   "巧克力布朗尼",
    # ── Add-ons ─────────────────────────────────────────────────────────────
    "Extra Shot":          "加濃縮",
    "Oat Milk":            "燕麥奶",
    "Almond Milk":         "杏仁奶",
    "Vanilla Syrup":       "香草糖漿",
    "Caramel Syrup":       "焦糖糖漿",
    "Whipped Cream":       "鮮奶油",
}

# Order fulfillment options
FULFILLMENT_OPTIONS = ["dine-in", "takeaway", "delivery"]


def format_menu_for_prompt() -> str:
    """Return a plain-text menu string suitable for inclusion in a system prompt."""
    lines = [
        f"=== {RESTAURANT_INFO['name']} Menu ===",
        f"Hours: {RESTAURANT_INFO['hours']}",
        f"Currency: {RESTAURANT_INFO['currency']}",
        "",
    ]
    for category, items in MENU.items():
        lines.append(f"[ {category} ]")
        for item, price in items.items():
            lines.append(f"  - {item}: {price} {RESTAURANT_INFO['currency']}")
        lines.append("")
    lines.append(f"Fulfillment options: {', '.join(FULFILLMENT_OPTIONS)}")
    return "\n".join(lines)


def calculate_total(order_items: list[dict]) -> int:
    """
    Calculate order total from a list of {"name": str, "qty": int} dicts.
    Looks up prices from MENU. Returns 0 for unknown items.
    """
    total = 0
    all_items = {item: price for cat in MENU.values() for item, price in cat.items()}
    for entry in order_items:
        price = all_items.get(entry.get("name", ""), 0)
        total += price * entry.get("qty", 1)
    return total
