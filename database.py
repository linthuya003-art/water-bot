import sqlite3
import logging
import os
from datetime import datetime, date
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger("gift_hub.database")

# ─────────────────────────────────────────────────────────────────────
#  Database Configuration
# ─────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(BASE_DIR, "gift_hub.db")
)

@contextmanager
def get_connection():
    """
    SQLite Connection ကို context manager နဲ့ manage —
    commit / rollback / close အလိုအလျောက် လုပ်ပေး
    """
    conn = sqlite3.connect(
    DB_PATH,
    timeout=30,
    check_same_thread=False
)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error("DB Error: %s", e)
        raise
    finally:
        conn.close()


def init_db():
    """
    Database နဲ့ Table တွေ Initialize လုပ်
    """
    logger.info("Database initialize: %s", DB_PATH)

    with get_connection() as conn:
        conn.executescript("""
            -- စာရင်း entries table
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_telegram_id INTEGER NOT NULL,
                user_name TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                bottles INTEGER NOT NULL DEFAULT 0,
                money INTEGER NOT NULL DEFAULT 0,
                price_per_bottle REAL NOT NULL DEFAULT 0,
                tier TEXT NOT NULL DEFAULT '1000',
                entry_date DATE NOT NULL,
                entry_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER NOT NULL DEFAULT 0
            );

                UNIQUE(user_telegram_id, customer_name, bottles, money, entry_date, entry_time)
            -- Admin users table
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL UNIQUE,
                name TEXT NOT NULL,
                added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            -- Settings / Config table
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            -- Indexes for fast queries
            CREATE INDEX IF NOT EXISTS idx_entries_date ON entries(entry_date);
            CREATE INDEX IF NOT EXISTS idx_entries_tier ON entries(tier);
            CREATE INDEX IF NOT EXISTS idx_entries_user ON entries(user_telegram_id);
        """)

    logger.info("Database tables initialized successfully")


def insert_entry(user_id: int, user_name: str, entry_data: dict) -> int:
    """
    စာရင်း entry တစ်ခု database ထဲ ထည့်

    Args:
        user_id: Telegram user ID (ပို့တဲ့သူ)
        user_name: Telegram user name (ပို့တဲ့သူ)
        entry_data: parser က return ပေးတဲ့ dict

    Returns:
        inserted row ID
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO entries
                (user_telegram_id, user_name, customer_name, bottles, money,
                 price_per_bottle, tier, entry_date, entry_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                user_name,
                entry_data["name"],
                entry_data["bottles"],
                entry_data["money"],
                entry_data["price_per_bottle"],
                entry_data["tier"],
                entry_data["date"].isoformat(),
                entry_data["timestamp"].isoformat(),
            )
        )
        row_id = cursor.lastrowid
        logger.info("Entry inserted: id=%d, customer=%s", row_id, entry_data["name"])
        return row_id


def insert_batch_entries(user_id: int, user_name: str, entries: list[dict]) -> list[int]:
    """
    Batch entries တွေကို database ထဲ ထည့်
    """
    ids = []
    with get_connection() as conn:
        for entry in entries:
            cursor = conn.execute(
                """
                INSERT INTO entries
                    (user_telegram_id, user_name, customer_name, bottles, money,
                     price_per_bottle, tier, entry_date, entry_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    user_name,
                    entry["name"],
                    entry["bottles"],
                    entry["money"],
                    entry["price_per_bottle"],
                    entry["tier"],
                    entry["date"].isoformat(),
                    entry["timestamp"].isoformat(),
                )
            )
            ids.append(cursor.lastrowid)

    logger.info("Batch inserted: %d entries", len(ids))
    return ids


# ─────────────────────────────────────────────────────────────────────
#  Report Queries
# ─────────────────────────────────────────────────────────────────────


