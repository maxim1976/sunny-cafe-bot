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
