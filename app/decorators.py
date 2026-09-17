"""Décorateurs de contrôle d'accès."""
from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def admin_required(f):
    """Restreint une route aux administrateurs connectés."""

    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not getattr(current_user, "is_admin", False):
            abort(403)
        return f(*args, **kwargs)

    return decorated