def get_daily_report(target_date: date) -> dict:
    """
    ရက်တစ်ရက်ရဲ့ စာရင်း report ယူ

    Returns:
        report dictionary with totals and tier breakdown
    """
    with get_connection() as conn:
        # စုစုပေါင်း အနှစ်ချုပ်
        cursor = conn.execute(
            """
            SELECT
                COUNT(*) as customer_count,
                SUM(bottles) as total_bottles,
                SUM(money) as total_money,
                SUM(CASE WHEN tier = '1000' THEN 1 ELSE 0 END) as tier_1000_count,
                SUM(CASE WHEN tier = '1100' THEN 1 ELSE 0 END) as tier_1100_count,
                SUM(CASE WHEN tier = '1300' THEN 1 ELSE 0 END) as tier_1300_count,
                SUM(CASE WHEN tier = '1000' THEN bottles ELSE 0 END) as tier_1000_bottles,
                SUM(CASE WHEN tier = '1100' THEN bottles ELSE 0 END) as tier_1100_bottles,
                SUM(CASE WHEN tier = '1300' THEN bottles ELSE 0 END) as tier_1300_bottles,
                SUM(CASE WHEN tier = '1000' THEN money ELSE 0 END) as tier_1000_money,
                SUM(CASE WHEN tier = '1100' THEN money ELSE 0 END) as tier_1100_money,
                SUM(CASE WHEN tier = '1300' THEN money ELSE 0 END) as tier_1300_money
            FROM entries
            WHERE entry_date = ? AND is_deleted = 0
            """,
            (target_date.isoformat(),)
        )

        row = cursor.fetchone()

        if row["customer_count"] == 0:
            return None

        # ခွဲတွက်အလိုက် အသေးစိတ် list
        cursor = conn.execute(
            """
            SELECT customer_name, bottles, money, tier, entry_time
            FROM entries
            WHERE entry_date = ? AND is_deleted = 0
            ORDER BY entry_time DESC
            """,
            (target_date.isoformat(),)
        )

        details = [dict(r) for r in cursor.fetchall()]

        report = {
            "date": target_date,
            "customer_count": row["customer_count"],
            "total_bottles": row["total_bottles"] or 0,
            "total_money": row["total_money"] or 0,
            "tier_breakdown": {
                "1000": {
                    "count": row["tier_1000_count"] or 0,
                    "bottles": row["tier_1000_bottles"] or 0,
                    "money": row["tier_1000_money"] or 0,
                },
                "1100": {
                    "count": row["tier_1100_count"] or 0,
                    "bottles": row["tier_1100_bottles"] or 0,
                    "money": row["tier_1100_money"] or 0,
                },
                "1300": {
                    "count": row["tier_1300_count"] or 0,
                    "bottles": row["tier_1300_bottles"] or 0,
                    "money": row["tier_1300_money"] or 0,
                },
            },
            "details": details,
        }

        return report


def get_monthly_report(year: int, month: int) -> dict:
    """
    လတစ်လရဲ့ စာရင်း report ယူ
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                COUNT(*) as customer_count,
                SUM(bottles) as total_bottles,
                SUM(money) as total_money,
                SUM(CASE WHEN tier = '1000' THEN 1 ELSE 0 END) as tier_1000_count,
                SUM(CASE WHEN tier = '1100' THEN 1 ELSE 0 END) as tier_1100_count,
                SUM(CASE WHEN tier = '1300' THEN 1 ELSE 0 END) as tier_1300_count,
                SUM(CASE WHEN tier = '1000' THEN bottles ELSE 0 END) as tier_1000_bottles,
                SUM(CASE WHEN tier = '1100' THEN bottles ELSE 0 END) as tier_1100_bottles,
                SUM(CASE WHEN tier = '1300' THEN bottles ELSE 0 END) as tier_1300_bottles,
                SUM(CASE WHEN tier = '1000' THEN money ELSE 0 END) as tier_1000_money,
                SUM(CASE WHEN tier = '1100' THEN money ELSE 0 END) as tier_1100_money,
                SUM(CASE WHEN tier = '1300' THEN money ELSE 0 END) as tier_1300_money
            FROM entries
            WHERE strftime('%Y', entry_date) = ?
              AND strftime('%m', entry_date) = ?
              AND is_deleted = 0
            """,
            (str(year), f"{month:02d}")
        )

        row = cursor.fetchone()

        if row["customer_count"] == 0:
            return None

        # နေ့အလိုက် breakdown
        cursor = conn.execute(
            """
            SELECT
                entry_date,
                COUNT(*) as customer_count,
                SUM(bottles) as total_bottles,
                SUM(money) as total_money
            FROM entries
            WHERE strftime('%Y', entry_date) = ?
              AND strftime('%m', entry_date) = ?
              AND is_deleted = 0
            GROUP BY entry_date
            ORDER BY entry_date DESC
            """,
            (str(year), f"{month:02d}")
        )

        daily_breakdown = [dict(r) for r in cursor.fetchall()]

        report = {
            "year": year,
            "month": month,
            "customer_count": row["customer_count"],
            "total_bottles": row["total_bottles"] or 0,
            "total_money": row["total_money"] or 0,
            "tier_breakdown": {
                "1000": {
                    "count": row["tier_1000_count"] or 0,
                    "bottles": row["tier_1000_bottles"] or 0,
                    "money": row["tier_1000_money"] or 0,
                },
                "1100": {
                    "count": row["tier_1100_count"] or 0,
                    "bottles": row["tier_1100_bottles"] or 0,
                    "money": row["tier_1100_money"] or 0,
                },
                "1300": {
                    "count": row["tier_1300_count"] or 0,
                    "bottles": row["tier_1300_bottles"] or 0,
                    "money": row["tier_1300_money"] or 0,
                },
            },
            "daily_breakdown": daily_breakdown,
        }

        return report


