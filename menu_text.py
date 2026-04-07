"""
menu_text.py - Builds a plain-text menu string from the database for Claude's system prompt.
"""

import db


def build_menu_text() -> str:
    categories = db.get_categories(available_only=True)
    lines = ["=== Menu ==="]
    for cat in categories:
        lines.append(f"\n[ {cat['name_zh']} / {cat['name_en']} ]")
        items = db.get_items(cat["id"], available_only=True)
        for item in items:
            lines.append(f"  - {item['name_zh']} ({item['name_en']}): NT${item['price']}")
    return "\n".join(lines)
