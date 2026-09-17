"""Système de parrainage à 3 niveaux et gestion des commissions.

Taux centralisés dans ``config.py`` :
    REFERRAL_LEVEL_1 = 0.18
    REFERRAL_LEVEL_2 = 0.02
    REFERRAL_LEVEL_3 = 0.01

Hiérarchie :
    A (niveau 3)
    └─ B (niveau 2)
       └─ C (niveau 1)
          └─ D (acheteur)

Lorsqu'un achat est effectué par D, des commissions sont créées pour C (1),
B (2) et A (3). Chaque commission est créée au statut ``pending`` puis validée
par l'administrateur (ou annulée). Une référence unique et un contrôle de
doublon empêchent toute commission dupliquée pour la même opération.
"""
from decimal import Decimal, ROUND_HALF_UP

from flask import current_app

from app.models import Commission, Transaction, db, generate_reference, utcnow
from app.utils import to_dec


def referral_rate(level: int) -> Decimal:
    return Decimal(str(current_app.config["REFERRAL_LEVELS"][level - 1]))


def create_commissions_for_purchase(purchase):
    """Crée les commissions (niveau 1 à 3) liées à un achat, sans doublon."""
    buyer = purchase.user
    amount = to_dec(purchase.amount)
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
            purchase_id=purchase.id,
            level=level,
            beneficiary_id=referrer.id,
        ).first()
        if exists:
            continue  # anti doublon

        commission = Commission(
            beneficiary_id=referrer.id,
            source_user_id=buyer.id,
            purchase_id=purchase.id,
            level=level,
            rate=rate,
            amount=commission_amount,
            reference=generate_reference("COM"),
            status="pending",
        )
        db.session.add(commission)
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
