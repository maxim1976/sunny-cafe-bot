"""
printer.py - ESC/POS kitchen ticket printing via TCP (Epson TM-T20 or compatible)
Falls back gracefully if the printer is offline.
"""

import logging
import os
import re
import socket
import textwrap
from datetime import datetime

logger = logging.getLogger(__name__)

PRINTER_IP = os.getenv("PRINTER_IP", "192.168.1.100")
PRINTER_PORT = int(os.getenv("PRINTER_PORT", "9100"))
PRINTER_TIMEOUT = 5  # seconds

# Ticket width in characters (80mm paper = 42 chars; 58mm = 32 chars)
TICKET_WIDTH = 42

# ── ESC/POS byte helpers ──────────────────────────────────────────────────────
ESC = b"\x1b"
GS = b"\x1d"

INIT = ESC + b"@"                      # Initialize printer
ALIGN_LEFT = ESC + b"a\x00"
ALIGN_CENTER = ESC + b"a\x01"
BOLD_ON = ESC + b"E\x01"
BOLD_OFF = ESC + b"E\x00"
DOUBLE_HEIGHT_ON = GS + b"!\x01"
DOUBLE_HEIGHT_OFF = GS + b"!\x00"
CUT_PAPER = GS + b"V\x41\x03"         # Partial cut with feed


def _encode(text: str) -> bytes:
    return text.encode("cp437", errors="replace")


def _line(text: str = "") -> bytes:
    return _encode(text + "\n")


def _divider(char: str = "-") -> bytes:
    return _encode(char * TICKET_WIDTH + "\n")


def _center(text: str) -> bytes:
    return ALIGN_CENTER + _encode(text + "\n") + ALIGN_LEFT


def _bold(text: str) -> bytes:
    return BOLD_ON + _encode(text) + BOLD_OFF


# ── Order number generator ────────────────────────────────────────────────────

_order_counter_file = "order_counter.txt"


def _next_order_number() -> int:
    try:
        with open(_order_counter_file) as f:
            n = int(f.read().strip()) + 1
    except (FileNotFoundError, ValueError):
        n = 1
    with open(_order_counter_file, "w") as f:
        f.write(str(n))
    return n


# ── Ticket builder ────────────────────────────────────────────────────────────

def build_ticket(
    order_number: int,
    customer_name: str,
    items: list[dict],   # [{"name": str, "qty": int, "price": int}, ...]
    total: int,
    fulfillment: str,    # "dine-in" | "takeaway" | "delivery"
    currency: str = "THB",
    note: str = "",
) -> bytes:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    buf = bytearray()
    buf += INIT

    # Header
    buf += ALIGN_CENTER
    buf += DOUBLE_HEIGHT_ON + _encode("SUNNY CAFE\n") + DOUBLE_HEIGHT_OFF
    buf += _line("Kitchen Ticket")
    buf += _divider("=")

    buf += ALIGN_LEFT
    buf += _bold(f"Order #: {order_number:04d}") + _line()
    buf += _line(f"Time    : {now}")
    buf += _line(f"Name    : {customer_name}")
    buf += _line(f"Type    : {fulfillment.upper()}")
    buf += _divider()

    # Items
    buf += BOLD_ON + _line("  ITEM                     QTY  PRICE") + BOLD_OFF
    buf += _divider()

    for item in items:
        name = item.get("name", "")
        qty = item.get("qty", 1)
        price = item.get("price", 0)
        subtotal = qty * price

        # Wrap long item names
        wrapped = textwrap.wrap(name, width=24)
        for i, part in enumerate(wrapped):
            if i == 0:
                buf += _line(f"  {part:<24} {qty:>2}  {subtotal:>5}")
            else:
                buf += _line(f"    {part}")

    buf += _divider()
    buf += BOLD_ON + _encode(f"  {'TOTAL':<27} {total:>5} {currency}\n") + BOLD_OFF
    buf += _divider("=")

    if note:
        buf += _line(f"Note: {note}")
        buf += _divider()

    # Footer
    buf += ALIGN_CENTER
    buf += _line("Thank you for choosing Sunny Cafe!")
    buf += _line("www.sunnycafe.example.com")
    buf += _line("")
    buf += _line("")

    buf += CUT_PAPER

    return bytes(buf)


