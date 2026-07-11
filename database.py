import sqlite3
from datetime import datetime


DB_NAME = "water_bot.db"


def create_table():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        bottles INTEGER,
        money INTEGER,
        date TEXT
    )
    """)

    conn.commit()
    conn.close()


def save_record(user, bottles, money):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO records
        (user, bottles, money, date)
        VALUES (?, ?, ?, ?)
        """,
        (
            user,
            bottles,
            money,
            datetime.now().strftime("%Y-%m-%d")
        )
    )

    conn.commit()
    conn.close()
def get_today_records():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")

    cur.execute(
        """
        SELECT SUM(bottles), SUM(money)
        FROM records
        WHERE date = ?
        """,
        (today,)
    )

    result = cur.fetchone()

    conn.close()

    if result[0] is None:
        return 0, 0

    return result[0], result[1]