# ─────────────────────────────────────────────────────────────────────
#  Admin Management
# ─────────────────────────────────────────────────────────────────────


def is_admin(telegram_id: int) -> bool:
    """
    Telegram user တစ်ယောက် Admin ဟုတ်မဟုတ် စစ်
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT 1 FROM admins WHERE telegram_id = ?",
            (telegram_id,)
        )
        return cursor.fetchone() is not None


def add_admin(telegram_id: int, name: str) -> bool:
    """
    Admin user ထည့်
    """
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO admins (telegram_id, name) VALUES (?, ?)",
                (telegram_id, name)
            )
        logger.info("Admin added: %d (%s)", telegram_id, name)
        return True
    except Exception as e:
        logger.error("Admin add failed: %s", e)
        return False


def remove_admin(telegram_id: int) -> bool:
    """
    Admin user ဖျက်
    """
    try:
        with get_connection() as conn:
            conn.execute(
                "DELETE FROM admins WHERE telegram_id = ?",
                (telegram_id,)
            )
        logger.info("Admin removed: %d", telegram_id)
        return True
    except Exception as e:
        logger.error("Admin remove failed: %s", e)
        return False


def get_all_admins() -> list[dict]:
    """
    Admin list ရ
    """
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM admins ORDER BY added_at DESC")
        return [dict(r) for r in cursor.fetchall()]


# ─────────────────────────────────────────────────────────────────────
#  Entry Management
# ─────────────────────────────────────────────────────────────────────


def delete_entry(entry_id: int) -> bool:
    """
    Entry soft delete (is_deleted = 1)
    """
    try:
        with get_connection() as conn:
            conn.execute(
                "UPDATE entries SET is_deleted = 1 WHERE id = ?",
                (entry_id,)
            )
        logger.info("Entry deleted: id=%d", entry_id)
        return True
    except Exception as e:
        logger.error("Entry delete failed: %s", e)
        return False


def get_entry_by_id(entry_id: int) -> Optional[dict]:
    """
    Entry ID နဲ့ entry တစ်ခု ရ
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM entries WHERE id = ?",
            (entry_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_entries_by_date(target_date: date) -> list[dict]:
    """
    ရက်တစ်ရက်ရဲ့ entries list ရ
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM entries
            WHERE entry_date = ? AND is_deleted = 0
            ORDER BY entry_time DESC
            """,
            (target_date.isoformat(),)
        )
        return [dict(r) for r in cursor.fetchall()]


# ─────────────────────────────────────────────────────────────────────
#  Export Data
# ─────────────────────────────────────────────────────────────────────


def get_export_data(target_date: Optional[date] = None, month_year: Optional[tuple[int, int]] = None) -> list[dict]:
    """
    Excel export အတွက် data ရ

    Args:
        target_date: specific date filter
        month_year: (year, month) tuple for monthly filter
    """
    with get_connection() as conn:
        if target_date:
            cursor = conn.execute(
                """
                SELECT * FROM entries
                WHERE entry_date = ? AND is_deleted = 0
                ORDER BY entry_time
                """,
                (target_date.isoformat(),)
            )
        elif month_year:
            year, month = month_year
            cursor = conn.execute(
                """
                SELECT * FROM entries
                WHERE strftime('%Y', entry_date) = ?
                  AND strftime('%m', entry_date) = ?
                  AND is_deleted = 0
                ORDER BY entry_time
                """,
                (str(year), f"{month:02d}")
            )
        else:
            cursor = conn.execute(
                """
                SELECT * FROM entries
                WHERE is_deleted = 0
                ORDER BY entry_date DESC, entry_time DESC
                """
            )

        return [dict(r) for r in cursor.fetchall()]


# ─────────────────────────────────────────────────────────────────────
#  Initialize on import
# ─────────────────────────────────────────────────────────────────────

# Initialize Database
init_db()
