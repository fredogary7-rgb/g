"""Création des notifications."""
from app.models import Notification, db


def notify(user_id, type_, title, message=None, link=None):
    """Crée une notification individuelle (user_id) ou globale (user_id=None)."""
    n = Notification(
        user_id=user_id,
        type=type_,
        title=title,
        message=message,
        link=link,
    )
    db.session.add(n)
    return n


def broadcast(type_, title, message=None, link=None):
    """Annonce globale visible par tous les utilisateurs."""
    return notify(None, type_, title, message, link)
