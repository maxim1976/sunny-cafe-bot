"""
seed_item_images.py - Set Unsplash photo URLs for all menu items.

Run once after deploy (or locally with a .env that has DATABASE_URL):
    python seed_item_images.py

Images are matched by name_en. Any item not in the map is skipped.
You can re-run safely — it only updates, never deletes.
"""

from dotenv import load_dotenv
load_dotenv()

import db

db.init_pool()

# Unsplash CDN format: https://images.unsplash.com/photo-{id}?w=400&h=300&fit=crop&q=80
def _u(photo_id: str) -> str:
    return f"https://images.unsplash.com/photo-{photo_id}?w=400&h=300&fit=crop&q=80&auto=format"


ITEM_IMAGES: dict[str, str] = {
    # ── Coffee & Espresso ────────────────────────────────────
    "Espresso":       _u("1510591509098-f4fdc6d0ff04"),
    "Americano":      _u("1495474472287-4d71bcdd2085"),
    "Latte":          _u("1561047029-3000c68339ca"),
    "Cappuccino":     _u("1534778101976-62847782c213"),
    "Mocha":          _u("1578314675249-a6910f80cc4e"),
    "Flat White":     _u("1572442388796-11668a67e53d"),
    "Cold Brew":      _u("1461023058943-07fcbe16d735"),

    # ── Non-Coffee ───────────────────────────────────────────
    "Matcha Latte":       _u("1536256263959-770b48d82b0a"),
    "Thai Tea Latte":     _u("1558618666-fcd25c85cd64"),
    "Chocolate":          _u("1542990253-a781e9421a25"),
    "Strawberry Smoothie":_u("1553530666-ba11a7da3888"),
    "Mango Smoothie":     _u("1546173159-315724a31696"),
    "Fresh Orange Juice": _u("1621506289937-a8e4df240d0b"),

    # ── Food ─────────────────────────────────────────────────
    "Avocado Toast":      _u("1541519227354-08fa5d50c820"),
    "Eggs Benedict":      _u("1608039829572-78524f79c4c7"),
    "Croissant Sandwich": _u("1509722747041-616f39b57569"),
    "Club Sandwich":      _u("1528735602780-2552fd46c7af"),
    "Caesar Salad":       _u("1546793665-c74683f339c1"),
    "Overnight Oats":     _u("1517673400267-0251440c45dc"),

    # ── Pastries & Desserts ───────────────────────────────────
    "Butter Croissant":   _u("1555507036-ab1f4038808a"),
    "Blueberry Muffin":   _u("1607958996333-41aef7caefaa"),
    "Banana Bread":       _u("1481456901329-9eadde7d4103"),
    "Cheesecake Slice":   _u("1565958011703-44f9829ba187"),
    "Chocolate Brownie":  _u("1606313564200-e75d5e30476c"),

    # Add-ons intentionally left without images (shown with category emoji)
}


def main():
    from db import _conn, _cur  # noqa: internal use only in this script

    with _conn() as conn, _cur(conn) as cur:
        cur.execute("SELECT id, name_en FROM items")
        items = cur.fetchall()

    updated = 0
    skipped = 0
    for item in items:
        url = ITEM_IMAGES.get(item["name_en"])
        if url:
            db.update_item(item["id"], image_file=url)
            print(f"  ✓ {item['name_en']}")
            updated += 1
        else:
            skipped += 1

    print(f"\nDone: {updated} updated, {skipped} skipped (no image mapped)")
    print("Tip: verify images look right in the LIFF menu, then update any bad URLs via this script.")


if __name__ == "__main__":
    main()
