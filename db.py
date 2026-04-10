"""
db.py - All PostgreSQL access for Sunny Cafe Bot.
This is the ONLY file that touches the database.
"""

import logging
import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
import psycopg2.pool

logger = logging.getLogger(__name__)

# ── Connection pool ───────────────────────────────────────────────────────────

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def init_pool() -> None:
    global _pool
    _pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=10,
        dsn=os.environ["DATABASE_URL"],
        sslmode="require",
    )
    logger.info("PostgreSQL connection pool initialised")


@contextmanager
def _conn():
    assert _pool is not None, "Call init_pool() first"
    conn = _pool.getconn()
    conn.autocommit = False
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


def _cur(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


# ── Schema init ───────────────────────────────────────────────────────────────


def init_schema() -> None:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id         SERIAL PRIMARY KEY,
                name_en    TEXT    NOT NULL,
                name_zh    TEXT    NOT NULL,
                emoji      TEXT    DEFAULT '•',
                image_file TEXT,
                sort_order INTEGER DEFAULT 0,
                available  BOOLEAN DEFAULT TRUE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id          SERIAL PRIMARY KEY,
                category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
                name_en     TEXT    NOT NULL,
                name_zh     TEXT    NOT NULL,
                price       INTEGER NOT NULL,
                available   BOOLEAN DEFAULT TRUE,
                sort_order  INTEGER DEFAULT 0
            )
        """)
        cur.execute("ALTER TABLE items ADD COLUMN IF NOT EXISTS image_file TEXT")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS discounts (
                id         SERIAL PRIMARY KEY,
                name       TEXT    NOT NULL,
                type       TEXT    NOT NULL CHECK (type IN ('percent','fixed')),
                value      INTEGER NOT NULL,
                active     BOOLEAN DEFAULT TRUE,
                expires_at TIMESTAMPTZ
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS store_info (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id         SERIAL PRIMARY KEY,
                title      TEXT,
                body       TEXT    NOT NULL,
                active     BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id            SERIAL PRIMARY KEY,
                user_id       TEXT    NOT NULL,
                display_name  TEXT,
                customer_name TEXT,
                phone         TEXT,
                fulfillment   TEXT CHECK (fulfillment IN ('dine-in','takeaway','delivery')),
                address       TEXT,
                pickup_time   TEXT,
                total         INTEGER,
                discount_amt  INTEGER DEFAULT 0,
                status        TEXT DEFAULT 'pending'
                                   CHECK (status IN ('pending','ready','done','cancelled')),
                created_at    TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id       SERIAL PRIMARY KEY,
                order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
                name_en  TEXT    NOT NULL,
                name_zh  TEXT    NOT NULL,
                price    INTEGER NOT NULL,
                qty      INTEGER NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS carts (
                user_id  TEXT    NOT NULL,
                item_id  INTEGER REFERENCES items(id) ON DELETE CASCADE,
                qty      INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (user_id, item_id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_prefs (
                user_id TEXT PRIMARY KEY,
                lang    TEXT DEFAULT 'zh'
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id         SERIAL PRIMARY KEY,
                user_id    TEXT NOT NULL,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                id            SERIAL PRIMARY KEY,
                username      TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role          TEXT NOT NULL CHECK (role IN ('owner','staff')),
                active        BOOLEAN DEFAULT TRUE,
                created_at    TIMESTAMPTZ DEFAULT NOW()
            )
        """)
    logger.info("Schema ready")


# ── Categories ────────────────────────────────────────────────────────────────


def get_categories(available_only: bool = True) -> list[dict]:
    with _conn() as conn, _cur(conn) as cur:
        q = "SELECT * FROM categories"
        if available_only:
            q += " WHERE available = TRUE"
        q += " ORDER BY sort_order, id"
        cur.execute(q)
        return cur.fetchall()


def get_category(category_id: int) -> dict | None:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute("SELECT * FROM categories WHERE id = %s", (category_id,))
        return cur.fetchone()


def create_category(
    name_en: str,
    name_zh: str,
    emoji: str = "•",
    image_file: str | None = None,
    sort_order: int = 0,
) -> dict:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute(
            """INSERT INTO categories (name_en, name_zh, emoji, image_file, sort_order)
               VALUES (%s, %s, %s, %s, %s) RETURNING *""",
            (name_en, name_zh, emoji, image_file, sort_order),
        )
        return cur.fetchone()


