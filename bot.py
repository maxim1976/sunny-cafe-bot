"""
bot.py - Sales AI assistant for 花蓮Vibe數位工作室.

Enabled when CLAUDE_ENABLED=true.
Acts as a bilingual sales agent: explains the product, collects client intake,
and notifies the owner when a prospect is ready to proceed.
"""

import logging
import os
import json
import queue
import threading
import urllib.error
import urllib.request
from datetime import datetime

logger = logging.getLogger(__name__)

CLAUDE_ENABLED = os.getenv("CLAUDE_ENABLED", "false").lower() == "true"
MODEL = "claude-sonnet-4-6"

# Owner gets a LINE push when a prospect is ready to proceed.
# Set OWNER_LINE_USER_ID in Railway env vars to your personal LINE user ID.
OWNER_LINE_USER_ID = os.getenv("OWNER_LINE_USER_ID", "")

# Internal marker the AI includes to signal handoff is needed.
_HANDOFF_MARKER = "[[NOTIFY_OWNER]]"

# Background queue + worker thread for non-blocking owner notifications.
_notify_queue: queue.Queue = queue.Queue()


def _push_messages(token: str, messages: list[dict]) -> None:
    """Send a single LINE push call. Raises on HTTP error with full details."""
    payload = json.dumps({
        "to": OWNER_LINE_USER_ID,
        "messages": messages,
    }).encode()
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/push",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        logger.error("LINE push failed: HTTP %s — %s", exc.code, body)
        raise
    except Exception as exc:
        logger.error("LINE push failed: %s", exc)
        raise


def _notify_worker() -> None:
    while True:
        item = _notify_queue.get()
        try:
            token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
            if not token:
                logger.warning("LINE_CHANNEL_ACCESS_TOKEN not set — skipping owner notification")
                continue

            import db
            history = db.get_full_history(item["user_id"])

            # Push 1: summary header (its own call so thread gets all 5 slots)
            header = (
                f"🔔 新客戶詢問 / New lead!\n\n"
                f"LINE User: {item['user_id']}\n\n"
                f"📋 {item['summary']}\n\n"
                f"請盡快聯繫他們 😊"
            )
            _push_messages(token, [{"type": "text", "text": header}])
            total_sent = 1

            # Push 2+: conversation thread, up to 5 messages per call
            if history:
                thread_label = "── 完整對話 / Full conversation ──\n\n"
                cont_label = "(續 {n}) "
                conversation = _format_conversation(history)
                chunks = _chunk_text(conversation, prefix=thread_label)
                batch: list[dict] = []
                for i, chunk in enumerate(chunks):
                    prefix = thread_label if i == 0 else cont_label.format(n=i + 1)
                    batch.append({"type": "text", "text": prefix + chunk})
                    if len(batch) == 5:
                        _push_messages(token, batch)
                        total_sent += len(batch)
                        batch = []
                if batch:
                    _push_messages(token, batch)
                    total_sent += len(batch)

            logger.info("Owner notified about lead: %s (%d messages sent)", item["user_id"], total_sent)
        except Exception as exc:
            logger.error("Failed to notify owner: %s", exc)
        finally:
            _notify_queue.task_done()


threading.Thread(target=_notify_worker, daemon=True, name="notify-worker").start()

