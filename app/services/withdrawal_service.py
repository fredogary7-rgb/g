"""Gestion des retraits.

Version développement : un retrait est créé au statut ``pending``, le solde
est immobilisé, puis l'administrateur approuve ou rejette la demande.
AUCUN transfert d'argent réel n'est simulé silencieusement.
"""
from app.models import Transaction, Withdrawal, db, generate_reference
from app.utils import to_dec


def create_withdrawal(user, amount, method, destination):
    amount = to_dec(amount)
    if amount <= 0:
        raise ValueError("Le montant doit être supérieur à zéro.")

    if to_dec(user.balance) < amount:
        raise ValueError("Solde insuffisant pour ce retrait.")

    reference = generate_reference("WDR")
    withdrawal = Withdrawal(
        user_id=user.id,
        amount=amount,
        method=method,
        destination=destination,
        reference=reference,
        status="pending",
    )
    db.session.add(withdrawal)

    # Immobilisation : le solde est débité dès la demande.
    user.balance = to_dec(user.balance) - amount

    from app.services.finance_service import record_transaction
    record_transaction(
        user, "withdrawal", -amount, reference,
        f"Retrait {method} — {destination}",
        status="pending",
    )

    from app.services.notification_service import notify
    notify(
        user.id,
        "withdrawal",
        "Demande de retrait",
        f"Votre retrait de {int(amount):,} FCFA est en attente.",
        "/historique",
    )
    return withdrawal


def approve_withdrawal(withdrawal, note=None):
    """Approuve un retrait : l'argent a été 'débloqué' (test)."""
    if withdrawal.status != "pending":
        return withdrawal
    withdrawal.status = "approved"
    withdrawal.processed_at = _now()
    if note:
        withdrawal.note = note

    # Marquer la transaction de retrait comme complétée (référence unique conservée).
    tx = Transaction.query.filter_by(reference=withdrawal.reference).first()
    if tx:
        tx.status = "completed"

    from app.services.notification_service import notify
    notify(
        withdrawal.user_id,
        "withdrawal",
        "Retrait approuvé",
        f"Votre retrait de {int(withdrawal.amount):,} FCFA a été approuvé.",
        "/historique",
    )
    return withdrawal


def reject_withdrawal(withdrawal, note=None):
    """Rejette un retrait : le solde immobilisé est recrédité."""
    if withdrawal.status != "pending":
        return withdrawal
    withdrawal.status = "rejected"
    withdrawal.processed_at = _now()
    if note:
        withdrawal.note = note

    user = withdrawal.user
    user.balance = to_dec(user.balance) + to_dec(withdrawal.amount)

    # Marquer la transaction de retrait comme rejetée.
    tx = Transaction.query.filter_by(reference=withdrawal.reference).first()
    if tx:
        tx.status = "rejected"

    # Remboursement : nouvelle référence dédiée.
    from app.services.finance_service import record_transaction
    record_transaction(
        user, "refund", to_dec(withdrawal.amount),
        generate_reference("RFD"), "Remboursement retrait rejeté",
        status="completed",
    )

    from app.services.notification_service import notify
    notify(
        user.id,
        "withdrawal",
        "Retrait rejeté",
        f"Votre retrait de {int(withdrawal.amount):,} FCFA a été rejeté et recrédité.",
        "/historique",
    )
    return withdrawal


def _now():
    from app.models import utcnow
    return utcnow()
