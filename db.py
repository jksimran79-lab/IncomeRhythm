"""
db.py — SQLite database layer for IncomeRhythm.
Tables: income_entries, expense_entries, savings_goals, chat_history
"""

import sqlite3
import os
import random
from datetime import date, timedelta
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "incomeRhythm.db")

DEMO_USER = "demo"

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

def init_db() -> None:
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS income_entries (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user      TEXT    NOT NULL,
            entry_date TEXT   NOT NULL,          -- ISO date YYYY-MM-DD
            amount    REAL    NOT NULL,
            source    TEXT    NOT NULL            -- e.g. Swiggy, Tutor, Freelance
        );

        CREATE TABLE IF NOT EXISTS expense_entries (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user      TEXT    NOT NULL,
            entry_date TEXT   NOT NULL,
            amount    REAL    NOT NULL,
            category  TEXT    NOT NULL            -- Essential | Discretionary
        );

        CREATE TABLE IF NOT EXISTS savings_goals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user        TEXT    NOT NULL,
            description TEXT    NOT NULL,
            target      REAL    NOT NULL,
            saved       REAL    NOT NULL DEFAULT 0.0,
            created_at  TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chat_history (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user      TEXT    NOT NULL,
            role      TEXT    NOT NULL,           -- user | assistant
            message   TEXT    NOT NULL,
            ts        TEXT    NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Sample data seeding
# ---------------------------------------------------------------------------

SOURCES = ["Swiggy", "Zomato", "Uber", "Tutoring", "Freelance Design", "Daily Wage"]

def _has_demo_data(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM income_entries WHERE user = ?", (DEMO_USER,)
    ).fetchone()
    return row["cnt"] > 0


def seed_demo_data() -> None:
    """Pre-populate 20 days of realistic irregular income for the demo user."""
    conn = get_connection()
    if _has_demo_data(conn):
        conn.close()
        return

    today = date.today()
    random.seed(42)

    income_rows = []
    expense_rows = []

    # Simulate a delivery+tutoring gig worker
    for i in range(20, 0, -1):
        d = today - timedelta(days=i)
        day_of_week = d.weekday()  # 0=Mon … 6=Sun

        # Weekends earn more for delivery, weekdays for tutoring
        if day_of_week in (5, 6):
            # Weekend: good delivery day
            delivery = round(random.uniform(450, 900), 0)
            income_rows.append((DEMO_USER, d.isoformat(), delivery, "Swiggy"))
            if random.random() > 0.4:
                income_rows.append((DEMO_USER, d.isoformat(), round(random.uniform(100, 300), 0), "Zomato"))
        elif day_of_week in (0, 2, 4):
            # Mon / Wed / Fri: tutoring days
            income_rows.append((DEMO_USER, d.isoformat(), round(random.uniform(300, 600), 0), "Tutoring"))
            if random.random() > 0.5:
                income_rows.append((DEMO_USER, d.isoformat(), round(random.uniform(100, 250), 0), "Swiggy"))
        else:
            # Tue / Thu: typically lean
            if random.random() > 0.3:
                income_rows.append((DEMO_USER, d.isoformat(), round(random.uniform(80, 350), 0), "Swiggy"))

        # Random expenses every ~2 days
        if random.random() > 0.5:
            cat = "Essential" if random.random() > 0.4 else "Discretionary"
            expense_rows.append((DEMO_USER, d.isoformat(), round(random.uniform(30, 250), 0), cat))

    conn.executemany(
        "INSERT INTO income_entries (user, entry_date, amount, source) VALUES (?,?,?,?)",
        income_rows,
    )
    conn.executemany(
        "INSERT INTO expense_entries (user, entry_date, amount, category) VALUES (?,?,?,?)",
        expense_rows,
    )

    # Seed a sample savings goal
    conn.execute(
        "INSERT INTO savings_goals (user, description, target, saved, created_at) VALUES (?,?,?,?,date('now'))",
        (DEMO_USER, "Emergency fund (1 month expenses)", 5000.0, 1200.0),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Income CRUD
# ---------------------------------------------------------------------------

def add_income(user: str, entry_date: str, amount: float, source: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO income_entries (user, entry_date, amount, source) VALUES (?,?,?,?)",
        (user, entry_date, amount, source),
    )
    conn.commit()
    conn.close()


def get_income(user: str, days: Optional[int] = None):
    """Return income rows newest-first. If days given, limit to last N days."""
    conn = get_connection()
    if days:
        since = (date.today() - timedelta(days=days)).isoformat()
        rows = conn.execute(
            "SELECT * FROM income_entries WHERE user=? AND entry_date >= ? ORDER BY entry_date DESC",
            (user, since),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM income_entries WHERE user=? ORDER BY entry_date DESC",
            (user,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Expense CRUD
# ---------------------------------------------------------------------------

def add_expense(user: str, entry_date: str, amount: float, category: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO expense_entries (user, entry_date, amount, category) VALUES (?,?,?,?)",
        (user, entry_date, amount, category),
    )
    conn.commit()
    conn.close()


def get_expenses(user: str, days: Optional[int] = None):
    conn = get_connection()
    if days:
        since = (date.today() - timedelta(days=days)).isoformat()
        rows = conn.execute(
            "SELECT * FROM expense_entries WHERE user=? AND entry_date >= ? ORDER BY entry_date DESC",
            (user, since),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM expense_entries WHERE user=? ORDER BY entry_date DESC",
            (user,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Savings Goals
# ---------------------------------------------------------------------------

def get_goals(user: str):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM savings_goals WHERE user=? ORDER BY id DESC", (user,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_goal(user: str, description: str, target: float) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO savings_goals (user, description, target, saved, created_at) VALUES (?,?,?,0,date('now'))",
        (user, description, target),
    )
    conn.commit()
    conn.close()


def update_goal_saved(goal_id: int, saved: float) -> None:
    conn = get_connection()
    conn.execute("UPDATE savings_goals SET saved=? WHERE id=?", (saved, goal_id))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Chat history
# ---------------------------------------------------------------------------

def append_chat(user: str, role: str, message: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO chat_history (user, role, message) VALUES (?,?,?)",
        (user, role, message),
    )
    conn.commit()
    conn.close()


def get_chat_history(user: str, limit: int = 20):
    conn = get_connection()
    rows = conn.execute(
        "SELECT role, message FROM chat_history WHERE user=? ORDER BY id DESC LIMIT ?",
        (user, limit),
    ).fetchall()
    conn.close()
    return list(reversed([dict(r) for r in rows]))
