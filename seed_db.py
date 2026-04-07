"""
seed_db.py - Populate the database with initial menu data and store info.
Run once after provisioning a fresh PostgreSQL database.

Usage:
    python seed_db.py
"""

import os
from dotenv import load_dotenv
load_dotenv()

import db

CATEGORIES = [
    {"name_en": "Coffee & Espresso", "name_zh": "咖啡 & 濃縮", "emoji": "☕", "image_file": "coffee.jpg",     "sort_order": 1},
    {"name_en": "Non-Coffee",         "name_zh": "非咖啡飲品",   "emoji": "🍵", "image_file": "non-coffee.jpg", "sort_order": 2},
    {"name_en": "Food",               "name_zh": "餐點",         "emoji": "🍽️", "image_file": "food.jpg",       "sort_order": 3},
    {"name_en": "Pastries & Desserts","name_zh": "麵包 & 甜點",   "emoji": "🥐", "image_file": "pastries.jpg",   "sort_order": 4},
    {"name_en": "Add-ons",            "name_zh": "加點選項",      "emoji": "✨", "image_file": "addons.jpg",     "sort_order": 5},
]

ITEMS = {
    "Coffee & Espresso": [
        ("Espresso",   "義式濃縮", 55),
        ("Americano",  "美式咖啡", 60),
        ("Latte",      "拿鐵",     75),
        ("Cappuccino", "卡布奇諾", 75),
        ("Mocha",      "摩卡",     80),
        ("Flat White", "馥列白",   80),
        ("Cold Brew",  "冷萃咖啡", 85),
    ],
    "Non-Coffee": [
        ("Matcha Latte",        "抹茶拿鐵",   80),
        ("Thai Tea Latte",      "泰奶拿鐵",   70),
        ("Chocolate",           "巧克力飲",   75),
        ("Strawberry Smoothie", "草莓思慕昔", 90),
        ("Mango Smoothie",      "芒果思慕昔", 90),
        ("Fresh Orange Juice",  "新鮮柳橙汁", 80),
    ],
    "Food": [
        ("Avocado Toast",      "酪梨吐司",   150),
        ("Eggs Benedict",      "班尼迪克蛋", 180),
        ("Croissant Sandwich", "可頌三明治", 130),
        ("Club Sandwich",      "總匯三明治", 160),
        ("Caesar Salad",       "凱薩沙拉",   140),
        ("Overnight Oats",     "隔夜燕麥",   110),
    ],
    "Pastries & Desserts": [
        ("Butter Croissant",   "奶油可頌",     65),
        ("Blueberry Muffin",   "藍莓馬芬",     70),
        ("Banana Bread",       "香蕉蛋糕",     65),
        ("Cheesecake Slice",   "起司蛋糕",     120),
        ("Chocolate Brownie",  "巧克力布朗尼", 90),
    ],
    "Add-ons": [
        ("Extra Shot",    "加濃縮",   20),
        ("Oat Milk",      "燕麥奶",   20),
        ("Almond Milk",   "杏仁奶",   20),
        ("Vanilla Syrup", "香草糖漿", 15),
        ("Caramel Syrup", "焦糖糖漿", 15),
        ("Whipped Cream", "鮮奶油",   15),
    ],
}

STORE_INFO = {
    "name":     "Sunny Cafe",
    "address":  "花蓮縣花蓮市林森路 252 號",
    "phone":    "03-888-8888",
    "hours":    "每日 08:00 - 20:00 / Daily 08:00 - 20:00",
    "currency": "TWD",
    "wifi":     "",
}


def seed():
    db.init_pool()
    db.init_schema()

    print("Seeding store info...")
    db.set_store_info_bulk(STORE_INFO)

    print("Seeding categories and items...")
    for cat_data in CATEGORIES:
        cat = db.create_category(
            name_en=cat_data["name_en"],
            name_zh=cat_data["name_zh"],
            emoji=cat_data["emoji"],
            image_file=cat_data["image_file"],
            sort_order=cat_data["sort_order"],
        )
        print(f"  Category: {cat['name_en']} (id={cat['id']})")
        for sort_i, (name_en, name_zh, price) in enumerate(ITEMS[cat_data["name_en"]]):
            db.create_item(
                category_id=cat["id"],
                name_en=name_en,
                name_zh=name_zh,
                price=price,
                sort_order=sort_i,
            )
            print(f"    Item: {name_en} NT${price}")

    print("\n✅ Database seeded successfully!")


if __name__ == "__main__":
    seed()
