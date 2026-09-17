"""Portefeuille : solde, dépôt, retrait et historique."""
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.models import Deposit, Purchase, Transaction, Withdrawal, db
from app.utils import to_dec

wallet_bp = Blueprint("wallet", __name__)

TYPE_LABELS = {
    "purchase": "Produits",
    "deposit": "Dépôts",
    "withdrawal": "Retraits",
    "income": "Revenus",
    "commission": "Commissions",
    "refund": "Remboursements",
}


@wallet_bp.route("/portefeuille")
@login_required
def overview():
    user = current_user
    active_count = Purchase.query.filter_by(user_id=user.id, status="active").count()
    data = {
        "balance": to_dec(user.balance),
        "total_deposit": to_dec(user.total_deposit),
        "income": to_dec(user.total_income),
        "commission": to_dec(user.total_commission),
        "active_products": active_count,
    }
    return render_template("wallet/overview.html", data=data)


@wallet_bp.route("/depot", methods=["GET", "POST"])
@login_required
def deposit():
    methods = current_app.config.get("PAYMENT_METHODS", [])
    if request.method == "POST":
        amount = (request.form.get("amount") or "").strip()
        method = (request.form.get("method") or "").strip()
        try:
            amount_dec = to_dec(amount)
        except Exception:
            amount_dec = to_dec(0)
        if amount_dec <= 0:
            flash("Veuillez saisir un montant valide.", "error")
        elif method not in methods:
            flash("Veuillez choisir une méthode de paiement.", "error")
        else:
            from app.services.payment_service import get_provider
            provider = get_provider()
            dep = provider.create_deposit(current_user, amount_dec, method)
            db.session.commit()
            flash(
                f"Dépôt de test enregistré (référence {dep.reference}). "
                "Il sera crédité après validation.",
                "success",
            )
            return redirect(url_for("wallet.history", type="deposit"))

    return render_template("wallet/deposit.html", methods=methods)


@wallet_bp.route("/retrait", methods=["GET", "POST"])
@login_required
def withdraw():
    methods = current_app.config.get("WITHDRAWAL_METHODS", [])
    if request.method == "POST":
        amount = (request.form.get("amount") or "").strip()
        method = (request.form.get("method") or "").strip()
        destination = (request.form.get("destination") or "").strip()
        try:
            amount_dec = to_dec(amount)
        except Exception:
            amount_dec = to_dec(0)

        if amount_dec <= 0:
            flash("Veuillez saisir un montant valide.", "error")
        elif method not in methods:
            flash("Veuillez choisir une méthode de retrait.", "error")
        elif len(destination) < 6:
            flash("Numéro de paiement invalide.", "error")
        else:
            from app.services.withdrawal_service import create_withdrawal
            try:
                wd = create_withdrawal(current_user, amount_dec, method, destination)
                db.session.commit()
                flash(
                    f"Demande de retrait {wd.reference} enregistrée. "
                    "Le montant est immobilisé jusqu'à validation.",
                    "success",
                )
                return redirect(url_for("wallet.history", type="withdrawal"))
            except ValueError as err:
                db.session.rollback()
                flash(str(err), "error")

    return render_template("wallet/withdraw.html", methods=methods, balance=to_dec(current_user.balance))


@wallet_bp.route("/historique")
@login_required
def history():
    type_filter = request.args.get("type", "")
    query = Transaction.query.filter_by(user_id=current_user.id)
    if type_filter in TYPE_LABELS:
        query = query.filter_by(type=type_filter)
    items = query.order_by(Transaction.created_at.desc()).limit(100).all()

    counts = {}
    for key in TYPE_LABELS:
        counts[key] = Transaction.query.filter_by(user_id=current_user.id, type=key).count()

    return render_template(
        "wallet/history.html",
        items=items,
        type_filter=type_filter,
        labels=TYPE_LABELS,
        counts=counts,
    )
