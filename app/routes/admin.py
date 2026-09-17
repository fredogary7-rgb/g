"""Espace administrateur : supervision et gestion complète."""
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func, or_

from app.decorators import admin_required
from app.models import (
    AdminAction,
    Commission,
    Deposit,
    Product,
    Purchase,
    Transaction,
    User,
    Withdrawal,
    db,
)
from app.utils import money, to_dec

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _log(action, target_type, target_id=None, detail=None):
    db.session.add(AdminAction(
        admin_id=current_user.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    ))


@admin_bp.route("", methods=["GET"])
@admin_required
def dashboard():
    total_users = User.query.count()
    active_users = User.query.filter_by(is_banned=False).count()

    approved_deposits = Deposit.query.filter_by(status="approved")
    deposit_sum = db.session.query(func.coalesce(func.sum(Deposit.amount), 0)).filter_by(status="approved").scalar()

    withdrawals = Withdrawal.query
    withdrawal_sum = db.session.query(func.coalesce(func.sum(Withdrawal.amount), 0)).scalar()

    active_purchases = Purchase.query.filter_by(status="active").count()
    commission_sum = db.session.query(func.coalesce(func.sum(Commission.amount), 0)).filter_by(status="approved").scalar()

    stats = {
        "total_users": total_users,
        "active_users": active_users,
        "deposits_count": approved_deposits.count(),
        "deposits_sum": to_dec(deposit_sum),
        "withdrawals_count": withdrawals.count(),
        "withdrawals_sum": to_dec(withdrawal_sum),
        "active_purchases": active_purchases,
        "commissions_sum": to_dec(commission_sum),
    }

    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    pending_deposits = Deposit.query.filter_by(status="pending").order_by(Deposit.created_at.desc()).limit(5).all()
    pending_withdrawals = Withdrawal.query.filter_by(status="pending").order_by(Withdrawal.created_at.desc()).limit(5).all()

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_users=recent_users,
        pending_deposits=pending_deposits,
        pending_withdrawals=pending_withdrawals,
    )


@admin_bp.route("/users")
@admin_required
def users():
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)

    query = User.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            User.username.ilike(like),
            User.email.ilike(like),
            User.phone.ilike(like),
        ))

    pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template("admin/users.html", pagination=pagination, q=q)


@admin_bp.route("/users/<int:user_id>")
@admin_required
def user_detail(user_id):
    user = db.get_or_404(User, user_id)
    level1 = User.query.filter_by(referred_by=user.id).all()
    transactions = (
        Transaction.query.filter_by(user_id=user.id)
        .order_by(Transaction.created_at.desc()).limit(20).all()
    )
    purchases = Purchase.query.filter_by(user_id=user.id).order_by(Purchase.created_at.desc()).limit(20).all()
    deposits = Deposit.query.filter_by(user_id=user.id).order_by(Deposit.created_at.desc()).limit(10).all()
    withdrawals = Withdrawal.query.filter_by(user_id=user.id).order_by(Withdrawal.created_at.desc()).limit(10).all()
    return render_template(
        "admin/user_detail.html",
        user=user,
        level1=level1,
        transactions=transactions,
        purchases=purchases,
        deposits=deposits,
        withdrawals=withdrawals,
        countries=current_app.config.get("COUNTRIES", ["Burkina Faso"]),
    )


@admin_bp.route("/users/<int:user_id>/ban", methods=["POST"])
@admin_required
def ban_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.is_admin:
        flash("Impossible de bannir un administrateur.", "error")
    else:
        user.is_banned = True
        _log("ban_user", "user", user.id, user.username)
        db.session.commit()
        flash(f"Utilisateur {user.username} banni.", "success")
    return redirect(url_for("admin.user_detail", user_id=user.id))


@admin_bp.route("/users/<int:user_id>/unban", methods=["POST"])
@admin_required
def unban_user(user_id):
    user = db.get_or_404(User, user_id)
    user.is_banned = False
    _log("unban_user", "user", user.id, user.username)
    db.session.commit()
    flash(f"Utilisateur {user.username} débanni.", "success")
    return redirect(url_for("admin.user_detail", user_id=user.id))


