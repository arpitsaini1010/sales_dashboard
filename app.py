"""
Sales Analytics Dashboard - Backend
-----------------------------------
Flask backend that:
  * handles user registration / login / logout (SQLite + hashed passwords + sessions)
  * protects the dashboard page and every /api/* data route behind login
  * reads the sales CSV with pandas and serves KPI numbers, table rows and
    matplotlib/seaborn charts to the front-end

Run:
    pip install -r requirements.txt
    python app.py
Open:
    http://127.0.0.1:5000
"""

import base64
import io
import os
import re
import sqlite3
import tempfile
import threading
from datetime import datetime
from functools import wraps

# Ensure matplotlib uses a writable temp directory for config/font cache across platforms (Windows/Linux/Render)
os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "matplotlib_cache"))

import matplotlib 
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns
from flask import (Flask, g, jsonify, redirect, request, send_from_directory,
                   session)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data.csv")
DB_PATH = os.path.join(BASE_DIR, "users.db")
PAGES_DIR = os.path.join(BASE_DIR, "pages")

REQUIRED_COLUMNS = {
    "OrderID", "CustomerID", "OrderDate", "City", "Category", "ProductName",
    "PaymentMethod", "Status", "CustomerSegment", "Quantity", "Sales",
}

# static_url_path is NOT "" on purpose: the HTML pages are served through
# protected routes below, so nobody can open /index.html without logging in.
app = Flask(__name__, static_folder="static", static_url_path="/assets")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "sales-analytics-production-secret-key-2026")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# In-memory dataset - loaded once, replaced when a CSV is uploaded.
df = pd.read_csv(DATA_PATH)


