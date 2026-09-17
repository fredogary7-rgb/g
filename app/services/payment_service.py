"""Couche de paiement.

Cette couche est volontairement abstraite : elle n'intègre AUCUNE API, jeton ou
URL de prestataire en dur. Lorsque vous fournirez la documentation officielle
(nom, clé API, token, URL, méthodes), il suffira d'implémenter une nouvelle
classe ``PaymentProvider`` et de la retourner dans ``get_provider()``.

En mode ``sandbox`` (par défaut), les dépôts sont enregistrés au statut
``pending`` et AUCUNE transaction réelle n'est prétendue effectuée :
c'est l'administrateur qui confirme manuellement depuis l'espace admin.
"""
from flask import current_app

from app.models import Deposit, db, generate_reference
from app.utils import to_dec


class PaymentProvider:
    """Interface contractuelle d'un prestataire de paiement."""

    name = "base"

    def available_methods(self):
        return current_app.config.get("PAYMENT_METHODS", [])

    def create_deposit(self, user, amount, method):
        raise NotImplementedError

    def verify_payment(self, reference):
        """À implémenter côté prestataire réel (webhook / requête API)."""
        raise NotImplementedError


class SandboxPaymentProvider(PaymentProvider):
    """Mode TEST : aucun argent réel n'est déplacé."""

    name = "sandbox"

    def create_deposit(self, user, amount, method):
        amount = to_dec(amount)
        reference = generate_reference("DEP")
        deposit = Deposit(
            user_id=user.id,
            amount=amount,
            method=method,
            reference=reference,
            status="pending",
            note="Mode SANDBOX — dépôt de test, aucun paiement réel.",
        )
        db.session.add(deposit)
        db.session.flush()

        from app.services.notification_service import notify
        notify(
            user.id,
            "deposit",
            "Dépôt enregistré",
            f"Votre dépôt de test de {int(amount):,} FCFA est en attente de validation.",
            "/historique",
        )
        return deposit


def get_provider() -> PaymentProvider:
    """Retourne le prestataire actif selon ``PAYMENT_MODE``."""
    mode = current_app.config.get("PAYMENT_MODE", "sandbox")
    if mode == "sandbox":
        return SandboxPaymentProvider()
    # Brancher ici le prestataire officiel une fois l'API fournie.
    raise RuntimeError(
        "Aucun prestataire de paiement configuré pour le mode actif. "
        "Renseignez les clés dans .env et implémentez le fournisseur."
    )
