"""Commandes CLI (Flask) : initialisation, seed et traitement des revenus."""
import os

import click
from flask.cli import with_appcontext


def _create_tables():
    from app.models import db
    db.create_all()


def _seed_products():
    from app.models import Product, db
    from app.seed_data import PRODUCTS_SEED
    existing = {p.name for p in Product.query.all()}
    added = 0
    for data in PRODUCTS_SEED:
        if data["name"] in existing:
            continue
        db.session.add(Product(**data))
        added += 1
    return added


def _seed_admin():
    from app.models import User, db, ensure_referral_code_unique, generate_referral_code
    username = os.getenv("ADMIN_USERNAME", "admin")
    email = os.getenv("ADMIN_EMAIL", "admin@fanta.app")
    admin = User.query.filter_by(username=username).first()
    if admin is not None:
        return admin, False

    password = os.getenv("ADMIN_PASSWORD") or "Admin@1234"
    admin = User(
        username=username,
        email=email,
        phone=None,
        is_admin=True,
        referral_code=ensure_referral_code_unique(generate_referral_code()),
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.flush()
    return admin, True


def register(app):
    @app.cli.command("init-db")
    def init_db_command():
        """Crée les tables de la base de données."""
        _create_tables()
        click.echo("✓ Tables de base de données créées.")

    @app.cli.command("seed")
    @with_appcontext
    def seed_command():
        """Insère les 8 produits Fanta et le compte administrateur."""
        _create_tables()
        added = _seed_products()
        admin, created = _seed_admin()
        from app.models import db
        db.session.commit()
        click.echo(f"✓ {added} produit(s) inséré(s).")
        if created:
            click.echo(
                "✓ Administrateur créé -> identifiant: admin / "
                f"mot de passe: {os.getenv('ADMIN_PASSWORD') or 'Admin@1234'} "
                "(changez-le immédiatement)"
            )
        else:
            click.echo("✓ Administrateur déjà présent.")

    @app.cli.command("process-income")
    @with_appcontext
    def process_income_command():
        """Crédite un jour de revenu aux produits actifs."""
        from app.services.income_service import process_daily_income
        count = process_daily_income()
        click.echo(f"✓ {count} revenu(s) quotidien(s) crédité(s).")
