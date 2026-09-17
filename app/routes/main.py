"""Pages principales : accueil, dashboard, produits, détail et confirmation."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.models import Product, Purchase, Transaction, db
from app.utils import to_dec

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    """Page d'accueil publique (landing) présentant l'univers FANTA."""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    products = Product.query.filter_by(active=True).order_by(Product.sort_order).limit(4).all()
    return render_template("home.html", products=products)


@main_bp.route("/dashboard")
@login_required
def dashboard():
    user = current_user
    active_purchases = Purchase.query.filter_by(user_id=user.id, status="active").all()
    recent = (
        Transaction.query.filter_by(user_id=user.id)
        .order_by(Transaction.created_at.desc())
        .limit(6)
        .all()
    )
    products = Product.query.filter_by(active=True).order_by(Product.sort_order).all()
    featured = products[0] if products else None

    stats = {
        "balance": to_dec(user.balance),
        "income": to_dec(user.total_income),
        "commission": to_dec(user.total_commission),
        "active_products": len(active_purchases),
    }
    return render_template(
        "dashboard.html",
        stats=stats,
        recent=recent,
        products=products,
        featured=featured,
        active_purchases=active_purchases,
    )


@main_bp.route("/produits")
@login_required
def products():
    items = Product.query.filter_by(active=True).order_by(Product.sort_order).all()
    return render_template("products.html", items=items)


@main_bp.route("/produit/<int:product_id>")
@login_required
def product_detail(product_id):
    product = db.get_or_404(Product, product_id)
    return render_template("product_detail.html", product=product)


@main_bp.route("/produit/<int:product_id>/confirmation", methods=["GET", "POST"])
@login_required
def product_confirm(product_id):
    product = db.get_or_404(Product, product_id)
    if not product.active:
        flash("Ce produit n'est plus disponible.", "error")
        return redirect(url_for("main.products"))

    if request.method == "POST":
        from app.services.finance_service import purchase_product
        try:
            purchase_product(current_user, product)
            db.session.commit()
        except ValueError as err:
            db.session.rollback()
            flash(str(err), "error")
            if "solde" in str(err).lower():
                return redirect(url_for("wallet.deposit"))
            return redirect(url_for("main.product_detail", product_id=product.id))

        flash(f"{product.name} activé avec succès !", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("product_confirm.html", product=product)
