"""Authentification : inscription, connexion, déconnexion."""
import re

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_

from app.models import Referral, User, db, ensure_referral_code_unique, generate_referral_code

auth_bp = Blueprint("auth", __name__, url_prefix="")


def _clean_phone(phone: str) -> str:
    """Normalise un numéro : conserve + et chiffres, retire les espaces/tirets/etc."""
    return re.sub(r"[^\d+]", "", phone or "").strip()


def _valid_phone(phone: str) -> bool:
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return False
    # Burkina Faso : 8 chiffres en local ; 11 avec l'indicatif +226.
    return 8 <= len(digits) <= 15


def _validate_registration(form) -> tuple[list, dict]:
    """Validation serveur stricte. Ne fait JAMAIS confiance au JS."""
    errors = []
    username = (form.get("username") or "").strip()
    phone = (form.get("phone") or "").strip()
    country = (form.get("country") or "").strip()
    ref_code = (form.get("referral_code") or "").strip().upper()
    password = form.get("password") or ""
    confirm = form.get("confirm_password") or ""
    accept = form.get("accept")

    if len(username) < 3:
        errors.append("Le nom d'utilisateur doit contenir au moins 3 caractères.")
    if " " in username:
        errors.append("Le nom d'utilisateur ne doit pas contenir d'espaces.")
    if not country:
        errors.append("Veuillez sélectionner votre pays.")
    if not phone:
        errors.append("Le numéro de téléphone est requis.")
    elif not _valid_phone(phone):
        errors.append("Numéro de téléphone invalide (ex. +226 70 12 34 56).")
    if len(password) < 6:
        errors.append("Le mot de passe doit contenir au moins 6 caractères.")
    if password != confirm:
        errors.append("Les mots de passe ne correspondent pas.")
    if not accept:
        errors.append("Vous devez accepter les conditions d'utilisation.")

    if User.query.filter_by(username=username).first():
        errors.append("Ce nom d'utilisateur est déjà utilisé.")

    referrer = None
    if ref_code:
        referrer = User.query.filter_by(referral_code=ref_code).first()
        if not referrer:
            errors.append("Code de parrainage invalide.")
        elif referrer.is_banned:
            errors.append("Ce parrain n'est plus disponible.")

    data = {
        "username": username,
        "phone": _clean_phone(phone),
        "country": country,
        "referral_code": ref_code,
        "password": password,
        "referrer": referrer,
    }
    return errors, data


@auth_bp.route("/inscription", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    # Pré-remplissage quand on arrive via /inscription?ref=ABC123
    ref = (request.args.get("ref") or "").strip().upper()
    form_data = {"username": "", "phone": "", "country": "Burkina Faso", "referral_code": ref}

    if request.method == "POST":
        errors, data = _validate_registration(request.form)
        form_data.update({
            "username": data["username"],
            "phone": data["phone"],
            "country": data["country"],
            "referral_code": data["referral_code"],
        })
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            user = User(
                username=data["username"],
                email=None,
                phone=data["phone"] or None,
                country=data["country"],
                referral_code=ensure_referral_code_unique(generate_referral_code()),
            )
            if data["referrer"] is not None:
                user.referred_by = data["referrer"].id
            user.set_password(data["password"])
            db.session.add(user)
            db.session.flush()

            if data["referrer"] is not None:
                db.session.add(Referral(
                    referrer_id=data["referrer"].id,
                    referred_id=user.id,
                ))
                from app.services.notification_service import notify
                notify(
                    data["referrer"].id,
                    "referral",
                    "Nouveau filleul",
                    f"{user.username} vient de rejoindre FANTA avec votre code.",
                    "/equipe",
                )
            db.session.commit()

            login_user(user)
            flash("Compte créé avec succès. Bienvenue sur FANTA !", "success")
            return redirect(url_for("main.dashboard"))

    return render_template("auth/inscription.html", ref=ref, form_data=form_data)


@auth_bp.route("/connexion", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        identifier = (request.form.get("identifier") or "").strip()
        password = request.form.get("password") or ""
        remember = request.form.get("remember") == "on"

        ident_phone = _clean_phone(identifier)
        user = User.query.filter(
            or_(
                User.username == identifier,
                User.email == identifier.lower(),
                User.phone == identifier,
                User.phone == ident_phone,
            )
        ).first()

        if user and user.check_password(password):
            if user.is_banned:
                flash("Ce compte a été suspendu. Contactez le support.", "error")
            else:
                login_user(user, remember=remember)
                flash(f"Bonjour {user.username} !", "success")
                next_url = request.args.get("next")
                return redirect(next_url or url_for("main.dashboard"))
        else:
            flash("Identifiants incorrects.", "error")

    return render_template("auth/connexion.html")


@auth_bp.route("/deconnexion", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Vous êtes déconnecté(e). À bientôt !", "info")
    return redirect(url_for("auth.login"))
