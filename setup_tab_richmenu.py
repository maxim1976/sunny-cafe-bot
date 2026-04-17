"""
setup_tab_richmenu.py - Creates the rich menu: store card (top) + 2 tabs.

Layout:
  ┌──────────────────────────────────┐
  │  [cafe photo]                    │  → opens LIFF (Open Menu)
  │  Sunny Cafe                      │
  │  address / phone / hours         │
  │  [  瀏覽菜單 / Open Menu  ]      │
  ├──────────────────┬───────────────┤
  │   AI 顧問        │    地址       │
  └──────────────────┴───────────────┘

Run locally:
    pip install pillow
    python setup_tab_richmenu.py

Requires LINE_CHANNEL_ACCESS_TOKEN and LIFF_ID in .env
"""

import json
import os
import urllib.request
from dotenv import load_dotenv

load_dotenv()

import db
db.init_pool()

TOKEN      = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LIFF_ID    = os.getenv("LIFF_ID", "")
IMAGE_PATH = "richmenu_tab_image.jpg"
MENU_NAME  = "Sunny Cafe Tab Bar"

# ── Dimensions (LINE max = 2500 x 1686) ──────────────────────────────────────
W        = 2500
H_PHOTO  = 780    # hero image
H_INFO   = 460    # white store info area
H_BTN    = 160    # open-menu button strip
H_TOP    = H_PHOTO + H_INFO + H_BTN   # 1400 — full card tap zone
H_TABS   = 286                         # two bottom tabs
H        = H_TOP + H_TABS              # 1686

# ── Palette ───────────────────────────────────────────────────────────────────
_COFFEE     = (107,  66,  38)
_BROWN_MID  = (152, 101,  65)
_WHITE      = (255, 255, 255)
_CREAM_DARK = (245, 230, 204)
_TEXT_DARK  = (80,  50,  25)
_TEXT_GRAY  = (100, 100, 100)


# ── Image generation ──────────────────────────────────────────────────────────

