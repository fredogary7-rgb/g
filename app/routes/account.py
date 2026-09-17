"""Profil, paramètres et notifications."""
import re

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.models import Notification, User, db

account_bp = Blueprint("account", __name__)


def _valid_phone(phone):
    digits = re.sub(r"\D", "", phone or "")
    return 8 <= len(digits) <= 15


@account_bp.route("/profil")
@login_required
def profile():
    user = current_user
    whatsapp_url = current_app.config.get("WHATSAPP_GROUP_URL", "")
    return render_template("account/profile.html", user=user, whatsapp_url=whatsapp_url)


@account_bp.route("/profil/modifier", methods=["GET", "POST"])
@login_required
def edit_profile():
    user = current_user
    countries = current_app.config.get("COUNTRIES", ["Burkina Faso"])
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        country = (request.form.get("country") or "").strip()

        errors = []
        if len(username) < 3:
            errors.append("Le nom d'utilisateur doit contenir au moins 3 caractères.")
        if not phone:
            errors.append("Le numéro de téléphone est requis.")
        elif not _valid_phone(phone):
            errors.append("Numéro de téléphone invalide (ex. +226 70 12 34 56).")
        if country not in countries:
            errors.append("Pays invalide.")

        taken_user = User.query.filter(User.username == username, User.id != user.id).first()
        if taken_user:
            errors.append("Ce nom d'utilisateur est déjà utilisé.")

        if errors:
            for e in errors:
                flash(e, "error")
        else:
            user.username = username
            user.phone = phone or None
            user.country = country
            db.session.commit()
            flash("Profil mis à jour avec succès.", "success")
            return redirect(url_for("account.profile"))

    return render_template("account/edit_profile.html", user=user, countries=countries)


@account_bp.route("/profil/mot-de-passe", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current = request.form.get("current_password") or ""
        new = request.form.get("new_password") or ""
        confirm = request.form.get("confirm_password") or ""

        if not current_user.check_password(current):
            flash("Mot de passe actuel incorrect.", "error")
        elif len(new) < 6:
            flash("Le nouveau mot de passe doit contenir au moins 6 caractères.", "error")
        elif new != confirm:
            flash("Les mots de passe ne correspondent pas.", "error")
        else:
            current_user.set_password(new)
            db.session.commit()
            flash("Mot de passe modifié avec succès.", "success")
            return redirect(url_for("account.profile"))

    return render_template("account/change_password.html")


@account_bp.route("/parametres")
@login_required
def settings():
    return render_template("account/settings.html")


@account_bp.route("/notifications")
@login_required
def notifications():
    items = (
        Notification.query
        .filter((Notification.user_id == current_user.id) | (Notification.user_id.is_(None)))
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return render_template("account/notifications.html", items=items)


@account_bp.route("/notifications/read", methods=["POST"])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    flash("Toutes vos notifications sont marquées comme lues.", "info")
    return redirect(url_for("account.notifications"))


@account_bp.route("/notifications/read/<int:notification_id>", methods=["POST"])
@login_required
def mark_read(notification_id):
    n = Notification.query.get_or_404(notification_id)
    if n.user_id == current_user.id:
        n.is_read = True
        db.session.commit()
    return redirect(n.link or url_for("account.notifications"))