SALES_PROMPT = """You are the sales assistant for 花蓮Vibe數位工作室 (Hualien Vibe Digital Studio).
We build custom LINE ordering bots for cafés, restaurants, drink shops, and food businesses in Taiwan.
You speak fluently in Traditional Chinese (繁體中文) and English — respond in whatever language the prospect uses.

Today is {date}.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
ABOUT OUR PRODUCT
━━━━━━━━━━━━━━━━━━━━━━━━━━━
We build a complete LINE ordering system for food & beverage businesses:

• Customers add the business as a LINE friend → tap the rich menu → browse a beautiful LIFF mini-app
• Visual menu: category tabs, item cards with photos, prices, add-to-cart
• Cart & checkout: name, phone, fulfillment (dine-in / takeaway / delivery), address, pickup time
• Orders saved to PostgreSQL database — owner views & manages via admin web panel
• Optional: orders auto-print to Epson kitchen printer via TCP/IP
• Optional: Claude AI FAQ — answers customer questions about menu, hours, location
• Optional: LINE Pay integration for cashless payment
• Bilingual: Chinese + English, auto-detected per customer
• Admin panel: manage menu, categories, prices, discounts, announcements — no coding needed

LIVE DEMO: This bot runs on top of the actual demo café system.
Tell the prospect: "Type 菜單 (or 'menu') to open the live ordering demo right now —
that's exactly what their customers will see and use."

━━━━━━━━━━━━━━━━━━━━━━━━━━━
TECHNOLOGY (explain simply — no jargon)
━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Hosted on Railway — a cloud platform. The client never touches a server.
• PostgreSQL database — stores menu, orders, customer info securely.
• LIFF (LINE Front-end Framework) — the ordering app that opens inside LINE.
• Flask web app — the engine powering everything.
• Admin panel — a private web page at /admin, accessible from any browser.
• The client only needs: a LINE Official Account and their menu content.
  We handle all technical setup and deployment.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRICING
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Setup fee (one-time): NT$3,000 – 5,000
  • Depends on number of menu items, complexity, design work needed

Monthly maintenance: NT$800 – 1,500 / month
  • Hosting costs, system monitoring, fast support for issues
  • Menu updates handled by the client via admin panel (no monthly charge for that)

AI FAQ add-on: +NT$300 – 500 / month
  • Claude AI answers customer questions (hours, location, menu, etc.)
  • Requires the client to have their own Anthropic API key (easy to get, pay-per-use)

LINE Pay integration: quoted separately
  • Adds cashless checkout; requires LINE Pay merchant account

LINE Official Account: NT$0 (free tier) or NT$800/month (verified plan)
  • Client applies directly via LINE — we guide them through the process

━━━━━━━━━━━━━━━━━━━━━━━━━━━
SETUP PROCESS
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Timeline: 3–5 business days after receiving all content from the client.

What the client provides:
  1. LINE Official Account credentials (or we guide them to create one)
  2. Menu: categories, item names (Chinese + English), prices
  3. Item photos (product cards) — can be sent via LINE chat
  4. Store photos — exterior and interior
  5. Store info: address, phone, hours, WiFi password (optional)
  6. Brand colors and overall visual style / vibe
  7. Fulfillment types: dine-in / takeaway / delivery?
  8. Kitchen printer? (Epson TCP/IP — yes or no)
  9. LINE Pay? (yes or no)
  10. AI FAQ add-on? (yes or no)

What we deliver:
  • Fully deployed LINE bot on Railway
  • Custom-designed LIFF menu matching their brand
  • Admin panel with login
  • Rich menu button registered on LINE
  • Training session (video call or in person in Hualien)
  • Documentation

━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTAKE — HOW TO COLLECT CLIENT INFO
━━━━━━━━━━━━━━━━━━━━━━━━━━━
When a prospect seems genuinely interested, guide the conversation to collect:

BUSINESS INFO:
  - Business name (Chinese + English if available)
  - City / location
  - Type: café / restaurant / drink shop / food stall / other
  - Current LINE Official Account? (yes / no)

MENU:
  - How many categories? (e.g. Coffee, Cold Drinks, Food, Desserts)
  - List of items per category with prices
  - Do they have product photos ready? (can send via LINE)

STORE IDENTITY & DESIGN:
  - Brand colors (if known — e.g. from logo, signage, packaging)
  - Overall vibe / style (e.g. minimalist, warm, Japanese, industrial, cozy)
  - Store photos (exterior, interior) — ask them to send via LINE chat

OPERATIONS:
  - Fulfillment: dine-in? takeaway? delivery?
  - Opening hours
  - Address
  - Phone number
  - Kitchen printer? (Epson TCP/IP)
  - LINE Pay integration?
  - AI FAQ add-on?

TIMELINE:
  - When do they want to launch?

Collect this naturally over the conversation — don't ask everything at once.
Acknowledge each answer before moving to the next topic.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
HANDOFF RULE
━━━━━━━━━━━━━━━━━━━━━━━━━━━
When a prospect confirms they want to proceed (e.g. says "I want this", "how do I start",
"let's do it", "我要", "我們開始吧", or provides enough intake info), do TWO things:

1. Tell them warmly:
   "Great! I'll notify Maxim now — he'll follow up with you directly on LINE.
    您的需求我都記下來了，Maxim 會盡快聯繫您！"

2. Include the exact text [[NOTIFY_OWNER]] somewhere in your response (it will be hidden from the user).
   Include a brief summary of what was collected, formatted like:
   [[NOTIFY_OWNER]] Business: X | City: X | Type: X | Menu categories: X | LINE Pay: X | AI: X | Notes: X

━━━━━━━━━━━━━━━━━━━━━━━━━━━
TONE & RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Warm, professional, helpful — not pushy
- If they ask a technical question, explain it in plain language (no jargon)
- If they ask something you don't know, say "let me have Maxim answer that directly"
- Never make up prices or features not listed above
- Never discuss ordering coffee or food — this is the sales channel
  If they try to order food, say: "This bot is our sales demo 😄
  But you can try the actual ordering experience — type 菜單!"
- If they seem to be testing or browsing with no intent to buy, answer helpfully anyway
- {lang_instruction}
"""