def create_image():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("❌  Pillow not installed. Run: pip install pillow")
        raise

    # Fetch store info from DB (falls back to defaults on error)
    try:
        info = db.get_store_info()
    except Exception as e:
        print(f"⚠️  Could not fetch store info ({e}), using defaults")
        info = {}
    name    = info.get("name",    "Sunny Cafe")
    address = info.get("address", "")
    phone   = info.get("phone",   "")
    hours   = info.get("hours",   "")

    img  = Image.new("RGB", (W, H), color=_WHITE)
    draw = ImageDraw.Draw(img)

    # ── Hero photo ────────────────────────────────────────────────────────────
    photo_path = "images/welcome.jpg"
    if os.path.exists(photo_path):
        from PIL import Image as PILImage
        photo = PILImage.open(photo_path).convert("RGB")
        # Scale to fill W x H_PHOTO (cover crop)
        r = max(W / photo.width, H_PHOTO / photo.height)
        new_w = int(photo.width  * r)
        new_h = int(photo.height * r)
        photo = photo.resize((new_w, new_h), PILImage.LANCZOS)
        x_off = (new_w - W)      // 2
        y_off = (new_h - H_PHOTO) // 2
        photo = photo.crop((x_off, y_off, x_off + W, y_off + H_PHOTO))
        img.paste(photo, (0, 0))
        draw = ImageDraw.Draw(img)

        # Subtle dark gradient at bottom of photo (readability)
        for i in range(140):
            alpha = int(160 * (i / 140))
            draw.line([(0, H_PHOTO - 140 + i), (W, H_PHOTO - 140 + i)],
                      fill=(40, 20, 5), width=1)
            # Actually just draw semi-transparent won't work in RGB mode.
            # Instead paint progressively darker lines
    else:
        draw.rectangle([0, 0, W, H_PHOTO], fill=_BROWN_MID)

    # ── Store info area ───────────────────────────────────────────────────────
    draw.rectangle([0, H_PHOTO, W, H_PHOTO + H_INFO], fill=_WHITE)

    # Thin amber accent line at top of info area
    draw.rectangle([0, H_PHOTO, W, H_PHOTO + 8], fill=_BROWN_MID)

    # ── Open Menu button strip ────────────────────────────────────────────────
    draw.rectangle([0, H_PHOTO + H_INFO, W, H_TOP], fill=_COFFEE)

    # ── Tab separator + panels ────────────────────────────────────────────────
    draw.rectangle([0, H_TOP, W, H_TOP + 6], fill=_WHITE)
    draw.rectangle([0,       H_TOP + 6, W // 2 - 3, H], fill=_COFFEE)
    draw.rectangle([W // 2 + 3, H_TOP + 6, W,       H], fill=_BROWN_MID)
    draw.rectangle([W // 2 - 3, H_TOP + 6, W // 2 + 3, H], fill=_WHITE)

    # ── Fonts ─────────────────────────────────────────────────────────────────
    def load_font(name_bold, name_reg, size):
        for path in [f"C:/Windows/Fonts/{name_bold}", f"C:/Windows/Fonts/{name_reg}"]:
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
        return ImageFont.load_default()

    f_name    = load_font("msjhbd.ttc", "msjh.ttc", 96)
    f_info    = load_font("msjh.ttc",   "msjh.ttc", 64)
    f_btn     = load_font("msjhbd.ttc", "msjh.ttc", 76)
    f_tab_lg  = load_font("msjhbd.ttc", "msjh.ttc", 88)
    f_tab_sm  = load_font("msjh.ttc",   "msjh.ttc", 54)

    # ── Cafe name ─────────────────────────────────────────────────────────────
    pad = 80
    y = H_PHOTO + 40
    draw.text((pad, y), name, fill=_TEXT_DARK, font=f_name)
    y += 115

    # ── Info rows ─────────────────────────────────────────────────────────────
    row_gap = 88
    if address:
        draw.text((pad, y), address, fill=_TEXT_GRAY, font=f_info)
        y += row_gap
    if phone:
        draw.text((pad, y), phone,   fill=_TEXT_GRAY, font=f_info)
        y += row_gap
    if hours:
        draw.text((pad, y), hours,   fill=_TEXT_GRAY, font=f_info)

    # ── Button label ──────────────────────────────────────────────────────────
    btn_cy = H_PHOTO + H_INFO + H_BTN // 2
    draw.text((W // 2, btn_cy), "瀏覽菜單 / Open Menu",
              fill=_WHITE, font=f_btn, anchor="mm")

    # ── Tab labels ────────────────────────────────────────────────────────────
    tab_cy = H_TOP + 6 + (H_TABS - 6) // 2
    draw.text((W // 4,     tab_cy - 34), "AI 顧問",       fill=_WHITE,      font=f_tab_lg, anchor="mm")
    draw.text((W // 4,     tab_cy + 56), "AI Consultant", fill=_CREAM_DARK, font=f_tab_sm, anchor="mm")
    draw.text((3 * W // 4, tab_cy - 34), "地址",          fill=_WHITE,      font=f_tab_lg, anchor="mm")
    draw.text((3 * W // 4, tab_cy + 56), "Location",      fill=_CREAM_DARK, font=f_tab_sm, anchor="mm")

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
    data = raw if raw is not None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        base + path, data=data,
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


def delete_existing():
    menus = _line_get("/v2/bot/richmenu/list").get("richmenus", [])
    for m in menus:
        if m.get("name") == MENU_NAME:
            _line_delete(f"/v2/bot/richmenu/{m['richMenuId']}")
            print(f"✓ Deleted old menu: {m['richMenuId']}")


def create_rich_menu() -> str:
    liff_url = f"https://liff.line.me/{LIFF_ID}" if LIFF_ID else "https://line.me"
    payload = {
        "size": {"width": W, "height": H},
        "selected": True,
        "name": MENU_NAME,
        "chatBarText": "☀️ 菜單 Menu",
        "areas": [
            {
                "bounds": {"x": 0, "y": 0, "width": W, "height": H_TOP},
                "action": {"type": "uri", "label": "Open Menu", "uri": liff_url},
            },
            {
                "bounds": {"x": 0, "y": H_TOP, "width": W // 2, "height": H_TABS},
                "action": {"type": "message", "label": "AI 顧問", "text": "AI顧問"},
            },
            {
                "bounds": {"x": W // 2, "y": H_TOP, "width": W // 2, "height": H_TABS},
                "action": {"type": "message", "label": "地址", "text": "地址"},
            },
        ],
    }
    result = _line_post("/v2/bot/richmenu", payload=payload)
    menu_id = result["richMenuId"]
    print(f"✓ Rich menu created: {menu_id}")
    return menu_id


def upload_image(menu_id: str):
    with open(IMAGE_PATH, "rb") as f:
        data = f.read()
    _line_post(f"/v2/bot/richmenu/{menu_id}/content", raw=data, content_type="image/jpeg")
    print("✓ Image uploaded to LINE")


def set_default(menu_id: str):
    _line_post(f"/v2/bot/user/all/richmenu/{menu_id}", payload={})
    print("✓ Set as default rich menu for all users")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  Sunny Cafe — Store Card Rich Menu Setup")
    print("=" * 50)

    delete_existing()
    create_image()
    menu_id = create_rich_menu()
    upload_image(menu_id)
    set_default(menu_id)

    print()
    print("✅  Rich menu is now live!")
    print(f"   Rich Menu ID: {menu_id}")
    print()
    print("   Top card  → opens LIFF menu")
    print("   AI 顧問   → sends 'AI顧問' message")
    print("   地址      → sends '地址' message")
