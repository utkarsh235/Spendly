import math
import os
import sqlite3
from datetime import date, datetime
from functools import wraps

from flask import (
    Flask,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from database import db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
db.init_app(app)

MIN_PASSWORD_LENGTH = 8

# How many expenses the dashboard ledger shows per page.
PER_PAGE = 10


# ------------------------------------------------------------------ #
# Auth helpers                                                        #
# ------------------------------------------------------------------ #

def login_required(view):
    """Redirect anonymous visitors to the login page."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_current_user():
    """Expose ``current_user`` to every template (None when logged out)."""
    if "user_id" in session:
        return {
            "current_user": {
                "id": session["user_id"],
                "name": session.get("user_name"),
            }
        }
    return {"current_user": None}


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("landing.html")


@app.route("/dashboard")
@login_required
def dashboard():
    conn = db.get_db()
    user_id = session["user_id"]

    count = conn.execute(
        "SELECT COUNT(*) AS n FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()["n"]
    total_pages = max(1, math.ceil(count / PER_PAGE))

    page = request.args.get("page", 1, type=int) or 1
    page = max(1, min(page, total_pages))
    offset = (page - 1) * PER_PAGE

    # Newest entry first. Sorting the visible page by a column is done
    # client-side (see static/js/main.js); the server only paginates.
    expenses = conn.execute(
        "SELECT id, amount, category, description, spent_on "
        "FROM expenses WHERE user_id = ? "
        "ORDER BY id DESC LIMIT ? OFFSET ?",
        (user_id, PER_PAGE, offset),
    ).fetchall()

    # The footer total is the whole account, not just the visible page.
    total = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS s FROM expenses WHERE user_id = ?",
        (user_id,),
    ).fetchone()["s"]

    return render_template(
        "dashboard.html",
        expenses=expenses,
        total=total,
        count=count,
        page=page,
        total_pages=total_pages,
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    error = None
    if not name or not email or not password:
        error = "All fields are required."
    elif len(password) < MIN_PASSWORD_LENGTH:
        error = f"Password must be at least {MIN_PASSWORD_LENGTH} characters."

    conn = db.get_db()
    if error is None:
        existing = conn.execute(
            "SELECT 1 FROM users WHERE email = ?", (email,)
        ).fetchone()
        if existing:
            error = "An account with that email already exists."

    if error is not None:
        return render_template("register.html", error=error, name=name, email=email)

    try:
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # Lost a race on the unique email between the check above and the insert.
        return render_template(
            "register.html",
            error="An account with that email already exists.",
            name=name,
            email=email,
        )

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    conn = db.get_db()
    user = conn.execute(
        "SELECT id, name, password_hash FROM users WHERE email = ?", (email,)
    ).fetchone()

    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template(
            "login.html", error="Invalid email or password.", email=email
        )

    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("dashboard"))


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if request.method == "GET":
        return render_template("reset_password.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    error = None
    if not email or not password:
        error = "All fields are required."
    elif len(password) < MIN_PASSWORD_LENGTH:
        error = f"Password must be at least {MIN_PASSWORD_LENGTH} characters."

    conn = db.get_db()
    if error is None:
        user = conn.execute(
            "SELECT 1 FROM users WHERE email = ?", (email,)
        ).fetchone()
        if user is None:
            error = "No account found with that email."

    if error is not None:
        return render_template("reset_password.html", error=error, email=email)

    conn.execute(
        "UPDATE users SET password_hash = ? WHERE email = ?",
        (generate_password_hash(password), email),
    )
    conn.commit()

    return redirect(url_for("login"))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    return "Profile page — coming in Step 4"


EXPENSE_CATEGORIES = [
    "Rent", "Groceries", "Transport", "Dining", "Utilities",
    "Shopping", "Entertainment", "Health", "Coffee", "Other",
]


@app.route("/expenses/add", methods=["GET", "POST"])
@login_required
def add_expense():
    if request.method == "GET":
        return render_template(
            "add_expense.html",
            categories=EXPENSE_CATEGORIES,
            spent_on=date.today().isoformat(),
        )

    amount_raw = request.form.get("amount", "").strip()
    category = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()
    spent_on = request.form.get("spent_on", "").strip()

    error = None
    amount = None
    if not amount_raw or not category or not spent_on:
        error = "Amount, category and date are required."
    else:
        try:
            amount = float(amount_raw)
        except ValueError:
            error = "Amount must be a number."
        else:
            if amount < 0:
                error = "Amount cannot be negative."
        if error is None:
            try:
                datetime.strptime(spent_on, "%Y-%m-%d")
            except ValueError:
                error = "Date must be in YYYY-MM-DD format."

    if error is not None:
        return render_template(
            "add_expense.html",
            error=error,
            categories=EXPENSE_CATEGORIES,
            amount=amount_raw,
            category=category,
            description=description,
            spent_on=spent_on,
        )

    conn = db.get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, description, spent_on) "
        "VALUES (?, ?, ?, ?, ?)",
        (session["user_id"], amount, category, description or None, spent_on),
    )
    conn.commit()

    return redirect(url_for("dashboard"))


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