@admin_bp.route("/users/<int:user_id>/edit", methods=["POST"])
@admin_required
def edit_user(user_id):
    user = db.get_or_404(User, user_id)
    username = (request.form.get("username") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    country = (request.form.get("country") or "").strip()

    if len(username) < 3:
        flash("Nom d'utilisateur trop court.", "error")
    elif User.query.filter(User.username == username, User.id != user.id).first():
        flash("Nom d'utilisateur déjà pris.", "error")
    else:
        user.username = username
        user.phone = phone or None
        user.country = country or "Burkina Faso"
        _log("edit_user", "user", user.id, f"{username} / {country}")
        db.session.commit()
        flash("Utilisateur mis à jour.", "success")

    return redirect(url_for("admin.user_detail", user_id=user.id))


@admin_bp.route("/users/<int:user_id>/credit", methods=["POST"])
@admin_required
def credit_user(user_id):
    user = db.get_or_404(User, user_id)
    try:
        amount = to_dec(request.form.get("amount") or 0)
    except Exception:
        amount = to_dec(0)

    if amount <= 0:
        flash("Montant invalide.", "error")
    else:
        from app.services.finance_service import admin_adjust_balance
        from app.services.notification_service import notify
        admin_adjust_balance(user, amount, description="Crédit administrateur")
        notify(user.id, "deposit", "Crédit reçu",
               f"Votre compte a été crédité de {int(amount):,} FCFA.", "/portefeuille")
        _log("credit_user", "user", user.id, f"{user.username} +{amount}")
        db.session.commit()
        flash(f"Compte crédité de {money(amount)}.", "success")

    return redirect(url_for("admin.user_detail", user_id=user.id))


@admin_bp.route("/users/<int:user_id>/debit", methods=["POST"])
@admin_required
def debit_user(user_id):
    user = db.get_or_404(User, user_id)
    try:
        amount = to_dec(request.form.get("amount") or 0)
    except Exception:
        amount = to_dec(0)

    if amount <= 0:
        flash("Montant invalide.", "error")
    else:
        from app.services.finance_service import admin_adjust_balance
        from app.services.notification_service import notify
        try:
            admin_adjust_balance(user, -amount, description="Débit administrateur")
        except ValueError as err:
            db.session.rollback()
            flash(str(err), "error")
            return redirect(url_for("admin.user_detail", user_id=user.id))
        notify(user.id, "deposit", "Débit effectué",
               f"Votre compte a été débité de {int(amount):,} FCFA.", "/portefeuille")
        _log("debit_user", "user", user.id, f"{user.username} -{amount}")
        db.session.commit()
        flash(f"Compte débité de {money(amount)}.", "success")

    return redirect(url_for("admin.user_detail", user_id=user.id))


@admin_bp.route("/users/<int:user_id>/toggle-admin", methods=["POST"])
@admin_required
def toggle_admin(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("Vous ne pouvez pas modifier votre propre rôle.", "error")
    else:
        user.is_admin = not user.is_admin
        _log("toggle_admin", "user", user.id, f"{user.username} -> admin={user.is_admin}")
        db.session.commit()
        if user.is_admin:
            flash(f"{user.username} est désormais administrateur.", "success")
        else:
            flash(f"{user.username} n'est plus administrateur.", "success")

    return redirect(url_for("admin.user_detail", user_id=user.id))


def _product_payload(form):
    """Extrait et valide les champs produit du formulaire."""
    errors = []
    name = (form.get("name") or "").strip()
    try:
        price = to_dec(form.get("price") or 0)
        daily = to_dec(form.get("daily_income") or 0)
        total = to_dec(form.get("total_income") or 0)
    except Exception:
        price = daily = total = to_dec(0)

    try:
        duration = int(form.get("duration") or 0)
    except ValueError:
        duration = 0

    if not name:
        errors.append("Le nom du produit est requis.")
    if price <= 0:
        errors.append("Le prix doit être supérieur à zéro.")
    if daily <= 0:
        errors.append("Le revenu quotidien doit être supérieur à zéro.")
    if total <= 0:
        errors.append("Le revenu total doit être supérieur à zéro.")
    if duration <= 0:
        errors.append("La durée doit être supérieure à zéro.")

    return errors, {
        "name": name,
        "price": price,
        "daily_income": daily,
        "total_income": total,
        "duration": duration,
        "image": (form.get("image") or "").strip(),
        "description": (form.get("description") or "").strip(),
        "sort_order": int(form.get("sort_order") or 0),
        "active": form.get("active") == "on",
    }


@admin_bp.route("/products")
@admin_required
def products():
    items = Product.query.order_by(Product.sort_order).all()
    return render_template("admin/products.html", items=items)


@admin_bp.route("/products/new", methods=["GET", "POST"])
@admin_required
def product_new():
    if request.method == "POST":
        errors, data = _product_payload(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            product = Product(**data)
            db.session.add(product)
            _log("create_product", "product", None, product.name)
            db.session.commit()
            flash(f"Produit {product.name} créé.", "success")
            return redirect(url_for("admin.products"))
    return render_template("admin/product_form.html", product=None)


@admin_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def product_edit(product_id):
    product = db.get_or_404(Product, product_id)
    if request.method == "POST":
        errors, data = _product_payload(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            for key, value in data.items():
                setattr(product, key, value)
            _log("edit_product", "product", product.id, product.name)
            db.session.commit()
            flash(f"Produit {product.name} mis à jour.", "success")
            return redirect(url_for("admin.products"))
    return render_template("admin/product_form.html", product=product)


@admin_bp.route("/products/<int:product_id>/toggle", methods=["POST"])
@admin_required
def product_toggle(product_id):
    product = db.get_or_404(Product, product_id)
    product.active = not product.active
    _log("toggle_product", "product", product.id, f"{product.name} -> {product.active}")
    db.session.commit()
    flash(f"Produit {product.name} {'activé' if product.active else 'désactivé'}.", "success")
    return redirect(url_for("admin.products"))


@admin_bp.route("/deposits")
@admin_required
def deposits():
    status = request.args.get("status", "")
    query = Deposit.query
    if status in ("pending", "approved", "rejected"):
        query = query.filter_by(status=status)
    items = query.order_by(Deposit.created_at.desc()).limit(200).all()
    return render_template("admin/deposits.html", items=items, status=status)


@admin_bp.route("/deposits/<int:deposit_id>/approve", methods=["POST"])
@admin_required
def deposit_approve(deposit_id):
    deposit = db.get_or_404(Deposit, deposit_id)
    note = (request.form.get("note") or "").strip() or None
    from app.services.finance_service import approve_deposit
    approve_deposit(deposit, note)
    _log("approve_deposit", "deposit", deposit.id, deposit.reference)
    db.session.commit()
    flash("Dépôt approuvé et crédité.", "success")
    return redirect(url_for("admin.deposits"))


@admin_bp.route("/deposits/<int:deposit_id>/reject", methods=["POST"])
@admin_required
def deposit_reject(deposit_id):
    deposit = db.get_or_404(Deposit, deposit_id)
    note = (request.form.get("note") or "").strip() or None
    from app.services.finance_service import reject_deposit
    reject_deposit(deposit, note)
    _log("reject_deposit", "deposit", deposit.id, deposit.reference)
    db.session.commit()
    flash("Dépôt rejeté.", "success")
    return redirect(url_for("admin.deposits"))


@admin_bp.route("/withdrawals")
@admin_required
def withdrawals():
    status = request.args.get("status", "")
    query = Withdrawal.query
    if status in ("pending", "approved", "rejected"):
        query = query.filter_by(status=status)
    items = query.order_by(Withdrawal.created_at.desc()).limit(200).all()
    return render_template("admin/withdrawals.html", items=items, status=status)


@admin_bp.route("/withdrawals/<int:withdrawal_id>/approve", methods=["POST"])
@admin_required
def withdrawal_approve(withdrawal_id):
    withdrawal = db.get_or_404(Withdrawal, withdrawal_id)
    note = (request.form.get("note") or "").strip() or None
    from app.services.withdrawal_service import approve_withdrawal
    approve_withdrawal(withdrawal, note)
    _log("approve_withdrawal", "withdrawal", withdrawal.id, withdrawal.reference)
    db.session.commit()
    flash("Retrait approuvé.", "success")
    return redirect(url_for("admin.withdrawals"))


@admin_bp.route("/withdrawals/<int:withdrawal_id>/reject", methods=["POST"])
@admin_required
def withdrawal_reject(withdrawal_id):
    withdrawal = db.get_or_404(Withdrawal, withdrawal_id)
    note = (request.form.get("note") or "").strip() or None
    from app.services.withdrawal_service import reject_withdrawal
    reject_withdrawal(withdrawal, note)
    _log("reject_withdrawal", "withdrawal", withdrawal.id, withdrawal.reference)
    db.session.commit()
    flash("Retrait rejeté et solde recrédité.", "success")
    return redirect(url_for("admin.withdrawals"))


@admin_bp.route("/commissions")
@admin_required
def commissions():
    level = request.args.get("level", type=int)
    query = Commission.query
    if level in (1, 2, 3):
        query = query.filter_by(level=level)
    items = query.order_by(Commission.created_at.desc()).limit(200).all()
    return render_template("admin/commissions.html", items=items, level=level)


@admin_bp.route("/commissions/<int:commission_id>/approve", methods=["POST"])
@admin_required
def commission_approve(commission_id):
    commission = db.get_or_404(Commission, commission_id)
    from app.services.referral_service import approve_commission
    approve_commission(commission)
    _log("approve_commission", "commission", commission.id, commission.reference)
    db.session.commit()
    flash("Commission approuvée et créditée.", "success")
    return redirect(url_for("admin.commissions"))


@admin_bp.route("/commissions/<int:commission_id>/cancel", methods=["POST"])
@admin_required
def commission_cancel(commission_id):
    commission = db.get_or_404(Commission, commission_id)
    from app.services.referral_service import cancel_commission
    cancel_commission(commission)
    _log("cancel_commission", "commission", commission.id, commission.reference)
    db.session.commit()
    flash("Commission annulée.", "success")
    return redirect(url_for("admin.commissions"))


@admin_bp.route("/transactions")
@admin_required
def transactions():
    page = request.args.get("page", 1, type=int)
    pagination = Transaction.query.order_by(Transaction.created_at.desc()).paginate(page=page, per_page=30, error_out=False)
    return render_template("admin/transactions.html", pagination=pagination)


@admin_bp.route("/actions")
@admin_required
def actions():
    items = AdminAction.query.order_by(AdminAction.created_at.desc()).limit(200).all()
    return render_template("admin/actions.html", items=items)



