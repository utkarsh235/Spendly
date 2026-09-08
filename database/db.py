"""Database setup for the expense tracker.

Provides:
    get_db()   — SQLite connection for the current request (row_factory + FK on)
    init_db()  — creates all tables using CREATE TABLE IF NOT EXISTS
    seed_db()  — inserts sample data for development
    init_app() — wires connection teardown into a Flask app

Bootstrap the database from the command line with:
    python -m database.db
"""

import sqlite3
from pathlib import Path

from flask import g
from werkzeug.security import generate_password_hash

# The .db file lives in the project root and is git-ignored.
DB_PATH = Path(__file__).resolve().parent.parent / "expense_tracker.db"


# ------------------------------------------------------------------ #
# Connections                                                         #
# ------------------------------------------------------------------ #

def _connect():
    """Open a new SQLite connection with sane defaults.

    - row_factory = sqlite3.Row so rows behave like dicts: row["email"]
    - foreign_keys = ON because SQLite does NOT enforce them by default,
      and it must be set on every connection.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    """Return the connection for the current request, creating it once.

    The connection is cached on Flask's ``g`` object so every call within
    a single request reuses it. ``close_db`` (registered by ``init_app``)
    closes it when the request ends.
    """
    if "db" not in g:
        g.db = _connect()
    return g.db


def close_db(e=None):
    """Close the request connection if one was opened."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    """Register ``close_db`` so connections are cleaned up after each request."""
    app.teardown_appcontext(close_db)


# ------------------------------------------------------------------ #
# Schema                                                              #
# ------------------------------------------------------------------ #

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS expenses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount      REAL NOT NULL CHECK (amount >= 0),
    category    TEXT NOT NULL,
    description TEXT,
    spent_on    TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_expenses_user_id ON expenses(user_id);
"""


def init_db():
    """Create every table if it does not already exist."""
    conn = _connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------------ #
# Sample data                                                         #
# ------------------------------------------------------------------ #

_SEED_USERS = [
    # (name, email, plaintext password)
    ("Nitish Kumar", "nitish@example.com", "password123"),
    ("Demo User", "demo@example.com", "password123"),
]

_SEED_EXPENSES = [
    # (email, amount, category, description, spent_on)
    ("nitish@example.com", 1200.00, "Rent", "October rent", "2025-10-01"),
    ("nitish@example.com", 85.50, "Groceries", "Weekly shop", "2025-10-03"),
    ("nitish@example.com", 42.00, "Transport", "Metro card top-up", "2025-10-04"),
    ("nitish@example.com", 15.99, "Entertainment", "Movie ticket", "2025-10-05"),
    ("nitish@example.com", 60.00, "Dining", "Dinner with friends", "2025-10-07"),
    ("nitish@example.com", 30.25, "Utilities", "Internet bill", "2025-10-08"),
    ("nitish@example.com", 120.00, "Shopping", "New running shoes", "2025-10-10"),
    ("nitish@example.com", 9.75, "Coffee", "Morning latte", "2025-10-11"),
    ("nitish@example.com", 250.00, "Health", "Dentist appointment", "2025-10-12"),
    ("nitish@example.com", 55.40, "Groceries", "Mid-week restock", "2025-10-14"),
]


def seed_db():
    """Insert sample users and expenses for development.

    Safe to run repeatedly: users are inserted with INSERT OR IGNORE on the
    unique email, and expenses are only seeded for a user that has none yet.
    """
    conn = _connect()
    try:
        for name, email, password in _SEED_USERS:
            conn.execute(
                "INSERT OR IGNORE INTO users (name, email, password_hash) "
                "VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            )

        for email, amount, category, description, spent_on in _SEED_EXPENSES:
            row = conn.execute(
                "SELECT id FROM users WHERE email = ?", (email,)
            ).fetchone()
            if row is None:
                continue
            user_id = row["id"]

            already = conn.execute(
                "SELECT 1 FROM expenses WHERE user_id = ? AND spent_on = ? "
                "AND amount = ? AND category = ?",
                (user_id, spent_on, amount, category),
            ).fetchone()
            if already:
                continue

            conn.execute(
                "INSERT INTO expenses "
                "(user_id, amount, category, description, spent_on) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, amount, category, description, spent_on),
            )

        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------------ #
# CLI bootstrap: python -m database.db                                #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    init_db()
    seed_db()
    print(f"Initialised and seeded {DB_PATH}")
