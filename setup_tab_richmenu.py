"""
setup_tab_richmenu.py - Rich menu mirroring the flex card design.

Layout (mirrors the old open-menu bubble):
  ┌─────────────────────────────────┐  580px  — hero photo
  ├─────────────────────────────────┤
  │  ☀  Sunny Cafe   (amber+bold)   │  620px  — white info area
  │  ◉  address                     │
  │  ◎  phone                       │
  │  ○  hours                       │
  ├─────────────────┬───────────────┤  486px  — tall tabs
  │   AI 顧問       │    地址       │
  └─────────────────┴───────────────┘
  Total: 1686px (LINE max)
"""

import json
import math
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

# ── Dimensions ────────────────────────────────────────────────────────────────
W        = 2500
H_PHOTO  = 580    # hero photo  (~35% of card)
H_WHITE  = 620    # white info  (~38% of card)
H_TOP    = H_PHOTO + H_WHITE   # 1200  — full tap zone → LIFF
H_TABS   = 486                  # tall tabs (~29% of total)
H        = H_TOP + H_TABS       # 1686

# ── Palette ───────────────────────────────────────────────────────────────────
_COFFEE    = (107,  66,  38)
_BROWN_MID = (152, 101,  65)
_AMBER     = (200, 161, 101)
_AMBER_DK  = (170, 125,  70)
_WHITE     = (255, 255, 255)
_CREAM     = (232, 213, 183)
_CREAM_DK  = (245, 230, 204)
_TEXT_DARK = ( 60,  35,  12)   # name color
_TEXT_GRAY = (100,  70,  40)   # info row color


# ── Custom icon drawers ───────────────────────────────────────────────────────

def icon_sun(draw, cx, cy, r):
    """Amber sun — filled circle + 8 short rays."""
    for i in range(8):
        a  = i * math.pi / 4
        x1 = cx + int((r + 6)  * math.cos(a))
        y1 = cy + int((r + 6)  * math.sin(a))
        x2 = cx + int((r + 26) * math.cos(a))
        y2 = cy + int((r + 26) * math.sin(a))
        draw.line([(x1, y1), (x2, y2)], fill=_AMBER, width=8)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_AMBER)


def icon_pin(draw, cx, cy, r):
    """Red location pin — circle + downward teardrop."""
    draw.ellipse([cx - r, cy - r, cx + int(r * 1.05), cy + int(r * 1.05)],
                 fill=(210, 60, 50))
    draw.polygon([(cx - int(r * 0.65), cy + int(r * 0.5)),
                  (cx + int(r * 0.65), cy + int(r * 0.5)),
                  (cx, cy + int(r * 2.1))],
                 fill=(210, 60, 50))
    ir = int(r * 0.38)
    draw.ellipse([cx - ir, cy - ir, cx + ir, cy + ir], fill=_WHITE)


def icon_phone(draw, cx, cy, r):
    """Coffee-brown handset icon."""
    w, h = int(r * 1.1), int(r * 2.0)
    draw.rounded_rectangle(
        [cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2],
        radius=int(w * 0.35), fill=_COFFEE,
    )
    ew = int(w * 0.45)
    eh = int(h * 0.08)
    for oy in [-h // 2 + int(h * 0.14), h // 2 - int(h * 0.22)]:
        draw.rounded_rectangle(
            [cx - ew // 2, cy + oy, cx + ew // 2, cy + oy + eh],
            radius=3, fill=_CREAM,
        )


def icon_clock(draw, cx, cy, r):
    """Amber clock — circle outline + hour + minute hands."""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                 outline=_AMBER, width=7)
    draw.ellipse([cx - r + 7, cy - r + 7, cx + r - 7, cy + r - 7],
                 outline=_AMBER_DK, width=2)
    draw.line([(cx, cy), (cx, cy - int(r * 0.52))], fill=_AMBER, width=8)
    draw.line([(cx, cy), (cx + int(r * 0.44), cy + int(r * 0.2))],
              fill=_AMBER, width=6)
    draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=_AMBER)


# ── Image generation ──────────────────────────────────────────────────────────

