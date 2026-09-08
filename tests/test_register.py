"""Tests for the /register route — Step 2 (Registration)."""

from werkzeug.security import check_password_hash

from database import db as db_module


def _user(email):
    conn = db_module._connect()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()


def _user_count():
    conn = db_module._connect()
    try:
        return conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"]
    finally:
        conn.close()


# ------------------------------------------------------------------ #
# GET                                                                 #
# ------------------------------------------------------------------ #

def test_get_register_renders_form(client):
    resp = client.get("/register")
    assert resp.status_code == 200
    assert b'action="/register"' in resp.data


# ------------------------------------------------------------------ #
# Successful registration                                             #
# ------------------------------------------------------------------ #

def test_post_valid_creates_user_and_redirects_to_login(client):
    before = _user_count()

    resp = client.post(
        "/register",
        data={
            "name": "Asha Rao",
            "email": "asha@example.com",
            "password": "supersecret",
        },
    )

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    assert _user_count() == before + 1

    row = _user("asha@example.com")
    assert row["name"] == "Asha Rao"
    assert row["password_hash"] != "supersecret"
    assert check_password_hash(row["password_hash"], "supersecret")


def test_post_normalises_email_case_and_whitespace(client):
    client.post(
        "/register",
        data={
            "name": "  Bina  ",
            "email": "  Bina@Example.COM  ",
            "password": "longenough1",
        },
    )

    assert _user("bina@example.com") is not None
    assert _user("bina@example.com")["name"] == "Bina"


# ------------------------------------------------------------------ #
# Rejected registration                                               #
# ------------------------------------------------------------------ #

def test_post_duplicate_email_is_rejected(client):
    # nitish@example.com is inserted by seed_db().
    before = _user_count()

    resp = client.post(
        "/register",
        data={
            "name": "Someone Else",
            "email": "nitish@example.com",
            "password": "anotherpassword",
        },
    )

    assert resp.status_code == 200
    assert b"already exists" in resp.data
    assert _user_count() == before


def test_post_duplicate_email_is_case_insensitive(client):
    resp = client.post(
        "/register",
        data={
            "name": "Someone Else",
            "email": "NITISH@example.com",
            "password": "anotherpassword",
        },
    )
    assert resp.status_code == 200
    assert b"already exists" in resp.data


def test_post_short_password_is_rejected(client):
    before = _user_count()

    resp = client.post(
        "/register",
        data={
            "name": "Short Pw",
            "email": "shortpw@example.com",
            "password": "1234567",  # 7 chars
        },
    )

    assert resp.status_code == 200
    assert b"at least 8 characters" in resp.data
    assert _user_count() == before
    assert _user("shortpw@example.com") is None


def test_post_missing_fields_is_rejected(client):
    before = _user_count()

    resp = client.post(
        "/register",
        data={"name": "", "email": "", "password": ""},
    )

    assert resp.status_code == 200
    assert b"required" in resp.data
    assert _user_count() == before


def test_rejected_registration_preserves_entered_values(client):
    resp = client.post(
        "/register",
        data={
            "name": "Keep Me",
            "email": "nitish@example.com",
            "password": "anotherpassword",
        },
    )
    assert b'value="Keep Me"' in resp.data
    assert b'value="nitish@example.com"' in resp.data