# ── TCP send ──────────────────────────────────────────────────────────────────

def _send_to_printer(data: bytes) -> bool:
    """
    Open a raw TCP socket to the printer and send data.
    Returns True on success, False on any network error.
    """
    try:
        with socket.create_connection(
            (PRINTER_IP, PRINTER_PORT), timeout=PRINTER_TIMEOUT
        ) as sock:
            sock.sendall(data)
        logger.info("Ticket sent to printer %s:%s", PRINTER_IP, PRINTER_PORT)
        return True
    except OSError as exc:
        logger.error(
            "Printer offline or unreachable (%s:%s): %s",
            PRINTER_IP, PRINTER_PORT, exc,
        )
        return False


# ── Public API ────────────────────────────────────────────────────────────────

def print_order_ticket(
    customer_name: str,
    items: list[dict],
    total: int,
    fulfillment: str,
    currency: str = "THB",
    note: str = "",
) -> dict:
    """
    Print a kitchen ticket for a confirmed order.

    Returns a dict with:
        success      – bool
        order_number – int (even on failure, so it can be shown to the customer)
        message      – human-readable status string
    """
    order_number = _next_order_number()

    ticket = build_ticket(
        order_number=order_number,
        customer_name=customer_name,
        items=items,
        total=total,
        fulfillment=fulfillment,
        currency=currency,
        note=note,
    )

    success = _send_to_printer(ticket)

    return {
        "success": success,
        "order_number": order_number,
        "message": "Ticket printed." if success else "Printer offline – order saved, print manually.",
    }


# ── Order detail parser ───────────────────────────────────────────────────────
# A lightweight extractor that parses the confirmed order summary from Claude's
# last message.  Claude is prompted to include Name, items, and fulfillment in
# its confirmation message, so we parse that text here.

def parse_order_from_text(text: str) -> dict:
    """
    Attempt to extract order details from a confirmation message.
    Returns a dict with keys: customer_name, items, total, fulfillment.
    Falls back to sensible defaults when parsing fails.
    """
    result = {
        "customer_name": "Guest",
        "items": [],
        "total": 0,
        "fulfillment": "takeaway",
    }

    # Customer name: look for patterns like "Name: John" or "for John"
    name_match = re.search(
        r"(?:name[:\s]+|order for\s+)([A-Za-z][A-Za-z\s]{1,30})",
        text,
        re.IGNORECASE,
    )
    if name_match:
        result["customer_name"] = name_match.group(1).strip().title()

    # Fulfillment type
    for ftype in ("dine-in", "dine in", "takeaway", "take away", "delivery"):
        if ftype.lower() in text.lower():
            result["fulfillment"] = ftype.replace(" ", "-")
            break

    # Total: look for "Total: 250 THB" style
    total_match = re.search(r"total[:\s]+(\d+)", text, re.IGNORECASE)
    if total_match:
        result["total"] = int(total_match.group(1))

    # Items: look for lines like "- Latte x2" or "2x Americano (120 THB)"
    item_patterns = [
        # "- Item Name x2" or "- Item Name (x2)"
        re.compile(
            r"[-•]\s*(.+?)\s*[x×](\d+)", re.IGNORECASE
        ),
        # "2x Item Name"
        re.compile(
            r"(\d+)\s*[x×]\s*(.+?)(?:\s*[-–]\s*\d+|\s*$)", re.IGNORECASE | re.MULTILINE
        ),
        # "Item Name: 2"
        re.compile(
            r"([A-Za-z][A-Za-z\s]{2,30}):\s*(\d+)", re.IGNORECASE
        ),
    ]
    for pattern in item_patterns:
        for m in pattern.finditer(text):
            groups = m.groups()
            if len(groups) == 2:
                try:
                    name_g, qty_g = groups
                    # Determine which group is name vs qty
                    if name_g.strip().isdigit():
                        name_g, qty_g = qty_g, name_g
                    item_name = name_g.strip().title()
                    qty = int(str(qty_g).strip())
                    if item_name and qty > 0:
                        result["items"].append({"name": item_name, "qty": qty, "price": 0})
                except (ValueError, AttributeError):
                    pass

    return result
