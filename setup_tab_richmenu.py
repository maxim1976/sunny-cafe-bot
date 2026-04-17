"""
setup_tab_richmenu.py - One-time script to create the 2-tab bottom bar Rich Menu.

Run locally (NOT on Railway):
    pip install pillow
    python setup_tab_richmenu.py

Requires LINE_CHANNEL_ACCESS_TOKEN in your .env file.
"""

import json
import os
import urllib.request
from dotenv import load_dotenv

load_dotenv()

TOKEN      = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
IMAGE_PATH = "richmenu_tab_image.jpg"
MENU_NAME  = "Sunny Cafe Tab Bar"

# Dimensions — thin bottom bar
W, H = 2500, 810

_COFFEE     = (107,  66,  38)   # #6B4226
_BROWN_MID  = (152, 101,  65)
_WHITE      = (255, 255, 255)
_CREAM_DARK = (245, 230, 204)


# ── Image generation ──────────────────────────────────────────────────────────

def create_image():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("❌  Pillow not installed. Run: pip install pillow")
        raise

    col = W // 2
    img = Image.new("RGB", (W, H), color=_WHITE)
    draw = ImageDraw.Draw(img)

    # Two colored panels
    draw.rectangle([0,       0, col - 2, H], fill=_COFFEE)
    draw.rectangle([col + 2, 0, W,      H], fill=_BROWN_MID)
    # Divider
    draw.rectangle([col - 2, 0, col + 2, H], fill=_WHITE)

    try:
        font_lg = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", 120)
        font_sm = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", 72)
    except OSError:
        print("⚠️  JhengHei font not found — using default font")
        font_lg = ImageFont.load_default()
        font_sm = font_lg

    cy = H // 2
    labels = [
        ("AI 顧問", "AI Consultant"),
        ("地址",    "Location"),
    ]
    centers = [col // 2, col + col // 2]

    for cx, (zh, en) in zip(centers, labels):
        draw.text((cx, cy - 70), zh, fill=_WHITE,      font=font_lg, anchor="mm")
        draw.text((cx, cy + 70), en, fill=_CREAM_DARK, font=font_sm, anchor="mm")

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


def _line_delete(path: str):
    req = urllib.request.Request(
        "https://api.line.me" + path,
        headers={"Authorization": f"Bearer {TOKEN}"},
        method="DELETE",
    )
    with urllib.request.urlopen(req) as resp:
        resp.read()


# ── Rich menu steps ───────────────────────────────────────────────────────────

def delete_existing():
    """Delete any rich menu named MENU_NAME so we can recreate it cleanly."""
    menus = _line_get("/v2/bot/richmenu/list").get("richmenus", [])
    for m in menus:
        if m.get("name") == MENU_NAME:
            _line_delete(f"/v2/bot/richmenu/{m['richMenuId']}")
            print(f"✓ Deleted old menu: {m['richMenuId']}")


def create_rich_menu() -> str:
    col = W // 2
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
                    "label": "AI 顧問 AI Consultant",
                    "data": "action=ai_consultant",
                    "displayText": "AI 顧問",
                },
            },
            {
                "bounds": {"x": col, "y": 0, "width": col, "height": H},
                "action": {
                    "type": "postback",
                    "label": "地址 Location",
                    "data": "action=location",
                    "displayText": "地址",
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
    print("  Sunny Cafe — 2-Tab Rich Menu Setup")
    print("=" * 50)

    delete_existing()
    create_image()
    menu_id = create_rich_menu()
    upload_image(menu_id)
    set_default(menu_id)

    print()
    print("✅  2-tab rich menu is now live for all users!")
    print(f"   Rich Menu ID: {menu_id}")
    print()
    print("   Left  AI 顧問 / AI Consultant → postback action=ai_consultant")
    print("   Right 地址 / Location          → postback action=location")
