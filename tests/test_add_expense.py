"""Tests for the /expenses/add route — adding an expense to your own account."""

from database import db as db_module

NITISH = ("nitish@example.com", "password123")  # 10 seeded expenses
DEMO = ("demo@example.com", "password123")       # 0 seeded expenses


def _login(client, creds):
    return client.post("/login", data={"email": creds[0], "password": creds[1]})


def _expenses(email):
    conn = db_module._connect()
    try:
        return conn.execute(
            "SELECT e.* FROM expenses e JOIN users u ON u.id = e.user_id "
            "WHERE u.email = ? ORDER BY e.id",
            (email,),
        ).fetchall()
    finally:
        conn.close()


# ------------------------------------------------------------------ #
# Auth gate                                                           #
# ------------------------------------------------------------------ #

def test_add_expense_requires_login_get(client):
    resp = client.get("/expenses/add")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_add_expense_requires_login_post(client):
    resp = client.post(
        "/expenses/add",
        data={"amount": "10", "category": "Coffee", "spent_on": "2026-09-08"},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    assert len(_expenses("demo@example.com")) == 0


# ------------------------------------------------------------------ #
# GET                                                                 #
# ------------------------------------------------------------------ #

def test_get_renders_form_with_todays_date(client):
    _login(client, DEMO)
    resp = client.get("/expenses/add")
    assert resp.status_code == 200
    assert b'action="/expenses/add"' in resp.data
    assert b'name="amount"' in resp.data
    assert b'name="category"' in resp.data
    assert b'name="spent_on"' in resp.data


# ------------------------------------------------------------------ #
# Successful add                                                      #
# ------------------------------------------------------------------ #

def test_post_valid_inserts_for_current_user_and_redirects(client):
    _login(client, DEMO)

    resp = client.post(
        "/expenses/add",
        data={
            "amount": "23.75",
            "category": "Coffee",
            "description": "Flat white",
            "spent_on": "2026-09-07",
        },
    )

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/dashboard")

    rows = _expenses("demo@example.com")
    assert len(rows) == 1
    assert rows[0]["amount"] == 23.75
    assert rows[0]["category"] == "Coffee"
    assert rows[0]["description"] == "Flat white"
    assert rows[0]["spent_on"] == "2026-09-07"


def test_added_expense_appears_on_the_dashboard(client):
    _login(client, DEMO)
    client.post(
        "/expenses/add",
        data={"amount": "500", "category": "Rent", "spent_on": "2026-09-01"},
    )
    resp = client.get("/dashboard")
    assert b"Rent" in resp.data
    assert b"1 expense logged" in resp.data


def test_blank_description_is_stored_as_null(client):
    _login(client, DEMO)
    client.post(
        "/expenses/add",
        data={"amount": "9", "category": "Misc", "spent_on": "2026-09-05"},
    )
    assert _expenses("demo@example.com")[0]["description"] is None


def test_expense_is_scoped_to_the_logged_in_user(client):
    demo_before = len(_expenses("demo@example.com"))
    nitish_before = len(_expenses("nitish@example.com"))

    _login(client, DEMO)
    client.post(
        "/expenses/add",
        data={"amount": "12", "category": "Coffee", "spent_on": "2026-09-08"},
    )

    assert len(_expenses("demo@example.com")) == demo_before + 1
    assert len(_expenses("nitish@example.com")) == nitish_before


# ------------------------------------------------------------------ #
# Rejected add                                                        #
# ------------------------------------------------------------------ #

def test_post_missing_required_fields_is_rejected(client):
    _login(client, DEMO)
    resp = client.post(
        "/expenses/add",
        data={"amount": "", "category": "", "spent_on": ""},
    )
    assert resp.status_code == 200
    assert b"are required" in resp.data
    assert len(_expenses("demo@example.com")) == 0


def test_post_non_numeric_amount_is_rejected(client):
    _login(client, DEMO)
    resp = client.post(
        "/expenses/add",
        data={"amount": "abc", "category": "Coffee", "spent_on": "2026-09-08"},
    )
    assert resp.status_code == 200
    assert b"must be a number" in resp.data
    assert len(_expenses("demo@example.com")) == 0


def test_post_negative_amount_is_rejected(client):
    _login(client, DEMO)
    resp = client.post(
        "/expenses/add",
        data={"amount": "-5", "category": "Coffee", "spent_on": "2026-09-08"},
    )
    assert resp.status_code == 200
    assert b"cannot be negative" in resp.data
    assert len(_expenses("demo@example.com")) == 0


def test_post_bad_date_is_rejected(client):
    _login(client, DEMO)
    resp = client.post(
        "/expenses/add",
        data={"amount": "5", "category": "Coffee", "spent_on": "08-09-2026"},
    )
    assert resp.status_code == 200
    assert b"YYYY-MM-DD" in resp.data
    assert len(_expenses("demo@example.com")) == 0


def test_rejected_add_preserves_entered_values(client):
    _login(client, DEMO)
    resp = client.post(
        "/expenses/add",
        data={
            "amount": "-5",
            "category": "Dining",
            "description": "Lunch",
            "spent_on": "2026-09-06",
        },
    )
    assert b'value="-5"' in resp.data
    assert b'value="Dining"' in resp.data
    assert b'value="Lunch"' in resp.data