def update_category(category_id: int, **fields) -> dict | None:
    allowed = {"name_en", "name_zh", "emoji", "image_file", "sort_order", "available"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return get_category(category_id)
    sets = ", ".join(f"{k} = %s" for k in fields)
    with _conn() as conn, _cur(conn) as cur:
        cur.execute(
            f"UPDATE categories SET {sets} WHERE id = %s RETURNING *",
            (*fields.values(), category_id),
        )
        return cur.fetchone()


def delete_category(category_id: int) -> None:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute("DELETE FROM categories WHERE id = %s", (category_id,))


# ── Items ─────────────────────────────────────────────────────────────────────


def get_items(category_id: int, available_only: bool = True) -> list[dict]:
    with _conn() as conn, _cur(conn) as cur:
        q = "SELECT * FROM items WHERE category_id = %s"
        params = [category_id]
        if available_only:
            q += " AND available = TRUE"
        q += " ORDER BY sort_order, id"
        cur.execute(q, params)
        return cur.fetchall()


def get_item(item_id: int) -> dict | None:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute("SELECT * FROM items WHERE id = %s", (item_id,))
        return cur.fetchone()


def get_all_items(available_only: bool = True) -> list[dict]:
    with _conn() as conn, _cur(conn) as cur:
        q = "SELECT i.*, c.name_en as cat_en, c.name_zh as cat_zh FROM items i JOIN categories c ON c.id = i.category_id"
        if available_only:
            q += " WHERE i.available = TRUE AND c.available = TRUE"
        q += " ORDER BY c.sort_order, i.sort_order, i.id"
        cur.execute(q)
        return cur.fetchall()


def get_menu_for_liff() -> list[dict]:
    """Return available categories with their items nested — for the LIFF menu page."""
    result = []
    for cat in get_categories(available_only=True):
        entry = {
            "id":         cat["id"],
            "name_en":    cat["name_en"],
            "name_zh":    cat["name_zh"],
            "emoji":      cat["emoji"],
            "image_file": cat["image_file"],
            "sort_order": cat["sort_order"],
            "menu_items": [
                {
                    "id":         item["id"],
                    "name_en":    item["name_en"],
                    "name_zh":    item["name_zh"],
                    "price":      item["price"],
                    "image_file": item["image_file"],
                }
                for item in get_items(cat["id"], available_only=True)
            ],
        }
        result.append(entry)
    return result


def create_item(
    category_id: int, name_en: str, name_zh: str, price: int, sort_order: int = 0, image_file: str | None = None
) -> dict:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute(
            """INSERT INTO items (category_id, name_en, name_zh, price, sort_order, image_file)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING *""",
            (category_id, name_en, name_zh, price, sort_order, image_file),
        )
        return cur.fetchone()


def update_item(item_id: int, **fields) -> dict | None:
    allowed = {"name_en", "name_zh", "price", "available", "sort_order", "category_id", "image_file"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return get_item(item_id)
    sets = ", ".join(f"{k} = %s" for k in fields)
    with _conn() as conn, _cur(conn) as cur:
        cur.execute(
            f"UPDATE items SET {sets} WHERE id = %s RETURNING *",
            (*fields.values(), item_id),
        )
        return cur.fetchone()


def delete_item(item_id: int) -> None:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute("DELETE FROM items WHERE id = %s", (item_id,))


# ── Cart ──────────────────────────────────────────────────────────────────────


def cart_get(user_id: str) -> list[dict]:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute(
            """SELECT c.item_id, c.qty, i.name_en, i.name_zh, i.price
               FROM carts c JOIN items i ON i.id = c.item_id
               WHERE c.user_id = %s ORDER BY c.item_id""",
            (user_id,),
        )
        return cur.fetchall()


def cart_add(user_id: str, item_id: int) -> None:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute(
            """INSERT INTO carts (user_id, item_id, qty) VALUES (%s, %s, 1)
               ON CONFLICT (user_id, item_id) DO UPDATE SET qty = carts.qty + 1""",
            (user_id, item_id),
        )


def cart_clear(user_id: str) -> None:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute("DELETE FROM carts WHERE user_id = %s", (user_id,))


def cart_total(user_id: str) -> int:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute(
            """SELECT COALESCE(SUM(c.qty * i.price), 0) as total
               FROM carts c JOIN items i ON i.id = c.item_id WHERE c.user_id = %s""",
            (user_id,),
        )
        return cur.fetchone()["total"]


# ── Orders ────────────────────────────────────────────────────────────────────


def create_order(
    user_id: str,
    display_name: str | None,
    customer_name: str,
    phone: str,
    fulfillment: str,
    address: str | None,
    pickup_time: str | None,
    total: int,
    discount_amt: int = 0,
) -> dict:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute(
            """INSERT INTO orders
               (user_id, display_name, customer_name, phone, fulfillment,
                address, pickup_time, total, discount_amt)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (
                user_id,
                display_name,
                customer_name,
                phone,
                fulfillment,
                address,
                pickup_time,
                total,
                discount_amt,
            ),
        )
        return cur.fetchone()


def add_order_items(order_id: int, items: list[dict]) -> None:
    with _conn() as conn, _cur(conn) as cur:
        for item in items:
            cur.execute(
                """INSERT INTO order_items (order_id, name_en, name_zh, price, qty)
                   VALUES (%s, %s, %s, %s, %s)""",
                (
                    order_id,
                    item["name_en"],
                    item["name_zh"],
                    item["price"],
                    item["qty"],
                ),
            )


def get_order(order_id: int) -> dict | None:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
        return cur.fetchone()


def get_order_items(order_id: int) -> list[dict]:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute("SELECT * FROM order_items WHERE order_id = %s", (order_id,))
        return cur.fetchall()


def update_order_status(order_id: int, status: str) -> None:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute("UPDATE orders SET status = %s WHERE id = %s", (status, order_id))


def get_orders(status: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
    with _conn() as conn, _cur(conn) as cur:
        q = "SELECT * FROM orders"
        params: list = []
        if status:
            q += " WHERE status = %s"
            params.append(status)
        q += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        cur.execute(q, params)
        return cur.fetchall()


def count_orders(status: str | None = None) -> int:
    with _conn() as conn, _cur(conn) as cur:
        q = "SELECT COUNT(*) as n FROM orders"
        params: list = []
        if status:
            q += " WHERE status = %s"
            params.append(status)
        cur.execute(q, params)
        return cur.fetchone()["n"]


def get_today_orders() -> list[dict]:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute(
            """SELECT * FROM orders
               WHERE created_at AT TIME ZONE 'Asia/Taipei' >= (NOW() AT TIME ZONE 'Asia/Taipei')::date
               ORDER BY created_at DESC""",
        )
        return cur.fetchall()


# ── Discounts ─────────────────────────────────────────────────────────────────


def get_active_discounts() -> list[dict]:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute(
            """SELECT * FROM discounts
               WHERE active = TRUE
               AND (expires_at IS NULL OR expires_at > NOW())
               ORDER BY id""",
        )
        return cur.fetchall()


def get_all_discounts() -> list[dict]:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute("SELECT * FROM discounts ORDER BY id DESC")
        return cur.fetchall()


def create_discount(name: str, type_: str, value: int, expires_at=None) -> dict:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute(
            """INSERT INTO discounts (name, type, value, expires_at)
               VALUES (%s, %s, %s, %s) RETURNING *""",
            (name, type_, value, expires_at),
        )
        return cur.fetchone()


def update_discount(discount_id: int, **fields) -> None:
    allowed = {"name", "type", "value", "active", "expires_at"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    sets = ", ".join(f"{k} = %s" for k in fields)
    with _conn() as conn, _cur(conn) as cur:
        cur.execute(
            f"UPDATE discounts SET {sets} WHERE id = %s",
            (*fields.values(), discount_id),
        )


def delete_discount(discount_id: int) -> None:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute("DELETE FROM discounts WHERE id = %s", (discount_id,))


# ── Store info ────────────────────────────────────────────────────────────────


def get_store_info() -> dict:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute("SELECT key, value FROM store_info")
        return {row["key"]: row["value"] for row in cur.fetchall()}


def set_store_info(key: str, value: str) -> None:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute(
            """INSERT INTO store_info (key, value) VALUES (%s, %s)
               ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value""",
            (key, value),
        )


def set_store_info_bulk(data: dict) -> None:
    for key, value in data.items():
        set_store_info(key, value)


# ── Posts ─────────────────────────────────────────────────────────────────────


def get_active_posts() -> list[dict]:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute("SELECT * FROM posts WHERE active = TRUE ORDER BY created_at DESC")
        return cur.fetchall()


def get_all_posts() -> list[dict]:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute("SELECT * FROM posts ORDER BY created_at DESC")
        return cur.fetchall()


def create_post(title: str | None, body: str, active: bool = True) -> dict:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute(
            "INSERT INTO posts (title, body, active) VALUES (%s, %s, %s) RETURNING *",
            (title, body, active),
        )
        return cur.fetchone()


def update_post(post_id: int, **fields) -> None:
    allowed = {"title", "body", "active"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    sets = ", ".join(f"{k} = %s" for k in fields)
    with _conn() as conn, _cur(conn) as cur:
        cur.execute(
            f"UPDATE posts SET {sets} WHERE id = %s",
            (*fields.values(), post_id),
        )


def delete_post(post_id: int) -> None:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute("DELETE FROM posts WHERE id = %s", (post_id,))


# ── User preferences ──────────────────────────────────────────────────────────


def get_lang(user_id: str) -> str:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute("SELECT lang FROM user_prefs WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        return row["lang"] if row else "zh"


def set_lang(user_id: str, lang: str) -> None:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute(
            """INSERT INTO user_prefs (user_id, lang) VALUES (%s, %s)
               ON CONFLICT (user_id) DO UPDATE SET lang = EXCLUDED.lang""",
            (user_id, lang),
        )


# ── Claude FAQ history ────────────────────────────────────────────────────────

MAX_HISTORY = 10


def get_history(user_id: str) -> list[dict]:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute(
            """SELECT role, content FROM messages
               WHERE user_id = %s ORDER BY id DESC LIMIT %s""",
            (user_id, MAX_HISTORY),
        )
        rows = cur.fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def save_message(user_id: str, role: str, content: str) -> None:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute(
            "INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)",
            (user_id, role, content),
        )
        # Prune old messages
        cur.execute(
            """DELETE FROM messages WHERE user_id = %s AND id NOT IN (
               SELECT id FROM messages WHERE user_id = %s
               ORDER BY id DESC LIMIT %s)""",
            (user_id, user_id, MAX_HISTORY),
        )


def has_history(user_id: str) -> bool:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute("SELECT 1 FROM messages WHERE user_id = %s LIMIT 1", (user_id,))
        return cur.fetchone() is not None


# ── Admin users ───────────────────────────────────────────────────────────────


def get_admin_user(username: str) -> dict | None:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute(
            "SELECT * FROM admin_users WHERE username = %s AND active = TRUE",
            (username,),
        )
        return cur.fetchone()


def get_admin_user_by_id(user_id: int) -> dict | None:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute("SELECT * FROM admin_users WHERE id = %s", (user_id,))
        return cur.fetchone()


def get_all_admin_users() -> list[dict]:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute("SELECT * FROM admin_users ORDER BY role, username")
        return cur.fetchall()


def create_admin_user(username: str, password_hash: str, role: str) -> dict:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute(
            """INSERT INTO admin_users (username, password_hash, role)
               VALUES (%s, %s, %s) RETURNING *""",
            (username, password_hash, role),
        )
        return cur.fetchone()


def update_admin_user(user_id: int, **fields) -> None:
    allowed = {"username", "password_hash", "role", "active"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    sets = ", ".join(f"{k} = %s" for k in fields)
    with _conn() as conn, _cur(conn) as cur:
        cur.execute(
            f"UPDATE admin_users SET {sets} WHERE id = %s",
            (*fields.values(), user_id),
        )


def delete_admin_user(user_id: int) -> None:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute("DELETE FROM admin_users WHERE id = %s", (user_id,))


def admin_user_exists() -> bool:
    with _conn() as conn, _cur(conn) as cur:
        cur.execute("SELECT 1 FROM admin_users LIMIT 1")
        return cur.fetchone() is not None
