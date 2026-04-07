"""
admin/routes.py - Owner admin panel for Sunny Cafe Bot.
Protected by HTTP Basic Auth (ADMIN_USER / ADMIN_PASSWORD env vars).
"""

import functools
import os

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, Response)

import db

admin_bp = Blueprint("admin", __name__, template_folder="templates",
                     url_prefix="/admin")

ADMIN_USER     = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")


# ── Basic Auth ────────────────────────────────────────────────────────────────

def _check_auth(username: str, password: str) -> bool:
    return username == ADMIN_USER and password == ADMIN_PASSWORD


def require_auth(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not _check_auth(auth.username, auth.password):
            return Response(
                "Authentication required.",
                401,
                {"WWW-Authenticate": 'Basic realm="Sunny Cafe Admin"'},
            )
        return f(*args, **kwargs)
    return decorated


# ── Dashboard ─────────────────────────────────────────────────────────────────

@admin_bp.route("/")
@require_auth
def dashboard():
    today  = db.get_today_orders()
    counts = {s: sum(1 for o in today if o["status"] == s)
              for s in ("pending", "ready", "done", "cancelled")}
    return render_template("admin/dashboard.html", orders=today, counts=counts)


# ── Menu ──────────────────────────────────────────────────────────────────────

@admin_bp.route("/menu")
@require_auth
def menu():
    categories = db.get_categories(available_only=False)
    items_by_cat = {cat["id"]: db.get_items(cat["id"], available_only=False)
                    for cat in categories}
    return render_template("admin/menu.html",
                           categories=categories, items_by_cat=items_by_cat)


@admin_bp.route("/menu/category/add", methods=["POST"])
@require_auth
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
@require_auth
def toggle_category(cat_id):
    cat = db.get_category(cat_id)
    if cat:
        db.update_category(cat_id, available=not cat["available"])
    return redirect(url_for("admin.menu"))


@admin_bp.route("/menu/category/<int:cat_id>/delete", methods=["POST"])
@require_auth
def delete_category(cat_id):
    db.delete_category(cat_id)
    flash("Category deleted.", "warning")
    return redirect(url_for("admin.menu"))


@admin_bp.route("/menu/item/add", methods=["POST"])
@require_auth
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
@require_auth
def toggle_item(item_id):
    item = db.get_item(item_id)
    if item:
        db.update_item(item_id, available=not item["available"])
    return redirect(url_for("admin.menu"))


@admin_bp.route("/menu/item/<int:item_id>/edit", methods=["POST"])
@require_auth
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
@require_auth
def delete_item(item_id):
    db.delete_item(item_id)
    flash("Item deleted.", "warning")
    return redirect(url_for("admin.menu"))


# ── Discounts ─────────────────────────────────────────────────────────────────

@admin_bp.route("/discounts")
@require_auth
def discounts():
    return render_template("admin/discounts.html",
                           discounts=db.get_all_discounts())


@admin_bp.route("/discounts/add", methods=["POST"])
@require_auth
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
@require_auth
def toggle_discount(discount_id):
    discounts_list = db.get_all_discounts()
    d = next((x for x in discounts_list if x["id"] == discount_id), None)
    if d:
        db.update_discount(discount_id, active=not d["active"])
    return redirect(url_for("admin.discounts"))


@admin_bp.route("/discounts/<int:discount_id>/delete", methods=["POST"])
@require_auth
def delete_discount(discount_id):
    db.delete_discount(discount_id)
    flash("Discount deleted.", "warning")
    return redirect(url_for("admin.discounts"))


# ── Posts ─────────────────────────────────────────────────────────────────────

@admin_bp.route("/posts")
@require_auth
def posts():
    return render_template("admin/posts.html", posts=db.get_all_posts())


@admin_bp.route("/posts/add", methods=["POST"])
@require_auth
def add_post():
    db.create_post(
        title=request.form.get("title") or None,
        body=request.form["body"],
        active="active" in request.form,
    )
    flash("Post published.", "success")
    return redirect(url_for("admin.posts"))


@admin_bp.route("/posts/<int:post_id>/toggle", methods=["POST"])
@require_auth
def toggle_post(post_id):
    all_posts = db.get_all_posts()
    p = next((x for x in all_posts if x["id"] == post_id), None)
    if p:
        db.update_post(post_id, active=not p["active"])
    return redirect(url_for("admin.posts"))


@admin_bp.route("/posts/<int:post_id>/delete", methods=["POST"])
@require_auth
def delete_post(post_id):
    db.delete_post(post_id)
    flash("Post deleted.", "warning")
    return redirect(url_for("admin.posts"))


# ── Store info ────────────────────────────────────────────────────────────────

@admin_bp.route("/store")
@require_auth
def store():
    return render_template("admin/store.html", info=db.get_store_info())


@admin_bp.route("/store/save", methods=["POST"])
@require_auth
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
    order_list = db.get_orders(status=status_filter, limit=100)
    # Attach items to each order so the template can render them
    for o in order_list:
        o["items"] = db.get_order_items(o["id"])
    return render_template("admin/orders.html",
                           orders=order_list, status_filter=status_filter)


@admin_bp.route("/orders/<int:order_id>/status", methods=["POST"])
@require_auth
def update_order_status(order_id):
    db.update_order_status(order_id, request.form["status"])
    return redirect(request.referrer or url_for("admin.orders"))
