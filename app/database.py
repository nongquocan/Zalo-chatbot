"""
Module quản lý SQLite database cho chatbot.

Tables:
  - conversations: lưu lịch sử hội thoại bền vững (thay thế in-memory)
  - orders:        lưu đơn hàng khi khách chốt đơn
  - analytics:     ghi log sự kiện để thống kê (tin nhắn, fallback, lỗi...)
"""
import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import contextmanager


DB_PATH = Path(__file__).parent.parent / "data" / "chatbot.db"


# ─────────────────────────────────────────────
# Connection Management
# ─────────────────────────────────────────────

@contextmanager
def get_connection():
    """
    Context manager cho database connection.
    Tự động commit khi thành công, rollback khi lỗi.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")     # Tăng hiệu suất đọc đồng thời
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ─────────────────────────────────────────────
# Database Initialization
# ─────────────────────────────────────────────

def init_db():
    """Khởi tạo database và tạo các bảng nếu chưa tồn tại."""
    # Đảm bảo thư mục data/ tồn tại
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        conn.executescript("""
            -- Bảng lịch sử hội thoại
            CREATE TABLE IF NOT EXISTS conversations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT NOT NULL,
                role        TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content     TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_conv_user
                ON conversations(user_id);
            CREATE INDEX IF NOT EXISTS idx_conv_created
                ON conversations(created_at);

            -- Bảng đơn hàng
            CREATE TABLE IF NOT EXISTS orders (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id          TEXT NOT NULL,
                user_name        TEXT DEFAULT 'Khách hàng',
                products         TEXT NOT NULL,      -- JSON array
                total_amount     INTEGER DEFAULT 0,
                shipping_address TEXT,
                payment_method   TEXT,
                note             TEXT,
                status           TEXT DEFAULT 'pending'
                                 CHECK(status IN (
                                     'pending','confirmed','shipped',
                                     'delivered','cancelled'
                                 )),
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_orders_user
                ON orders(user_id);
            CREATE INDEX IF NOT EXISTS idx_orders_status
                ON orders(status);

            -- Bảng analytics / event log
            CREATE TABLE IF NOT EXISTS analytics (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT NOT NULL,
                event_type  TEXT NOT NULL,   -- 'message','fallback','order','error'
                detail      TEXT,            -- JSON bổ sung
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_analytics_type
                ON analytics(event_type);
            CREATE INDEX IF NOT EXISTS idx_analytics_created
                ON analytics(created_at);

            -- Bảng lưu access_token/refresh_token Zalo OA hiện hành (chỉ 1 dòng,
            -- id cố định = 1). Access token Zalo chỉ sống ~1 giờ và refresh_token
            -- chỉ dùng được 1 lần nên PHẢI lưu bền vững, không giữ trong biến
            -- process (mất khi restart) hay hằng số .env (không tự cập nhật được).
            CREATE TABLE IF NOT EXISTS zalo_tokens (
                id            INTEGER PRIMARY KEY CHECK (id = 1),
                access_token  TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                expires_at    INTEGER NOT NULL,  -- unix timestamp (giây)
                updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    print("[DB] Database initialized successfully.")


# ─────────────────────────────────────────────
# Conversation Operations
# ─────────────────────────────────────────────

def save_message(user_id: str, role: str, content: str):
    """Lưu một tin nhắn vào database."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO conversations (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, role, content),
        )


def get_conversation_history(
    user_id: str, limit: int = 20
) -> List[Dict[str, str]]:
    """
    Lấy lịch sử hội thoại gần nhất của một user.
    Trả về theo thứ tự thời gian (cũ → mới).
    """
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT role, content, created_at
               FROM conversations
               WHERE user_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    # Đảo ngược để ra thứ tự thời gian
    return [
        {"role": r["role"], "content": r["content"], "created_at": r["created_at"]}
        for r in reversed(rows)
    ]


def clear_conversation(user_id: str) -> int:
    """Xóa toàn bộ lịch sử hội thoại của user trong database. Trả về số dòng đã xóa."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM conversations WHERE user_id = ?", (user_id,)
        )
    return cursor.rowcount


def get_conversation_count(user_id: str) -> int:
    """Đếm tổng số tin nhắn của user trong database."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM conversations WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return row["cnt"] if row else 0


def cleanup_old_conversations(days: int = 30) -> int:
    """Xóa các cuộc hội thoại cũ hơn N ngày. Trả về số dòng đã xóa."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM conversations WHERE created_at < datetime('now', ?)",
            (f"-{days} days",),
        )
    return cursor.rowcount


# ─────────────────────────────────────────────
# Order Operations
# ─────────────────────────────────────────────

def create_order(
    user_id: str,
    user_name: str = "Khách hàng",
    products: list = None,
    total_amount: int = 0,
    shipping_address: str = "",
    payment_method: str = "",
    note: str = "",
) -> int:
    """Tạo đơn hàng mới. Trả về order ID."""
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO orders
               (user_id, user_name, products, total_amount,
                shipping_address, payment_method, note)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                user_name,
                json.dumps(products or [], ensure_ascii=False),
                total_amount,
                shipping_address,
                payment_method,
                note,
            ),
        )
    return cursor.lastrowid


