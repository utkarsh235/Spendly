"""Tests for the /login and /logout routes — Step 3 (Authentication)."""

# nitish@example.com is seeded by seed_db() with the password "password123".
SEED_EMAIL = "nitish@example.com"
SEED_PASSWORD = "password123"


# ------------------------------------------------------------------ #
# GET                                                                 #
# ------------------------------------------------------------------ #

def test_get_login_renders_form(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b'action="/login"' in resp.data


# ------------------------------------------------------------------ #
# Successful login                                                    #
# ------------------------------------------------------------------ #

def test_post_valid_credentials_starts_session_and_redirects(client):
    resp = client.post(
        "/login",
        data={"email": SEED_EMAIL, "password": SEED_PASSWORD},
    )

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/dashboard")

    with client.session_transaction() as sess:
        assert sess["user_id"] == 1
        assert sess["user_name"] == "Nitish Kumar"


def test_post_normalises_email_case_and_whitespace(client):
    resp = client.post(
        "/login",
        data={"email": "  NITISH@Example.COM  ", "password": SEED_PASSWORD},
    )

    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert sess["user_id"] == 1


# ------------------------------------------------------------------ #
# Rejected login                                                      #
# ------------------------------------------------------------------ #

def test_post_wrong_password_is_rejected(client):
    resp = client.post(
        "/login",
        data={"email": SEED_EMAIL, "password": "not-the-password"},
    )

    assert resp.status_code == 200
    assert b"Invalid email or password" in resp.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_post_unknown_email_is_rejected_with_same_message(client):
    resp = client.post(
        "/login",
        data={"email": "ghost@example.com", "password": "whatever123"},
    )

    assert resp.status_code == 200
    assert b"Invalid email or password" in resp.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_rejected_login_preserves_entered_email(client):
    resp = client.post(
        "/login",
        data={"email": SEED_EMAIL, "password": "wrong"},
    )
    assert b'value="nitish@example.com"' in resp.data


# ------------------------------------------------------------------ #
# Logout                                                              #
# ------------------------------------------------------------------ #

def test_logout_clears_session_and_redirects(client):
    client.post("/login", data={"email": SEED_EMAIL, "password": SEED_PASSWORD})
    with client.session_transaction() as sess:
        assert "user_id" in sess

    resp = client.get("/logout")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")

    with client.session_transaction() as sess:
        assert "user_id" not in sess
        assert "user_name" not in sess


def test_password_reset_then_login_with_new_password(client):
    """End-to-end: reset the password, then the new one logs in and the old fails."""
    client.post(
        "/reset-password",
        data={"email": SEED_EMAIL, "password": "freshpass99"},
    )

    old = client.post(
        "/login", data={"email": SEED_EMAIL, "password": SEED_PASSWORD}
    )
    assert old.status_code == 200
    assert b"Invalid email or password" in old.data

    new = client.post(
        "/login", data={"email": SEED_EMAIL, "password": "freshpass99"}
    )
    assert new.status_code == 302
    with client.session_transaction() as sess:
        assert sess["user_id"] == 1
