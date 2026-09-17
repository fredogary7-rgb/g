"""Distribution des revenus quotidiens des produits actifs.

Le crédit quotidien est volontairement explicite : rien n'est simulé en
arrière-plan sans contrôle. L'administrateur (ou une tâche planifiée) lance
``flask process-income`` pour créditer la journée courante des en-cours actifs.
"""
from app.models import Purchase, db, generate_reference, utcnow
from app.utils import to_dec


def process_daily_income():
    """Crédite un jour de revenu aux en-cours actifs (une fois par jour max)."""
    today = utcnow().date()
    credited = 0

    for purchase in Purchase.query.filter_by(status="active").all():
        last = purchase.last_credited_date.date() if purchase.last_credited_date else None
        if last is not None and last >= today:
            continue  # déjà crédité aujourd'hui

        end = purchase.end_date.date() if purchase.end_date else None
        if end is not None and end < today:
            purchase.status = "completed"  # durée écoulée
            continue

        user = purchase.user
        amount = to_dec(purchase.daily_income)
        user.balance = to_dec(user.balance) + amount
        user.total_income = to_dec(user.total_income) + amount

        from app.services.finance_service import record_transaction
        record_transaction(
            user, "income", amount,
            generate_reference("INC"),
            f"Revenu quotidien — {purchase.product.name}",
        )
        purchase.last_credited_date = utcnow()
        credited += 1

    db.session.commit()
    return credited
