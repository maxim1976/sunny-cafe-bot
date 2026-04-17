"""
setup_tab_richmenu.py - One-time script to create the 3-tab bottom bar Rich Menu.

Run locally (NOT on Railway):
    pip install pillow
    python setup_tab_richmenu.py

Requires LINE_CHANNEL_ACCESS_TOKEN (and optionally LIFF_ID) in your .env file.
"""

import json
import os
import urllib.request
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

TOKEN   = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
IMAGE_PATH = "richmenu_tab_image.jpg"
MENU_NAME  = "Sunny Cafe Tab Bar"

# Dimensions — thin bottom bar
W, H = 2500, 270

# Cafe color palette
_AMBER      = (200, 161, 101)   # #C8A165
_COFFEE     = (107,  66,  38)   # #6B4226
_BROWN_MID  = (152, 101,  65)   # midpoint for third panel
_WHITE      = (255, 255, 255)
_CREAM_DARK = (245, 230, 204)   # #F5E6CC


# ── Image generation ──────────────────────────────────────────────────────────

def create_image():
    """Generate the 3-tab background image using Pillow."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("❌  Pillow not installed. Run: pip install pillow")
        raise

    col = W // 3
    img = Image.new("RGB", (W, H), color=_WHITE)
    draw = ImageDraw.Draw(img)

    # Three colored panels
    draw.rectangle([0,         0, col - 2,     H], fill=_AMBER)
    draw.rectangle([col + 1,   0, col * 2 - 2, H], fill=_COFFEE)
    draw.rectangle([col * 2 + 1, 0, W,         H], fill=_BROWN_MID)

    # Thin dividers
    draw.rectangle([col - 2,     0, col,         H], fill=_WHITE)
    draw.rectangle([col * 2 - 2, 0, col * 2,     H], fill=_WHITE)

    # Try Microsoft JhengHei (standard on Windows/Taiwan systems)
    try:
        font_lg = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", 48)
        font_sm = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", 30)
    except OSError:
        print("⚠️  JhengHei font not found — using default font (no Chinese chars)")
        font_lg = ImageFont.load_default()
        font_sm = font_lg

    cy = H // 2
    centers = [col // 2, col + col // 2, col * 2 + col // 2]

    labels = [
        ("📋 查看菜單", "View Menu"),
        ("🤖 AI 顧問",  "AI Consultant"),
        ("📍 地址",     "Location"),
    ]

    for cx, (zh, en) in zip(centers, labels):
        draw.text((cx, cy - 28), zh, fill=_WHITE,      font=font_lg, anchor="mm")
        draw.text((cx, cy + 28), en, fill=_CREAM_DARK, font=font_sm, anchor="mm")

    img.save(IMAGE_PATH, "JPEG", quality=95)
    print(f"✓ Image created: {IMAGE_PATH}")


# ── LINE API helpers ──────────────────────────────────────────────────────────

def _line_get(path: str) -> dict:
    req = urllib.request.Request(
        "https://api.line.me" + path,
        headers={"Authorization": f"Bearer {TOKEN}"},
        method="GET",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _line_post(path: str, payload: dict | None = None, raw: bytes | None = None,
               content_type: str = "application/json") -> dict:
    base = "https://api-data.line.me" if "content" in path else "https://api.line.me"
    url = base + path
    data = raw if raw is not None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": content_type},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        body = resp.read()
        return json.loads(body) if body else {}


# ── Rich menu steps ───────────────────────────────────────────────────────────

def check_existing() -> str | None:
    """Return richMenuId if a menu named MENU_NAME already exists, else None."""
    menus = _line_get("/v2/bot/richmenu/list").get("richmenus", [])
    for m in menus:
        if m.get("name") == MENU_NAME:
            print(f"⚠️  Rich menu '{MENU_NAME}' already exists: {m['richMenuId']}")
            return m["richMenuId"]
    return None


def create_rich_menu() -> str:
    col = W // 3
    payload = {
        "size": {"width": W, "height": H},
        "selected": True,
        "name": MENU_NAME,
        "chatBarText": "☀️ 菜單 Menu",
        "areas": [
            {
                "bounds": {"x": 0, "y": 0, "width": col, "height": H},
                "action": {
                    "type": "postback",
                    "label": "查看菜單 View Menu",
                    "data": "action=view_menu",
                    "displayText": "📋 查看菜單",
                },
            },
            {
                "bounds": {"x": col, "y": 0, "width": col, "height": H},
                "action": {
                    "type": "postback",
                    "label": "AI 顧問 AI Consultant",
                    "data": "action=ai_consultant",
                    "displayText": "🤖 AI 顧問",
                },
            },
            {
                "bounds": {"x": col * 2, "y": 0, "width": col, "height": H},
                "action": {
                    "type": "postback",
                    "label": "地址 Location",
                    "data": "action=location",
                    "displayText": "📍 地址",
                },
            },
        ],
    }
    result = _line_post("/v2/bot/richmenu", payload=payload)
    menu_id = result["richMenuId"]
    print(f"✓ Rich menu created: {menu_id}")
    return menu_id


def upload_image(menu_id: str):
    with open(IMAGE_PATH, "rb") as f:
        image_data = f.read()
    _line_post(
        f"/v2/bot/richmenu/{menu_id}/content",
        raw=image_data,
        content_type="image/jpeg",
    )
    print("✓ Image uploaded to LINE")


def set_default(menu_id: str):
    _line_post(f"/v2/bot/user/all/richmenu/{menu_id}", payload={})
    print("✓ Set as default rich menu for all users")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  Sunny Cafe — 3-Tab Rich Menu Setup")
    print("=" * 50)

    existing_id = check_existing()
    if existing_id:
        ans = input("Set it as default anyway? [y/N] ").strip().lower()
        if ans == "y":
            set_default(existing_id)
        print("Done — no changes made to the menu definition.")
    else:
        create_image()
        menu_id = create_rich_menu()
        upload_image(menu_id)
        set_default(menu_id)

        print()
        print("✅  3-tab rich menu is now live for all users!")
        print(f"   Rich Menu ID: {menu_id}")
        print()
        print("   Left   📋 查看菜單 / View Menu    → postback action=view_menu")
        print("   Center 🤖 AI 顧問 / AI Consultant → postback action=ai_consultant")
        print("   Right  📍 地址 / Location          → postback action=location")
