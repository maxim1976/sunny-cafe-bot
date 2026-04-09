"""
admin/routes.py - Owner admin panel for Sunny Cafe Bot.
Session-based auth with role support: owner (full access) / staff (orders only).
"""

import functools
import os

import bcrypt
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
)

import db

admin_bp = Blueprint(
    "admin", __name__, template_folder="templates", url_prefix="/admin"
)


# ── Auth helpers ──────────────────────────────────────────────────────────────


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _seed_owner() -> None:
    """Create first owner account from env vars if no admin users exist."""
    if db.admin_user_exists():
        return
    username = os.environ.get("ADMIN_USER")
    password = os.environ.get("ADMIN_PASSWORD")
    if username and password:
        db.create_admin_user(username, _hash_password(password), "owner")


def require_auth(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return decorated


def require_owner(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin.login"))
        if session.get("admin_role") != "owner":
            flash("Owner access required.", "warning")
            return redirect(url_for("admin.dashboard"))
        return f(*args, **kwargs)
    return decorated


# ── Login / Logout ────────────────────────────────────────────────────────────


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    _seed_owner()
    if session.get("admin_id"):
        return redirect(url_for("admin.dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.get_admin_user(username)
        if user and _check_password(password, user["password_hash"]):
            session["admin_id"] = user["id"]
            session["admin_username"] = user["username"]
            session["admin_role"] = user["role"]
            return redirect(url_for("admin.dashboard"))
        flash("Invalid username or password.", "warning")
    return render_template("admin/login.html")


@admin_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


# ── Dashboard ─────────────────────────────────────────────────────────────────


@admin_bp.route("/")
@require_auth
def dashboard():
    today = db.get_today_orders()
    counts = {
        s: sum(1 for o in today if o["status"] == s)
        for s in ("pending", "ready", "done", "cancelled")
    }
    return render_template("admin/dashboard.html", orders=today, counts=counts)


# ── Menu ──────────────────────────────────────────────────────────────────────


@admin_bp.route("/menu")
@require_owner
def menu():
    categories = db.get_categories(available_only=False)
    items_by_cat = {
        cat["id"]: db.get_items(cat["id"], available_only=False) for cat in categories
    }
    return render_template(
        "admin/menu.html", categories=categories, items_by_cat=items_by_cat
    )


@admin_bp.route("/menu/category/add", methods=["POST"])
@require_owner
def add_category():
    db.create_category(
        name_en=request.form["name_en"],
        name_zh=request.form["name_zh"],
        emoji=request.form.get("emoji", "•"),
        image_file=request.form.get("image_file") or None,
        sort_order=int(request.form.get("sort_order", 0)),
    )
    flash("Category added.", "success")
    return redirect(url_for("admin.menu"))


@admin_bp.route("/menu/category/<int:cat_id>/toggle", methods=["POST"])
@require_owner
def toggle_category(cat_id):
    cat = db.get_category(cat_id)
    if cat:
        db.update_category(cat_id, available=not cat["available"])
    return redirect(url_for("admin.menu"))


@admin_bp.route("/menu/category/<int:cat_id>/delete", methods=["POST"])
@require_owner
def delete_category(cat_id):
    db.delete_category(cat_id)
    flash("Category deleted.", "warning")
    return redirect(url_for("admin.menu"))


@admin_bp.route("/menu/item/add", methods=["POST"])
@require_owner
def add_item():
    db.create_item(
        category_id=int(request.form["category_id"]),
        name_en=request.form["name_en"],
        name_zh=request.form["name_zh"],
        price=int(request.form["price"]),
        sort_order=int(request.form.get("sort_order", 0)),
    )
    flash("Item added.", "success")
    return redirect(url_for("admin.menu"))


@admin_bp.route("/menu/item/<int:item_id>/toggle", methods=["POST"])
@require_owner
def toggle_item(item_id):
    item = db.get_item(item_id)
    if item:
        db.update_item(item_id, available=not item["available"])
    return redirect(url_for("admin.menu"))


@admin_bp.route("/menu/item/<int:item_id>/edit", methods=["POST"])
@require_owner
def edit_item(item_id):
    db.update_item(
        item_id,
        name_en=request.form["name_en"],
        name_zh=request.form["name_zh"],
        price=int(request.form["price"]),
    )
    flash("Item updated.", "success")
    return redirect(url_for("admin.menu"))


@admin_bp.route("/menu/item/<int:item_id>/delete", methods=["POST"])
@require_owner
def delete_item(item_id):
    db.delete_item(item_id)
    flash("Item deleted.", "warning")
    return redirect(url_for("admin.menu"))


# ── Discounts ─────────────────────────────────────────────────────────────────


@admin_bp.route("/discounts")
@require_owner
def discounts():
    return render_template("admin/discounts.html", discounts=db.get_all_discounts())


@admin_bp.route("/discounts/add", methods=["POST"])
@require_owner
def add_discount():
    expires = request.form.get("expires_at") or None
    db.create_discount(
        name=request.form["name"],
        type_=request.form["type"],
        value=int(request.form["value"]),
        expires_at=expires,
    )
    flash("Discount created.", "success")
    return redirect(url_for("admin.discounts"))


@admin_bp.route("/discounts/<int:discount_id>/toggle", methods=["POST"])
@require_owner
def toggle_discount(discount_id):
    discounts_list = db.get_all_discounts()
    d = next((x for x in discounts_list if x["id"] == discount_id), None)
    if d:
        db.update_discount(discount_id, active=not d["active"])
    return redirect(url_for("admin.discounts"))


@admin_bp.route("/discounts/<int:discount_id>/delete", methods=["POST"])
@require_owner
def delete_discount(discount_id):
    db.delete_discount(discount_id)
    flash("Discount deleted.", "warning")
    return redirect(url_for("admin.discounts"))


# ── Posts ─────────────────────────────────────────────────────────────────────


@admin_bp.route("/posts")
@require_owner
def posts():
    return render_template("admin/posts.html", posts=db.get_all_posts())


@admin_bp.route("/posts/add", methods=["POST"])
@require_owner
def add_post():
    db.create_post(
        title=request.form.get("title") or None,
        body=request.form["body"],
        active="active" in request.form,
    )
    flash("Post published.", "success")
    return redirect(url_for("admin.posts"))


@admin_bp.route("/posts/<int:post_id>/toggle", methods=["POST"])
@require_owner
def toggle_post(post_id):
    all_posts = db.get_all_posts()
    p = next((x for x in all_posts if x["id"] == post_id), None)
    if p:
        db.update_post(post_id, active=not p["active"])
    return redirect(url_for("admin.posts"))


@admin_bp.route("/posts/<int:post_id>/delete", methods=["POST"])
@require_owner
def delete_post(post_id):
    db.delete_post(post_id)
    flash("Post deleted.", "warning")
    return redirect(url_for("admin.posts"))


# ── Store info ────────────────────────────────────────────────────────────────


@admin_bp.route("/store")
@require_owner
def store():
    return render_template("admin/store.html", info=db.get_store_info())


@admin_bp.route("/store/save", methods=["POST"])
@require_owner
def save_store():
    data = {k: v for k, v in request.form.items() if k != "csrf_token"}
    db.set_store_info_bulk(data)
    flash("Store info saved.", "success")
    return redirect(url_for("admin.store"))


# ── Orders ────────────────────────────────────────────────────────────────────


@admin_bp.route("/orders")
@require_auth
def orders():
    status_filter = request.args.get("status") or None
    order_list = [dict(o) for o in db.get_orders(status=status_filter, limit=100)]
    for o in order_list:
        o["order_items"] = db.get_order_items(o["id"])
    return render_template(
        "admin/orders.html", orders=order_list, status_filter=status_filter
    )


@admin_bp.route("/orders/<int:order_id>/status", methods=["POST"])
@require_auth
def update_order_status(order_id):
    db.update_order_status(order_id, request.form["status"])
    return redirect(request.referrer or url_for("admin.orders"))


# ── Staff management (owner only) ─────────────────────────────────────────────


@admin_bp.route("/staff")
@require_owner
def staff():
    users = db.get_all_admin_users()
    return render_template("admin/staff.html", users=users)


@admin_bp.route("/staff/add", methods=["POST"])
@require_owner
def add_staff():
    username = request.form["username"].strip()
    password = request.form["password"]
    role = request.form["role"]
    if db.get_admin_user(username):
        flash("Username already exists.", "warning")
        return redirect(url_for("admin.staff"))
    db.create_admin_user(username, _hash_password(password), role)
    flash(f"Account '{username}' created.", "success")
    return redirect(url_for("admin.staff"))


@admin_bp.route("/staff/<int:user_id>/toggle", methods=["POST"])
@require_owner
def toggle_staff(user_id):
    if user_id == session.get("admin_id"):
        flash("Cannot deactivate your own account.", "warning")
        return redirect(url_for("admin.staff"))
    user = db.get_admin_user_by_id(user_id)
    if user:
        db.update_admin_user(user_id, active=not user["active"])
    return redirect(url_for("admin.staff"))


@admin_bp.route("/staff/<int:user_id>/delete", methods=["POST"])
@require_owner
def delete_staff(user_id):
    if user_id == session.get("admin_id"):
        flash("Cannot delete your own account.", "warning")
        return redirect(url_for("admin.staff"))
    db.delete_admin_user(user_id)
    flash("Account deleted.", "warning")
    return redirect(url_for("admin.staff"))


@admin_bp.route("/staff/<int:user_id>/reset-password", methods=["POST"])
@require_owner
def reset_password(user_id):
    new_password = request.form["password"]
    db.update_admin_user(user_id, password_hash=_hash_password(new_password))
    flash("Password updated.", "success")
    return redirect(url_for("admin.staff"))
