"""Opérations financières : transactions, solde, achats et validation des dépôts."""
from datetime import timedelta

from flask import url_for

from app.models import Purchase, Transaction, db, generate_reference, utcnow
from app.utils import to_dec


def record_transaction(user, type_, amount, reference, description=None, status="completed"):
    """Enregistre un mouvement signé et figé dans l'historique."""
    amount = to_dec(amount)
    t = Transaction(
        user_id=user.id,
        type=type_,
        amount=amount,
        balance_after=to_dec(user.balance),
        reference=reference,
        description=description,
        status=status,
    )
    db.session.add(t)
    return t


def credit_balance(user, amount):
    user.balance = to_dec(user.balance) + to_dec(amount)
    return user.balance


def debit_balance(user, amount):
    user.balance = to_dec(user.balance) - to_dec(amount)
    return user.balance


def purchase_product(user, product):
    """Active un produit : débite le solde, crée l'en-cours et les commissions."""
    price = to_dec(product.price)
    if to_dec(user.balance) < price:
        raise ValueError("Solde insuffisant. Rechargez d'abord votre portefeuille.")

    now = utcnow()
    reference = generate_reference("PUR")
    purchase = Purchase(
        user_id=user.id,
        product_id=product.id,
        reference=reference,
        amount=price,
        daily_income=product.daily_income,
        total_income=product.total_income,
        duration=int(product.duration),
        start_date=now,
        end_date=now + timedelta(days=int(product.duration)),
        status="active",
    )
    db.session.add(purchase)
    debit_balance(user, price)
    record_transaction(user, "purchase", -price, reference, f"Achat du produit {product.name}")
    db.session.flush()  # récupère purchase.id pour les commissions

    from app.services.referral_service import create_commissions_for_purchase
    commissions = create_commissions_for_purchase(purchase)

    from app.services.notification_service import notify
    notify(
        user.id,
        "product",
        "Produit activé",
        f"{product.name} a été activé avec succès.",
        url_for("main.product_detail", product_id=product.id),
    )
    return purchase, commissions


def approve_deposit(deposit, note=None):
    """Valide un dépôt sandbox : crédite solde + total déposé."""
    if deposit.status != "pending":
        return deposit
    deposit.status = "approved"
    deposit.processed_at = utcnow()
    if note:
        deposit.note = note

    user = deposit.user
    amount = to_dec(deposit.amount)
    credit_balance(user, amount)
    user.total_deposit = to_dec(user.total_deposit) + amount
    record_transaction(
        user, "deposit", amount, deposit.reference,
        f"Dépôt validé ({deposit.method})",
    )

    from app.services.notification_service import notify
    notify(
        user.id,
        "deposit",
        "Dépôt approuvé",
        f"Votre dépôt de {int(amount):,} FCFA a été crédité sur votre portefeuille.",
        "/portefeuille",
    )
    return deposit


def reject_deposit(deposit, note=None):
    if deposit.status != "pending":
        return deposit
    deposit.status = "rejected"
    deposit.processed_at = utcnow()
    if note:
        deposit.note = note

    from app.services.notification_service import notify
    notify(
        deposit.user_id,
        "deposit",
        "Dépôt rejeté",
        f"Votre dépôt {deposit.reference} a été rejeté.",
        "/historique",
    )
    return deposit
