"""Portefeuille : solde, dépôt, retrait et historique."""
import re

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
    "adjustment": "Ajustements",
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
    preset_amounts = [7000, 12000, 21000, 25000, 35000, 50000, 100000]
    account_number = current_app.config.get("OM_ACCOUNT_NUMBER", "07940067")
    account_name = current_app.config.get("OM_ACCOUNT_NAME", "Toure Ramata")

    if request.method == "POST":
        amount = (request.form.get("amount") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        try:
            amount_dec = to_dec(amount)
        except Exception:
            amount_dec = to_dec(0)

        digits = re.sub(r"\D", "", phone)
        if amount_dec < 500:
            flash("Montant minimum : 500 FCFA.", "error")
        elif len(digits) < 8:
            flash("Numéro Orange Money invalide.", "error")
        else:
            from app.services.payment_service import get_provider
            provider = get_provider()
            dep = provider.create_deposit(
                current_user, amount_dec, "Orange Money",
                note=f"Orange Money · n° {phone}",
            )
            db.session.commit()
            ussd = f"*144*2*1*{account_number}*{int(amount_dec)}#"
            return render_template(
                "wallet/deposit.html",
                preset_amounts=preset_amounts,
                account_number=account_number,
                account_name=account_name,
                deposit=dep,
                ussd=ussd,
            )

    return render_template(
        "wallet/deposit.html",
        preset_amounts=preset_amounts,
        account_number=account_number,
        account_name=account_name,
        deposit=None,
        ussd=None,
    )


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
