"""Tests for the per-user dashboard, the auth gate, and session-aware chrome."""

from database import db as db_module

# Seeded by seed_db():
#   nitish@example.com / password123  -> 10 expenses
#   demo@example.com   / password123  -> 0 expenses
NITISH = ("nitish@example.com", "password123")
DEMO = ("demo@example.com", "password123")


def _login(client, creds):
    return client.post(
        "/login", data={"email": creds[0], "password": creds[1]}
    )


def _bulk_insert(email, count, amount=10.0, category="Misc", spent_on="2026-01-01"):
    """Insert ``count`` expenses straight into the DB for the given user.

    Faster than POSTing the add form ``count`` times, and lets a test build a
    dataset bigger than one page without depending on /expenses/add.
    """
    conn = db_module._connect()
    try:
        user_id = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()["id"]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, description, spent_on) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (user_id, amount, category, f"row {i:03d}", spent_on)
                for i in range(count)
            ],
        )
        conn.commit()
    finally:
        conn.close()


def _row_count(body):
    """How many expense rows the rendered ledger body contains."""
    return body.count('<td class="date">')


# ------------------------------------------------------------------ #
# Auth gate                                                           #
# ------------------------------------------------------------------ #

def test_dashboard_requires_login(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_login_redirects_to_dashboard(client):
    resp = _login(client, NITISH)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/dashboard")


# ------------------------------------------------------------------ #
# Per-user content                                                    #
# ------------------------------------------------------------------ #

def test_dashboard_greets_the_logged_in_user_by_name(client):
    _login(client, NITISH)
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert b"Nitish Kumar" in resp.data


def test_dashboard_shows_only_the_current_users_expenses(client):
    # Nitish has 10 seeded expenses; "October rent" is one of them.
    _login(client, NITISH)
    resp = client.get("/dashboard")
    assert b"October rent" in resp.data  # description now shows in the ledger table
    assert b"Rent" in resp.data
    assert b"10 expenses logged" in resp.data


# ------------------------------------------------------------------ #
# Expenses ledger (table below the Add expense / Log out buttons)     #
# ------------------------------------------------------------------ #

def test_ledger_lists_every_expense_for_the_user(client):
    _login(client, NITISH)
    body = client.get("/dashboard").data
    assert b"<table" in body
    # All 10 seeded descriptions appear as rows.
    for description in (
        b"October rent", b"Weekly shop", b"Metro card top-up", b"Movie ticket",
        b"Dinner with friends", b"Internet bill", b"New running shoes",
        b"Morning latte", b"Dentist appointment", b"Mid-week restock",
    ):
        assert description in body


def test_ledger_defaults_to_insertion_order_newest_first(client):
    # seed_db() inserts "October rent" first and "Mid-week restock" last, so by
    # insertion order (id DESC) the restock is at the top and the rent at the bottom.
    _login(client, NITISH)
    body = client.get("/dashboard").data.decode()
    assert body.index("Mid-week restock") < body.index("October rent")


def test_ledger_order_follows_insertion_not_spend_date(client):
    # DEMO starts empty. Add a future-dated row, then a past-dated row: the
    # past-dated one was inserted last, so it must render first.
    _login(client, DEMO)
    client.post("/expenses/add", data={
        "amount": "10", "category": "Dining",
        "description": "future dinner", "spent_on": "2099-12-31",
    })
    client.post("/expenses/add", data={
        "amount": "20", "category": "Coffee",
        "description": "old coffee", "spent_on": "2000-01-01",
    })
    body = client.get("/dashboard").data.decode()
    assert body.index("old coffee") < body.index("future dinner")


def test_ledger_headers_are_marked_up_for_client_side_sorting(client):
    # main.js reads data-type on each <th> to sort the visible page in place;
    # amount cells expose a raw numeric data-sort value so "₹1,200.00" sorts as 1200.
    # (The sort interaction itself is JS and is covered by a browser check, not here.)
    _login(client, NITISH)
    body = client.get("/dashboard").data
    assert b'data-type="date"' in body
    assert b'data-type="number"' in body
    assert body.count(b'data-type="text"') >= 2
    assert b"data-sort=" in body
    # No server-side sort params in the page any more.
    assert b"sort=amount" not in body
    assert b"?sort=" not in body


# ------------------------------------------------------------------ #
# Pagination                                                          #
# ------------------------------------------------------------------ #

def test_dashboard_shows_at_most_ten_rows_per_page(client):
    _bulk_insert("demo@example.com", 25)
    _login(client, DEMO)
    assert _row_count(client.get("/dashboard").data.decode()) == 10


def test_dashboard_second_and_last_pages_show_the_remainder(client):
    _bulk_insert("demo@example.com", 25)  # 10 + 10 + 5
    _login(client, DEMO)
    assert _row_count(client.get("/dashboard?page=2").data.decode()) == 10
    assert _row_count(client.get("/dashboard?page=3").data.decode()) == 5


def test_dashboard_pages_do_not_repeat_or_drop_rows(client):
    _bulk_insert("demo@example.com", 25)
    _login(client, DEMO)
    seen = set()
    for page in (1, 2, 3):
        body = client.get(f"/dashboard?page={page}").data.decode()
        rows = {line for line in body.splitlines() if "row 0" in line}
        assert not (seen & rows)  # no row appears on two pages
        seen |= rows
    assert len(seen) == 25


def test_dashboard_clamps_out_of_range_and_junk_page_values(client):
    _bulk_insert("demo@example.com", 25)
    _login(client, DEMO)
    for bad in ("999", "0", "-4", "notanumber", ""):
        assert client.get(f"/dashboard?page={bad}").status_code == 200
    # page past the end clamps to the last page (5 rows); page < 1 clamps to first
    assert _row_count(client.get("/dashboard?page=999").data.decode()) == 5
    assert _row_count(client.get("/dashboard?page=0").data.decode()) == 10


def test_pager_is_absent_for_a_single_page(client):
    _bulk_insert("demo@example.com", 10)  # exactly one page
    _login(client, DEMO)
    assert b'class="pager"' not in client.get("/dashboard").data


def test_pager_shows_zero_padded_numbers_and_marks_the_current_page(client):
    _bulk_insert("demo@example.com", 25)  # 3 pages
    _login(client, DEMO)
    body = client.get("/dashboard?page=2").data.decode()
    assert 'class="pager"' in body
    assert ">01<" in body and ">02<" in body and ">03<" in body
    assert ">04<" not in body  # only three pages
    assert 'aria-current="page"' in body


def test_grand_total_and_count_cover_every_page(client):
    _bulk_insert("demo@example.com", 25, amount=10.0)  # 25 * 10 = 250.00
    _login(client, DEMO)
    for page in (1, 2, 3):
        body = client.get(f"/dashboard?page={page}").data
        assert b"250.00" in body          # footer total is the whole account
        assert b"25 expenses logged" in body


def test_ledger_shows_a_total_row(client):
    _login(client, NITISH)
    body = client.get("/dashboard").data
    assert b"Total" in body
    # 1200 + 85.50 + 42 + 15.99 + 60 + 30.25 + 120 + 9.75 + 250 + 55.40
    assert b"1868.89" in body


def test_ledger_shows_empty_state_for_a_user_with_no_expenses(client):
    _login(client, DEMO)
    body = client.get("/dashboard").data
    assert b"<table" not in body
    assert b"No expenses logged yet" in body


def test_ledger_is_scoped_to_the_logged_in_user(client):
    _login(client, DEMO)
    body = client.get("/dashboard").data
    assert b"October rent" not in body
    assert b"Mid-week restock" not in body


def test_newly_added_expense_appears_first_regardless_of_its_date(client):
    _login(client, NITISH)
    client.post(
        "/expenses/add",
        data={
            "amount": "7.50",
            "category": "Coffee",
            "description": "back-dated latte",
            "spent_on": "2020-01-01",
        },
    )
    body = client.get("/dashboard").data.decode()
    # Old spent_on, but inserted last -> shown first.
    assert body.index("back-dated latte") < body.index("Mid-week restock")


def test_dashboard_is_empty_for_a_user_with_no_expenses(client):
    _login(client, DEMO)
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert b"haven't logged any expenses yet" in resp.data
    assert b"Rent" not in resp.data


def test_two_users_see_different_dashboards(client):
    _login(client, NITISH)
    nitish_view = client.get("/dashboard").data
    client.get("/logout")

    _login(client, DEMO)
    demo_view = client.get("/dashboard").data

    assert b"10 expenses logged" in nitish_view
    assert b"10 expenses logged" not in demo_view


# ------------------------------------------------------------------ #
# Landing redirect + session-aware navbar                             #
# ------------------------------------------------------------------ #

def test_landing_redirects_logged_in_user_to_dashboard(client):
    _login(client, NITISH)
    resp = client.get("/")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/dashboard")


def test_landing_is_public_for_anonymous_visitors(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Get started" in resp.data
    assert b"Sign in" in resp.data


def test_navbar_hides_auth_buttons_when_logged_in(client):
    _login(client, NITISH)
    resp = client.get("/dashboard")
    assert b"Log out" in resp.data
    assert b"Get started" not in resp.data
    assert b">Sign in<" not in resp.data


def test_navbar_shows_auth_buttons_when_logged_out(client):
    resp = client.get("/login")
    assert b"Get started" in resp.data
    assert b"Log out" not in resp.data
