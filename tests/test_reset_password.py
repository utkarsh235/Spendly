"""Tests for the /reset-password route."""

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


# ------------------------------------------------------------------ #
# GET                                                                 #
# ------------------------------------------------------------------ #

def test_get_reset_password_renders_form(client):
    resp = client.get("/reset-password")
    assert resp.status_code == 200
    assert b'action="/reset-password"' in resp.data


# ------------------------------------------------------------------ #
# Successful reset                                                    #
# ------------------------------------------------------------------ #

def test_post_valid_updates_hash_and_redirects_to_login(client):
    # nitish@example.com is seeded with password "password123".
    old_hash = _user("nitish@example.com")["password_hash"]

    resp = client.post(
        "/reset-password",
        data={"email": "nitish@example.com", "password": "brandnewpass"},
    )

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")

    row = _user("nitish@example.com")
    assert row["password_hash"] != old_hash
    assert check_password_hash(row["password_hash"], "brandnewpass")
    assert not check_password_hash(row["password_hash"], "password123")


def test_post_normalises_email_case_and_whitespace(client):
    resp = client.post(
        "/reset-password",
        data={"email": "  NITISH@Example.COM  ", "password": "anothernewpass"},
    )

    assert resp.status_code == 302
    assert check_password_hash(
        _user("nitish@example.com")["password_hash"], "anothernewpass"
    )


def test_post_only_targeted_user_is_affected(client):
    demo_hash_before = _user("demo@example.com")["password_hash"]

    client.post(
        "/reset-password",
        data={"email": "nitish@example.com", "password": "changedpass1"},
    )

    assert _user("demo@example.com")["password_hash"] == demo_hash_before


# ------------------------------------------------------------------ #
# Rejected reset                                                      #
# ------------------------------------------------------------------ #

def test_post_unknown_email_is_rejected(client):
    resp = client.post(
        "/reset-password",
        data={"email": "nobody@example.com", "password": "whateverpass"},
    )

    assert resp.status_code == 200
    assert b"No account found" in resp.data
    assert _user("nobody@example.com") is None


def test_post_short_password_is_rejected(client):
    old_hash = _user("nitish@example.com")["password_hash"]

    resp = client.post(
        "/reset-password",
        data={"email": "nitish@example.com", "password": "1234567"},  # 7 chars
    )

    assert resp.status_code == 200
    assert b"at least 8 characters" in resp.data
    assert _user("nitish@example.com")["password_hash"] == old_hash


def test_post_missing_fields_is_rejected(client):
    old_hash = _user("nitish@example.com")["password_hash"]

    resp = client.post(
        "/reset-password",
        data={"email": "", "password": ""},
    )

    assert resp.status_code == 200
    assert b"required" in resp.data
    assert _user("nitish@example.com")["password_hash"] == old_hash


def test_rejected_reset_preserves_entered_email(client):
    resp = client.post(
        "/reset-password",
        data={"email": "nitish@example.com", "password": "short"},
    )
    assert b'value="nitish@example.com"' in resp.data
