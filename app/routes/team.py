"""Équipe (réseau de parrainage sur 3 niveaux) et lien de parrainage."""
from flask import Blueprint, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app.models import Commission, User
from app.utils import to_dec

team_bp = Blueprint("team", __name__)


@team_bp.route("/equipe")
@login_required
def team():
    user = current_user

    level1 = User.query.filter_by(referred_by=user.id).all()
    level2 = []
    for member in level1:
        level2.extend(User.query.filter_by(referred_by=member.id).all())
    level3 = []
    for member in level2:
        level3.extend(User.query.filter_by(referred_by=member.id).all())

    stats = {
        "level1": len(level1),
        "level2": len(level2),
        "level3": len(level3),
        "total": len(level1) + len(level2) + len(level3),
    }

    # Somme des commissions par niveau (toutes sources confondues).
    commission_sums = dict(
        Commission.query
        .filter_by(beneficiary_id=user.id)
        .with_entities(Commission.level, func.sum(Commission.amount))
        .group_by(Commission.level)
        .all()
    )
    commissions = {
        "level1": to_dec(commission_sums.get(1, 0)),
        "level2": to_dec(commission_sums.get(2, 0)),
        "level3": to_dec(commission_sums.get(3, 0)),
    }

    return render_template(
        "team/equipe.html",
        level1=level1,
        level2=level2,
        level3=level3,
        stats=stats,
        commissions=commissions,
    )


@team_bp.route("/parrainage")
@login_required
def referral():
    user = current_user
    referral_link = url_for("auth.register", ref=user.referral_code, _external=True)
    direct_count = User.query.filter_by(referred_by=user.id).count()
    return render_template(
        "team/parrainage.html",
        referral_link=referral_link,
        referral_code=user.referral_code,
        direct_count=direct_count,
    )