def create_image():
    from PIL import Image, ImageDraw, ImageFont

    try:
        info = db.get_store_info()
    except Exception as e:
        print(f"⚠️  DB ({e}) — using defaults")
        info = {}

    name    = info.get("name",    "Sunny Cafe")
    address = info.get("address", "")
    phone   = info.get("phone",   "")
    hours   = info.get("hours",   "")

    img  = Image.new("RGB", (W, H), color=_WHITE)
    draw = ImageDraw.Draw(img)

    # ── 1. Hero photo ─────────────────────────────────────────────────────────
    photo_path = "images/welcome.jpg"
    if os.path.exists(photo_path):
        photo = Image.open(photo_path).convert("RGB")
        r     = max(W / photo.width, H_PHOTO / photo.height)
        pw    = int(photo.width  * r)
        ph    = int(photo.height * r)
        photo = photo.resize((pw, ph), Image.LANCZOS)
        photo = photo.crop(((pw - W) // 2, (ph - H_PHOTO) // 2,
                             (pw - W) // 2 + W, (ph - H_PHOTO) // 2 + H_PHOTO))
        img.paste(photo, (0, 0))
    else:
        draw.rectangle([0, 0, W, H_PHOTO], fill=_BROWN_MID)

    draw = ImageDraw.Draw(img)

    # Slim bottom fade on photo → bleeds into white
    fade_h = 90
    overlay = Image.new("RGBA", (W, fade_h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for i in range(fade_h):
        a = int(110 * (i / fade_h) ** 2)
        od.line([(0, i), (W, i)], fill=(20, 10, 4, a))
    img_rgba = img.convert("RGBA")
    img_rgba.alpha_composite(overlay, (0, H_PHOTO - fade_h))
    img = img_rgba.convert("RGB")
    draw = ImageDraw.Draw(img)

    # ── 2. White info area ────────────────────────────────────────────────────
    draw.rectangle([0, H_PHOTO, W, H_TOP], fill=_WHITE)

    # Thin amber top-rule
    draw.rectangle([0, H_PHOTO, W, H_PHOTO + 10], fill=_AMBER)

    # ── 3. Tab panels ─────────────────────────────────────────────────────────
    draw.rectangle([0,          H_TOP, W // 2 - 3, H], fill=_COFFEE)
    draw.rectangle([W // 2 + 3, H_TOP, W,          H], fill=_BROWN_MID)
    draw.rectangle([W // 2 - 3, H_TOP, W // 2 + 3, H], fill=_CREAM)
    draw.rectangle([0,          H_TOP, W,           H_TOP + 6], fill=_AMBER)

    # ── 4. Fonts ──────────────────────────────────────────────────────────────
    def ttf(bold, reg, size):
        for p in [f"C:/Windows/Fonts/{bold}", f"C:/Windows/Fonts/{reg}"]:
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                pass
        return ImageFont.load_default()

    f_name   = ttf("msjhbd.ttc", "msjh.ttc", 148)
    f_info   = ttf("msjh.ttc",   "msjh.ttc",  76)
    f_tab_lg = ttf("msjhbd.ttc", "msjh.ttc", 112)
    f_tab_sm = ttf("msjh.ttc",   "msjh.ttc",  64)

    icon_r   = 34
    icon_gap = 32                         # gap between icon and text
    icon_w   = icon_r * 2 + icon_gap      # total horizontal footprint of icon

    # ── Measure widest row to align left edges ───────────────────────────────
    def text_w(text, font):
        bb = draw.textbbox((0, 0), text, font=font)
        return bb[2] - bb[0]

    rows = [("name", name, f_name)]
    if address: rows.append(("pin",   address, f_info))
    if phone:   rows.append(("phone", phone,   f_info))
    if hours:   rows.append(("clock", hours,   f_info))

    max_row_w = max(icon_w + text_w(t, f) for _, t, f in rows)
    block_x   = (W - max_row_w) // 2       # centered block, shared left edge

    # ── Vertical layout in white area ────────────────────────────────────────
    # Total needed: name (≈170) + underline_gap (40) + rows × gap
    n_info_rows = len(rows) - 1
    row_gap     = 118
    block_h     = 170 + 40 + n_info_rows * row_gap
    y0          = H_PHOTO + (H_WHITE - block_h) // 2   # vertically centered

    # ── Store name + sun icon ────────────────────────────────────────────────
    name_y  = y0
    name_cy = name_y + 74
    icon_sun(draw, block_x + icon_r, name_cy, icon_r)
    draw.text((block_x + icon_w, name_y), name,
              fill=_TEXT_DARK, font=f_name)

    # Amber underline under the name
    uy = name_y + 168
    draw.rectangle(
        [block_x + icon_w, uy,
         block_x + icon_w + min(text_w(name, f_name), 640), uy + 12],
        fill=_AMBER,
    )

    # ── Info rows (icons + text, left-aligned to shared block_x) ─────────────
    row_y = y0 + 210

    def info_row(y, icon_fn, text):
        icon_fn(draw, block_x + icon_r, y + 38, icon_r)
        draw.text((block_x + icon_w, y), text, fill=_TEXT_GRAY, font=f_info)

    for kind, text, _ in rows[1:]:
        fn = {"pin": icon_pin, "phone": icon_phone, "clock": icon_clock}[kind]
        info_row(row_y, fn, text)
        row_y += row_gap

    # ── 7. Tab labels ─────────────────────────────────────────────────────────
    tab_cy = H_TOP + 6 + (H_TABS - 6) // 2
    draw.text((W // 4,     tab_cy - 46), "AI 顧問",       fill=_WHITE,   font=f_tab_lg, anchor="mm")
    draw.text((W // 4,     tab_cy + 76), "AI Consultant", fill=_CREAM_DK, font=f_tab_sm, anchor="mm")
    draw.text((3 * W // 4, tab_cy - 46), "地址",          fill=_WHITE,   font=f_tab_lg, anchor="mm")
    draw.text((3 * W // 4, tab_cy + 76), "Location",      fill=_CREAM_DK, font=f_tab_sm, anchor="mm")

    img.save(IMAGE_PATH, "JPEG", quality=96)
    print(f"✓ Image saved: {IMAGE_PATH}")


# ── LINE API helpers ──────────────────────────────────────────────────────────

def _req(method, path, payload=None, raw=None, ct="application/json"):
    base = "https://api-data.line.me" if "content" in path else "https://api.line.me"
    data = raw if raw else (json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None)
    req  = urllib.request.Request(
        base + path, data=data,
        headers={"Authorization": f"Bearer {TOKEN}",
                 **({"Content-Type": ct} if data else {})},
        method=method,
    )
    with urllib.request.urlopen(req) as r:
        body = r.read()
        return json.loads(body) if body else {}

def delete_existing():
    for m in _req("GET", "/v2/bot/richmenu/list").get("richmenus", []):
        if m.get("name") == MENU_NAME:
            _req("DELETE", f"/v2/bot/richmenu/{m['richMenuId']}")
            print(f"✓ Deleted old menu: {m['richMenuId']}")

def create_rich_menu():
    liff = f"https://liff.line.me/{LIFF_ID}" if LIFF_ID else "https://line.me"
    mid  = _req("POST", "/v2/bot/richmenu", payload={
        "size": {"width": W, "height": H},
        "selected": True,
        "name": MENU_NAME,
        "chatBarText": "☀️ 菜單 Menu",
        "areas": [
            {"bounds": {"x": 0, "y": 0, "width": W, "height": H_TOP},
             "action": {"type": "uri", "label": "Open Menu", "uri": liff}},
            {"bounds": {"x": 0, "y": H_TOP, "width": W // 2, "height": H_TABS},
             "action": {"type": "message", "label": "AI 顧問", "text": "AI顧問"}},
            {"bounds": {"x": W // 2, "y": H_TOP, "width": W // 2, "height": H_TABS},
             "action": {"type": "message", "label": "地址", "text": "地址"}},
        ],
    })["richMenuId"]
    print(f"✓ Rich menu created: {mid}")
    return mid

def upload_image(mid):
    with open(IMAGE_PATH, "rb") as f:
        _req("POST", f"/v2/bot/richmenu/{mid}/content",
             raw=f.read(), ct="image/jpeg")
    print("✓ Image uploaded")

def set_default(mid):
    _req("POST", f"/v2/bot/user/all/richmenu/{mid}", payload={})
    print("✓ Set as default")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  Sunny Cafe — Store Card Rich Menu")
    print("=" * 50)
    delete_existing()
    create_image()
    mid = create_rich_menu()
    upload_image(mid)
    set_default(mid)
    print(f"\n✅  Live!  ID: {mid}")
    print("   Photo card  → opens LIFF")
    print("   AI 顧問     → 'AI顧問' message")
    print("   地址        → '地址' message")
