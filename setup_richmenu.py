"""
setup_richmenu.py - One-time script to create and activate the LINE Rich Menu.

Run locally (NOT on Railway):
    pip install pillow
    python setup_richmenu.py

Requires LINE_CHANNEL_ACCESS_TOKEN in your .env file.
"""

import json
import os
import urllib.request
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
IMAGE_PATH = "richmenu_image.jpg"

# Rich menu dimensions (LINE standard)
W, H = 1200, 405

# Same palette as the bot UI
_AMBER      = (200, 161, 101)   # #C8A165
_COFFEE     = (107,  66,  38)   # #6B4226
_WHITE      = (255, 255, 255)
_CREAM_DARK = (245, 230, 204)   # #F5E6CC
_CREAM_SOFT = (232, 213, 183)   # #E8D5B7


# ── Image generation ──────────────────────────────────────────────────────────

def create_image():
    """Generate the rich menu background image using Pillow."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("❌  Pillow not installed. Run: pip install pillow")
        raise

    img = Image.new("RGB", (W, H), color=_WHITE)
    draw = ImageDraw.Draw(img)

    # Left half — amber (View Menu)
    draw.rectangle([0, 0, W // 2 - 3, H], fill=_AMBER)
    # Right half — dark coffee (Start Order)
    draw.rectangle([W // 2 + 3, 0, W, H], fill=_COFFEE)
    # Center divider
    draw.rectangle([W // 2 - 3, 0, W // 2 + 3, H], fill=_WHITE)

    # Try Microsoft JhengHei (standard on Windows/Taiwan systems)
    try:
        font_lg = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", 56)
        font_sm = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", 36)
    except OSError:
        print("⚠️  JhengHei font not found — using default font (no Chinese chars)")
        font_lg = ImageFont.load_default()
        font_sm = font_lg

    cx_left  = W // 4
    cx_right = 3 * W // 4
    cy       = H // 2

    # Left button labels
    draw.text((cx_left, cy - 30), "☕ 查看菜單", fill=_WHITE,      font=font_lg, anchor="mm")
    draw.text((cx_left, cy + 40), "View Menu",   fill=_CREAM_DARK, font=font_sm, anchor="mm")

    # Right button labels
    draw.text((cx_right, cy - 30), "💬 開始點餐",  fill=_WHITE,      font=font_lg, anchor="mm")
    draw.text((cx_right, cy + 40), "Start Order", fill=_CREAM_SOFT, font=font_sm, anchor="mm")

    img.save(IMAGE_PATH, "JPEG", quality=95)
    print(f"✓ Image created: {IMAGE_PATH}")


# ── LINE API helpers ───────────────────────────────────────────────────────────

def _line_post(path: str, payload: dict | None = None, raw: bytes | None = None, content_type: str = "application/json") -> dict:
    base = "https://api.line.me" if not path.startswith("/v2/bot/richmenu") or "content" not in path else "https://api-data.line.me"
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


def create_rich_menu() -> str:
    payload = {
        "size": {"width": W, "height": H},
        "selected": True,
        "name": "Sunny Cafe Main Menu",
        "chatBarText": "☀️ 菜單 Menu",
        "areas": [
            {
                "bounds": {"x": 0, "y": 0, "width": W // 2, "height": H},
                "action": {"type": "message", "label": "查看菜單", "text": "menu"},
            },
            {
                "bounds": {"x": W // 2, "y": 0, "width": W // 2, "height": H},
                "action": {"type": "message", "label": "開始點餐", "text": "我想點餐"},
            },
        ],
    }
    result = _line_post("/v2/bot/richmenu", payload=payload)
    rich_menu_id = result["richMenuId"]
    print(f"✓ Rich menu created: {rich_menu_id}")
    return rich_menu_id


def upload_image(rich_menu_id: str):
    with open(IMAGE_PATH, "rb") as f:
        image_data = f.read()
    _line_post(
        f"/v2/bot/richmenu/{rich_menu_id}/content",
        raw=image_data,
        content_type="image/jpeg",
    )
    print("✓ Image uploaded to LINE")


def set_default(rich_menu_id: str):
    _line_post(f"/v2/bot/users/all/richmenu/{rich_menu_id}", payload={})
    print("✓ Set as default rich menu for all users")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  Sunny Cafe — LINE Rich Menu Setup")
    print("=" * 50)

    create_image()
    rich_menu_id = create_rich_menu()
    upload_image(rich_menu_id)
    set_default(rich_menu_id)

    print()
    print("✅  Rich menu is now live for all users!")
    print(f"   Rich Menu ID: {rich_menu_id}")
    print("   (Keep this ID if you need to update or delete it later)")
    print()
    print("   Users will see two buttons at the bottom of the chat:")
    print("   ☕ 查看菜單 / View Menu   →  sends 'menu'")
    print("   💬 開始點餐 / Start Order →  starts ordering with Claude")