_LANG_INSTRUCTIONS = {
    "en": "Respond in English unless the prospect switches to Chinese.",
    "zh": "預設使用繁體中文回覆。如果對方用英文，就用英文回覆。",
}


def _build_prompt(lang: str = "zh") -> str:
    return SALES_PROMPT.format(
        date=datetime.utcnow().strftime("%A, %B %d, %Y"),
        lang_instruction=_LANG_INSTRUCTIONS.get(lang, _LANG_INSTRUCTIONS["zh"]),
    )


def _format_conversation(history: list[dict]) -> str:
    """Format conversation history as a readable thread."""
    lines = []
    for msg in history:
        if msg["role"] == "user":
            icon, label = "👤", "Prospect"
        else:
            icon, label = "🤖", "Bot"
        content = msg["content"]
        # Truncate very long bot replies to keep the thread scannable
        if msg["role"] == "assistant" and len(content) > 400:
            content = content[:400] + "…"
        lines.append(f"{icon} {label}: {content}")
    return "\n\n".join(lines)


def _chunk_text(text: str, prefix: str = "", limit: int = 4500) -> list[str]:
    """Split text into chunks that fit within LINE's message size limit.
    Accounts for prefix length so the final message never exceeds limit."""
    effective = limit - len(prefix)
    if len(text) <= effective:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:effective])
        text = text[effective:]
    return chunks


def _notify_owner(prospect_user_id: str, summary: str) -> None:
    """Enqueue a lead notification — actual HTTP call happens in the worker thread."""
    if not OWNER_LINE_USER_ID:
        logger.warning("OWNER_LINE_USER_ID not set — skipping owner notification")
        return
    _notify_queue.put({"user_id": prospect_user_id, "summary": summary})


def get_reply(user_id: str, user_message: str,
              display_name: str | None = None, lang: str = "zh") -> str:
    """
    Get a sales AI reply from Claude. Returns a plain text string.
    Only call this when CLAUDE_ENABLED=true.
    """
    if not CLAUDE_ENABLED:
        if lang == "en":
            return "Hi! We build LINE ordering bots for cafés and restaurants. Type 菜單 to see a live demo, or ask me anything!"
        return "您好！我們為餐飲業打造 LINE 點餐機器人。輸入「菜單」體驗示範，或直接問我任何問題！"

    import anthropic
    import db

    db.save_message(user_id, "user", user_message)
    history = db.get_history(user_id)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=_build_prompt(lang),
            messages=history,
        )
        reply = response.content[0].text
    except Exception as exc:
        logger.error("Claude API error: %s", exc)
        if lang == "en":
            reply = "Sorry, I'm having a hiccup. Please try again or contact us directly on LINE: @839efdgh"
        else:
            reply = "抱歉，目前無法回覆，請稍後再試，或直接加我們 LINE：@839efdgh"
        db.save_message(user_id, "assistant", reply)
        return reply

    # Strip handoff marker from reply before saving or sending.
    # Only trigger on lines where the marker appears at the START (after stripping),
    # and only once on the first valid occurrence.
    notified = False
    if _HANDOFF_MARKER in reply:
        lines = reply.split("\n")
        clean_lines = []
        for line in lines:
            if not notified and line.strip().startswith(_HANDOFF_MARKER):
                summary = line.strip()[len(_HANDOFF_MARKER):].strip()
                if not summary or _HANDOFF_MARKER in summary or "\n" in summary:
                    logger.warning("Handoff marker found but summary is empty or invalid — skipping notification")
                else:
                    notified = True
                    handoff_summary = summary
            else:
                clean_lines.append(line)
        reply = "\n".join(clean_lines).strip()

    # Save reply first so the worker thread sees the complete conversation thread.
    db.save_message(user_id, "assistant", reply)

    if notified:
        _notify_owner(user_id, handoff_summary)

    return reply
