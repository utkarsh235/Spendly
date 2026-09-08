"""Tests for database/db.py — Step 1 (Database Setup)."""

import sqlite3

import pytest

from database import db as db_module


# ------------------------------------------------------------------ #
# Schema                                                              #
# ------------------------------------------------------------------ #

def test_init_db_creates_tables(initialised_db):
    conn = db_module._connect()
    try:
        names = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    finally:
        conn.close()
    assert {"users", "expenses"} <= names


def test_init_db_creates_user_id_index(initialised_db):
    conn = db_module._connect()
    try:
        names = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
    finally:
        conn.close()
    assert "idx_expenses_user_id" in names


def test_init_db_is_idempotent(initialised_db):
    # A second call must not raise and must not disturb existing rows.
    db_module.seed_db()
    db_module.init_db()

    conn = db_module._connect()
    try:
        users = conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"]
    finally:
        conn.close()
    assert users == len(db_module._SEED_USERS)


# ------------------------------------------------------------------ #
# Connection behaviour                                                #
# ------------------------------------------------------------------ #

def test_connect_uses_row_factory(conn):
    row = conn.execute("SELECT 1 AS answer").fetchone()
    assert row["answer"] == 1


def test_connect_enables_foreign_keys(conn):
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_get_db_returns_same_connection_within_request(app):
    with app.test_request_context("/"):
        assert db_module.get_db() is db_module.get_db()


def test_close_db_closes_connection_and_clears_g(app):
    from flask import g

    with app.app_context():
        conn = db_module.get_db()
        assert "db" in g

        db_module.close_db()

        assert "db" not in g
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")


def test_init_app_registers_teardown(app):
    assert db_module.close_db in app.teardown_appcontext_funcs


# ------------------------------------------------------------------ #
# Constraints                                                         #
# ------------------------------------------------------------------ #

def _make_user(conn, email="a@example.com"):
    cur = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("A", email, "hash"),
    )
    conn.commit()
    return cur.lastrowid


def test_users_email_is_unique(conn):
    _make_user(conn, "dup@example.com")
    with pytest.raises(sqlite3.IntegrityError):
        _make_user(conn, "dup@example.com")


def test_expense_requires_existing_user(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, spent_on) "
            "VALUES (?, ?, ?, ?)",
            (999, 10.0, "Misc", "2025-01-01"),
        )
        conn.commit()


def test_expense_amount_cannot_be_negative(conn):
    user_id = _make_user(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, spent_on) "
            "VALUES (?, ?, ?, ?)",
            (user_id, -1.0, "Misc", "2025-01-01"),
        )
        conn.commit()


def test_deleting_user_cascades_to_expenses(conn):
    user_id = _make_user(conn)
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, spent_on) "
        "VALUES (?, ?, ?, ?)",
        (user_id, 10.0, "Misc", "2025-01-01"),
    )
    conn.commit()

    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()

    remaining = conn.execute(
        "SELECT count(*) AS n FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()["n"]
    assert remaining == 0


# ------------------------------------------------------------------ #
# Seed data                                                           #
# ------------------------------------------------------------------ #

def test_seed_db_inserts_sample_rows(seeded_db):
    conn = db_module._connect()
    try:
        users = conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"]
        expenses = conn.execute(
            "SELECT count(*) AS n FROM expenses"
        ).fetchone()["n"]
    finally:
        conn.close()
    assert users == len(db_module._SEED_USERS)
    assert expenses == len(db_module._SEED_EXPENSES)


def test_seed_db_hashes_passwords(seeded_db):
    from werkzeug.security import check_password_hash

    name, email, plaintext = db_module._SEED_USERS[0]
    conn = db_module._connect()
    try:
        stored = conn.execute(
            "SELECT password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()["password_hash"]
    finally:
        conn.close()
    assert stored != plaintext
    assert check_password_hash(stored, plaintext)


def test_seed_db_is_idempotent(seeded_db):
    db_module.seed_db()
    db_module.seed_db()

    conn = db_module._connect()
    try:
        users = conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"]
        expenses = conn.execute(
            "SELECT count(*) AS n FROM expenses"
        ).fetchone()["n"]
    finally:
        conn.close()
    assert users == len(db_module._SEED_USERS)
    assert expenses == len(db_module._SEED_EXPENSES)
