"""Système de parrainage à 3 niveaux et gestion des commissions.

Taux centralisés dans ``config.py`` :
    REFERRAL_LEVEL_1 = 0.18
    REFERRAL_LEVEL_2 = 0.02
    REFERRAL_LEVEL_3 = 0.01

Hiérarchie :
    A (niveau 3)
    └─ B (niveau 2)
       └─ C (niveau 1)
          └─ D (déposant)

Lorsqu'un dépôt de D est validé par l'administrateur, des commissions sont
créées et créditées immédiatement pour C (1), B (2) et A (3). Une référence
unique et un contrôle de doublon empêchent toute commission dupliquée.
"""
from decimal import Decimal, ROUND_HALF_UP

from flask import current_app

from app.models import Commission, Transaction, db, generate_reference, utcnow
from app.utils import to_dec


def referral_rate(level: int) -> Decimal:
    return Decimal(str(current_app.config["REFERRAL_LEVELS"][level - 1]))


def create_commissions_for_deposit(deposit):
    """Crée et crédite immédiatement les commissions (niveau 1 à 3) après
    validation d'un dépôt. Anti-doublon par (deposit, niveau, bénéficiaire)."""
    buyer = deposit.user
    amount = to_dec(deposit.amount)
    created = []

    for level, referrer in buyer.referral_chain(max_level=3):
        if referrer.is_banned:
            continue  # pas de commission vers un compte banni

        rate = referral_rate(level)
        # Arrondi sain au FCFA le plus proche.
        commission_amount = (amount * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        if commission_amount <= 0:
            continue

        exists = Commission.query.filter_by(
            deposit_id=deposit.id,
            level=level,
            beneficiary_id=referrer.id,
        ).first()
        if exists:
            continue  # anti doublon

        commission = Commission(
            beneficiary_id=referrer.id,
            source_user_id=buyer.id,
            deposit_id=deposit.id,
            purchase_id=None,
            level=level,
            rate=rate,
            amount=commission_amount,
            reference=generate_reference("COM"),
            status="approved",
        )
        db.session.add(commission)

        # Crédit immédiat du bénéficiaire.
        referrer.total_commission = to_dec(referrer.total_commission) + commission_amount
        referrer.balance = to_dec(referrer.balance) + commission_amount

        db.session.add(Transaction(
            user_id=referrer.id,
            type="commission",
            amount=commission_amount,
            balance_after=referrer.balance,
            reference=commission.reference,
            description=f"Commission parrainage niveau {level}",
            status="completed",
        ))

        from app.services.notification_service import notify
        notify(
            referrer.id,
            "commission",
            "Nouvelle commission",
            f"Vous avez reçu {int(commission_amount):,} FCFA de commission (niveau {level}).",
            "/historique",
        )
        created.append(commission)

    return created


def approve_commission(commission):
    """Valide une commission : crédite le portefeuille du bénéficiaire."""
    if commission.status != "pending":
        return commission

    commission.status = "approved"
    commission.updated_at = utcnow()

    beneficiary = commission.beneficiary
    amount = to_dec(commission.amount)
    beneficiary.total_commission = to_dec(beneficiary.total_commission) + amount
    beneficiary.balance = to_dec(beneficiary.balance) + amount

    db.session.add(Transaction(
        user_id=beneficiary.id,
        type="commission",
        amount=amount,
        balance_after=beneficiary.balance,
        reference=commission.reference,
        description=f"Commission parrainage niveau {commission.level}",
        status="completed",
    ))

    from app.services.notification_service import notify
    notify(
        beneficiary.id,
        "commission",
        "Nouvelle commission",
        f"Vous avez reçu {int(amount):,} FCFA de commission (niveau {commission.level}).",
        "/historique",
    )
    return commission


def cancel_commission(commission, note=None):
    """Annule une commission encore en attente."""
    if commission.status == "cancelled":
        return commission
    commission.status = "cancelled"
    commission.updated_at = utcnow()
    return commission
