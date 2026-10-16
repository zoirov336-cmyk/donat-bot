import sqlite3
import time
import os

import config

_dir = os.path.dirname(config.DB_PATH)
if _dir:
    os.makedirs(_dir, exist_ok=True)

_c = sqlite3.connect(config.DB_PATH, check_same_thread=False, isolation_level=None)
_c.row_factory = sqlite3.Row
_c.executescript(
    """
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT,
        full_name TEXT,
        item_id TEXT NOT NULL,
        item_title TEXT NOT NULL,
        price INTEGER NOT NULL,
        nick TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        done_cmds INTEGER NOT NULL DEFAULT 0,
        error TEXT,
        proof_file_id TEXT,
        proof_uid TEXT,
        proof_kind TEXT,
        created_at INTEGER,
        updated_at INTEGER
    );
    CREATE TABLE IF NOT EXISTS admin_msgs (
        order_id INTEGER NOT NULL,
        chat_id INTEGER NOT NULL,
        message_id INTEGER NOT NULL
    );
    """
)


def _now() -> int:
    return int(time.time())


def create_order(user, item, nick, proof_file_id, proof_uid, proof_kind) -> int:
    cur = _c.execute(
        "INSERT INTO orders (user_id, username, full_name, item_id, item_title, price, nick,"
        " proof_file_id, proof_uid, proof_kind, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (user.id, user.username, user.full_name, item["id"], item["full_title"], item["price"],
         nick, proof_file_id, proof_uid, proof_kind, _now(), _now()),
    )
    return cur.lastrowid


def get(order_id: int):
    return _c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()


def claim(order_id: int) -> bool:
    """pending/failed -> processing (faqat bitta bosish o'tadi)."""
    cur = _c.execute(
        "UPDATE orders SET status='processing', updated_at=? WHERE id=? AND status IN ('pending','failed')",
        (_now(), order_id),
    )
    return cur.rowcount == 1


def reject(order_id: int) -> bool:
    cur = _c.execute(
        "UPDATE orders SET status='rejected', updated_at=? WHERE id=? AND status IN ('pending','failed')",
        (_now(), order_id),
    )
    return cur.rowcount == 1


def mark_manual_done(order_id: int) -> bool:
    cur = _c.execute(
        "UPDATE orders SET status='done', updated_at=? WHERE id=? AND status='failed'",
        (_now(), order_id),
    )
    return cur.rowcount == 1


def set_progress(order_id: int, done_cmds: int):
    _c.execute("UPDATE orders SET done_cmds=?, updated_at=? WHERE id=?", (done_cmds, _now(), order_id))


def set_status(order_id: int, status: str, error: str | None = None):
    _c.execute("UPDATE orders SET status=?, error=?, updated_at=? WHERE id=?", (status, error, _now(), order_id))


def count_pending(user_id: int) -> int:
    return _c.execute(
        "SELECT COUNT(*) FROM orders WHERE user_id=? AND status IN ('pending','processing','failed')",
        (user_id,),
    ).fetchone()[0]


def proof_used_before(proof_uid: str) -> bool:
    if not proof_uid:
        return False
    return _c.execute("SELECT 1 FROM orders WHERE proof_uid=? LIMIT 1", (proof_uid,)).fetchone() is not None


def user_orders(user_id: int, limit: int = 5):
    return _c.execute(
        "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit)
    ).fetchall()


def pending_orders(limit: int = 30):
    return _c.execute(
        "SELECT * FROM orders WHERE status IN ('pending','failed') ORDER BY id LIMIT ?", (limit,)
    ).fetchall()


def add_admin_msg(order_id: int, chat_id: int, message_id: int):
    _c.execute("INSERT INTO admin_msgs VALUES (?,?,?)", (order_id, chat_id, message_id))


def admin_msgs(order_id: int):
    return _c.execute("SELECT chat_id, message_id FROM admin_msgs WHERE order_id=?", (order_id,)).fetchall()


def recover_stuck():
    """Bot o'chib qolganda 'processing'da qolgan buyurtmalarni 'failed' qiladi (admin qayta urinadi)."""
    _c.execute(
        "UPDATE orders SET status='failed', error='Bot qayta ishga tushdi, qayta urinib ko''ring', updated_at=?"
        " WHERE status='processing'",
        (_now(),),
    )