# ================================================================ database ==
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS users (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   username TEXT NOT NULL UNIQUE,
                   email TEXT,
                   password_hash TEXT NOT NULL,
                   created_at TEXT NOT NULL
               )"""
        )
        db.commit()


init_db()


# ================================================================== auth ====
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Login required."}), 401
            return redirect("/login")
        return view(*args, **kwargs)
    return wrapped


USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@app.route("/login")
def login_page():
    if "user" in session:
        return redirect("/")
    return send_from_directory(PAGES_DIR, "login.html")


@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    if not USERNAME_RE.match(username):
        return jsonify({"error": "Username must be 3-30 characters: letters, numbers or underscore."}), 400
    if email and not EMAIL_RE.match(email):
        return jsonify({"error": "Please enter a valid email address."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    db = get_db()
    if db.execute("SELECT 1 FROM users WHERE lower(username)=lower(?)", (username,)).fetchone():
        return jsonify({"error": "That username is already taken."}), 409

    db.execute(
        "INSERT INTO users (username, email, password_hash, created_at) VALUES (?,?,?,?)",
        (username, email, generate_password_hash(password), datetime.utcnow().isoformat()),
    )
    db.commit()
    session.clear()
    session["user"] = username
    return jsonify({"ok": True, "username": username})


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    row = get_db().execute(
        "SELECT username, password_hash FROM users WHERE lower(username)=lower(?)", (username,)
    ).fetchone()
    # Same message for "no such user" and "wrong password" (don't leak which one).
    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Incorrect username or password."}), 401

    session.clear()
    session["user"] = row["username"]
    return jsonify({"ok": True, "username": row["username"]})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/me")
@login_required
def api_me():
    return jsonify({"username": session["user"]})


# ================================================================== pages ====
@app.route("/")
@login_required
def index():
    return send_from_directory(PAGES_DIR, "dashboard.html")


# ================================================================ styling ====
INK = "#132A2E"; PARCHMENT = "#F6F1E7"; TEAL = "#2E6E63"; BRASS = "#C1873A"
RUST = "#B24B3E"; OLIVE = "#7D8F6B"; SLATE = "#5C6B6A"; LINE = "#E4DCC9"
PALETTE = [TEAL, BRASS, RUST, OLIVE, "#8C6E4F", "#4E7A8C", "#9C7AA6", "#C4A35A", "#4B6B94", "#5F8D7B"]

plt.rcParams.update({
    "figure.facecolor": PARCHMENT, "axes.facecolor": "#FFFFFF", "axes.edgecolor": LINE,
    "axes.labelcolor": INK, "text.color": INK, "xtick.color": SLATE, "ytick.color": SLATE,
    "font.family": "DejaVu Sans", "font.size": 11, "axes.titlesize": 13, "axes.titleweight": "bold",
    "grid.color": LINE, "axes.grid": True, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
})


def k_fmt(x, pos=None):
    if x >= 1e6:
        return f"{x/1e6:.1f}M"
    if x >= 1e3:
        return f"{x/1e3:.0f}K"
    return f"{x:.0f}"


def fig_to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=PARCHMENT)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


# ============================================================== data utils ===
def filter_by_city(data, city):
    if city and city != "All" and "City" in data.columns:
        return data[data["City"] == city]
    return data


def completed_only(data):
    return data[data["Status"] == "Completed"]


# ================================================================== API ======
@app.route("/api/cities")
@login_required
def api_cities():
    cities = sorted(df["City"].dropna().unique().tolist())
    return jsonify(["All"] + cities)


@app.route("/api/summary")
@login_required
def api_summary():
    city = request.args.get("city", "All")
    sub = filter_by_city(df, city)
    completed = completed_only(sub)

    total_revenue = float(completed["Sales"].sum())
    total_orders = int(len(sub))
    completed_orders = int(len(completed))
    unique_customers = int(sub["CustomerID"].nunique())
    avg_order_value = total_revenue / completed_orders if completed_orders else 0.0
    completion_rate = (completed_orders / total_orders * 100) if total_orders else 0.0

    status_counts = {str(k): int(v) for k, v in sub["Status"].value_counts().items()}
    date_range = None
    dates = sub["OrderDate"].dropna()
    if len(dates):
        date_range = [str(dates.min()), str(dates.max())]

    top_products = (
        completed.groupby("ProductName")["Sales"].sum()
        .sort_values(ascending=False).head(8)
    )

    return jsonify({
        "totalRevenue": round(total_revenue, 2),
        "totalOrders": total_orders,
        "completedOrders": completed_orders,
        "uniqueCustomers": unique_customers,
        "avgOrderValue": round(avg_order_value, 2),
        "completionRate": round(completion_rate, 1),
        "statusCounts": status_counts,
        "dateRange": date_range,
        "topProducts": [[str(k), round(float(v), 2)] for k, v in top_products.items()],
    })


@app.route("/api/table")
@login_required
def api_table():
    city = request.args.get("city", "All")
    sub = filter_by_city(df, city)
    cols = ["OrderID", "OrderDate", "City", "Category", "ProductName",
            "CustomerSegment", "PaymentMethod", "Status", "Quantity", "Sales"]
    cols = [c for c in cols if c in sub.columns]
    sample = sub.head(15)[cols].astype(object).where(sub.head(15)[cols].notna(), None)
    return jsonify({"rows": sample.to_dict(orient="records"), "total": int(len(sub))})


CHART_LOCK = threading.Lock()      # matplotlib's pyplot is not thread-safe
CHART_CACHE = {}                   # (dataset_version, city) -> charts dict
DATASET_VERSION = 0                # bumped on every CSV upload


def build_charts(sub, label, selected_city="All"):
    """Draw every dashboard chart for the given rows. `label` (city name or
    'All cities') is written into each chart title so it is obvious the chart
    follows the city filter."""
    completed = completed_only(sub)
    charts = {}

    if len(completed):
        monthly = completed.copy()
        monthly["OrderDate"] = pd.to_datetime(monthly["OrderDate"], errors="coerce")
        monthly = monthly.dropna(subset=["OrderDate"]).set_index("OrderDate").resample("ME")["Sales"].sum()
        fig, ax = plt.subplots(figsize=(9, 3.6))
        ax.plot(monthly.index, monthly.values, color=TEAL, linewidth=2.2, marker="o", markersize=3.5)
        ax.fill_between(monthly.index, monthly.values, color=TEAL, alpha=0.08)
        ax.set_title(f"Revenue Trend \u2014 {label}")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(k_fmt))
        fig.autofmt_xdate()
        charts["revenueTrend"] = fig_to_b64(fig)

    # City chart: always compares ALL cities; the selected city is highlighted.
    city_rev = completed_only(df).groupby("City")["Sales"].sum().sort_values(ascending=False).head(10)
    if len(city_rev):
        fig, ax = plt.subplots(figsize=(6.5, 3.8))
        if selected_city != "All" and selected_city in city_rev.index:
            colors = [TEAL if c == selected_city else "#CFC7B3" for c in city_rev.index]
            title = f"City Ranking \u2014 {selected_city} highlighted"
        else:
            colors = PALETTE[:len(city_rev)]
            title = "Revenue by City \u2014 All cities"
        sns.barplot(x=city_rev.values, y=city_rev.index, ax=ax, palette=colors,
                    hue=city_rev.index, legend=False)
        ax.set_title(title)
        ax.set_xlabel("Revenue"); ax.set_ylabel("")
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(k_fmt))
        charts["revenueByCity"] = fig_to_b64(fig)

    cat_rev = completed.groupby("Category")["Sales"].sum().sort_values(ascending=False)
    if len(cat_rev):
        fig, ax = plt.subplots(figsize=(6.5, 3.6))
        sns.barplot(x=cat_rev.values, y=cat_rev.index, ax=ax, palette=PALETTE[:len(cat_rev)],
                    hue=cat_rev.index, legend=False)
        ax.set_title(f"Revenue by Category \u2014 {label}")
        ax.set_xlabel("Revenue"); ax.set_ylabel("")
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(k_fmt))
        charts["revenueByCategory"] = fig_to_b64(fig)

    pay = sub["PaymentMethod"].value_counts()
    if len(pay):
        fig, ax = plt.subplots(figsize=(4.6, 4.6))
        ax.pie(pay.values, labels=pay.index, autopct="%1.1f%%", colors=PALETTE,
               wedgeprops={"edgecolor": PARCHMENT, "linewidth": 2}, textprops={"color": INK})
        ax.set_title(f"Payment Method \u2014 {label}", fontsize=11)
        charts["paymentMethod"] = fig_to_b64(fig)

    seg = completed.groupby("CustomerSegment")["Sales"].sum().sort_values(ascending=False)
    if len(seg):
        fig, ax = plt.subplots(figsize=(4.6, 3.8))
        sns.barplot(x=seg.index, y=seg.values, ax=ax, palette=[OLIVE, "#8C6E4F", RUST][:len(seg)],
                    hue=seg.index, legend=False)
        ax.set_title(f"Customer Segment \u2014 {label}", fontsize=11)
        ax.set_ylabel("Revenue"); ax.set_xlabel("")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(k_fmt))
        charts["customerSegment"] = fig_to_b64(fig)

    status = sub["Status"].value_counts()
    if len(status):
        color_map = {"Completed": TEAL, "Cancelled": RUST, "Returned": BRASS}
        fig, ax = plt.subplots(figsize=(4.6, 4.6))
        ax.pie(status.values, labels=status.index, autopct="%1.1f%%",
               colors=[color_map.get(s, SLATE) for s in status.index],
               wedgeprops={"edgecolor": PARCHMENT, "linewidth": 2}, textprops={"color": INK})
        ax.set_title(f"Order Status \u2014 {label}", fontsize=11)
        charts["orderStatus"] = fig_to_b64(fig)

    return charts


@app.route("/api/charts")
@login_required
def api_charts():
    """Charts are drawn server-side (matplotlib/seaborn) and returned as base64
    PNGs, so the browser needs no charting library or internet connection.
    Results are cached per city, so switching back to a city is instant."""
    city = request.args.get("city", "All")
    key = (DATASET_VERSION, city)
    if key in CHART_CACHE:
        return jsonify(CHART_CACHE[key])

    with CHART_LOCK:                       # one chart job at a time
        if key not in CHART_CACHE:
            sub = filter_by_city(df, city)
            label = "All cities" if city == "All" else city
            CHART_CACHE[key] = build_charts(sub, label, city)
    return jsonify(CHART_CACHE[key])


@app.route("/api/upload", methods=["POST"])
@login_required
def api_upload():
    """Replace the in-memory dataset with an uploaded CSV (same columns)."""
    global df, DATASET_VERSION
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file received."}), 400
    try:
        new_df = pd.read_csv(file)
    except Exception:
        return jsonify({"error": "Could not read that file as CSV."}), 400

    missing = REQUIRED_COLUMNS - set(new_df.columns)
    if missing:
        return jsonify({"error": "Missing required columns: " + ", ".join(sorted(missing))}), 400

    df = new_df
    DATASET_VERSION += 1
    CHART_CACHE.clear()
    return jsonify({"ok": True, "rows": int(len(df))})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