def get_orders(
    user_id: Optional[str] = None, status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Lấy danh sách đơn hàng, có thể lọc theo user_id và/hoặc status."""
    query = "SELECT * FROM orders WHERE 1=1"
    params: list = []
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    results = []
    for row in rows:
        d = dict(row)
        d["products"] = json.loads(d["products"])
        results.append(d)
    return results


def update_order_status(order_id: int, status: str):
    """Cập nhật trạng thái đơn hàng."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, order_id),
        )


# ─────────────────────────────────────────────
# Analytics Operations
# ─────────────────────────────────────────────

def log_event(user_id: str, event_type: str, detail: Optional[dict] = None):
    """Ghi một sự kiện analytics."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO analytics (user_id, event_type, detail) VALUES (?, ?, ?)",
            (
                user_id,
                event_type,
                json.dumps(detail, ensure_ascii=False) if detail else None,
            ),
        )


def get_stats(days: int = 7) -> Dict[str, Any]:
    """Lấy thống kê cơ bản trong N ngày gần nhất."""
    cutoff = f"-{days} days"
    with get_connection() as conn:
        total_messages = conn.execute(
            "SELECT COUNT(*) AS cnt FROM analytics "
            "WHERE event_type = 'message' AND created_at > datetime('now', ?)",
            (cutoff,),
        ).fetchone()["cnt"]

        total_fallbacks = conn.execute(
            "SELECT COUNT(*) AS cnt FROM analytics "
            "WHERE event_type = 'fallback' AND created_at > datetime('now', ?)",
            (cutoff,),
        ).fetchone()["cnt"]

        unique_users = conn.execute(
            "SELECT COUNT(DISTINCT user_id) AS cnt FROM analytics "
            "WHERE created_at > datetime('now', ?)",
            (cutoff,),
        ).fetchone()["cnt"]

        total_orders = conn.execute(
            "SELECT COUNT(*) AS cnt FROM orders "
            "WHERE created_at > datetime('now', ?)",
            (cutoff,),
        ).fetchone()["cnt"]

    return {
        "period_days": days,
        "total_messages": total_messages,
        "total_fallbacks": total_fallbacks,
        "unique_users": unique_users,
        "total_orders": total_orders,
    }


# ─────────────────────────────────────────────
# Zalo OA Token Storage
# ─────────────────────────────────────────────

def save_zalo_token(access_token: str, refresh_token: str, expires_at: int):
    """Lưu (ghi đè) access_token/refresh_token Zalo OA hiện hành."""
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO zalo_tokens (id, access_token, refresh_token, expires_at, updated_at)
               VALUES (1, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(id) DO UPDATE SET
                   access_token = excluded.access_token,
                   refresh_token = excluded.refresh_token,
                   expires_at = excluded.expires_at,
                   updated_at = CURRENT_TIMESTAMP""",
            (access_token, refresh_token, expires_at),
        )


def get_zalo_token() -> Optional[Dict[str, Any]]:
    """Lấy access_token/refresh_token Zalo OA đang lưu, hoặc None nếu chưa có."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT access_token, refresh_token, expires_at FROM zalo_tokens WHERE id = 1"
        ).fetchone()
    return dict(row) if row else None


def get_recent_users(limit: int = 50) -> Dict[str, Any]:
    """Lấy danh sách user gần nhất có hội thoại, kèm số tin nhắn."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT user_id,
                      COUNT(*) AS message_count,
                      MAX(created_at) AS last_active
               FROM conversations
               GROUP BY user_id
               ORDER BY last_active DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return {
        "total": len(rows),
        "users": [
            {
                "user_id": r["user_id"],
                "message_count": r["message_count"],
                "last_active": r["last_active"],
            }
            for r in rows
        ],
    }
