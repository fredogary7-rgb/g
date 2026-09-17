"""Factory d'application FANTA."""
from flask import Flask, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFError, CSRFProtect

from config import Config

from app.models import Notification, User, db
from app.utils import fmt_date, money, number, timeago

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
login_manager.login_message_category = "warning"

csrf = CSRFProtect()


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # --- Filtres de templates ---
    app.add_template_filter(money, "money")
    app.add_template_filter(number, "number")
    app.add_template_filter(fmt_date, "fmt_date")
    app.add_template_filter(timeago, "timeago")

    # --- Blueprints ---
    from app.routes.account import account_bp
    from app.routes.admin import admin_bp
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.team import team_bp
    from app.routes.wallet import wallet_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(wallet_bp)
    app.register_blueprint(team_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(admin_bp)

    # --- Contexte global injecté dans tous les templates ---
    @app.context_processor
    def inject_globals():
        unread = 0
        if current_user.is_authenticated:
            unread = Notification.query.filter_by(
                user_id=current_user.id, is_read=False
            ).count()
        return {
            "APP_NAME": app.config["APP_NAME"],
            "CURRENCY": app.config["CURRENCY"],
            "unread_count": unread,
            "referral_levels": app.config["REFERRAL_LEVELS"],
        }

    # --- Gestionnaires d'erreurs ---
    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(_e):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    @app.errorhandler(CSRFError)
    def handle_csrf(_e):
        from flask import flash
        flash("Session expirée ou jeton de sécurité invalide. Réessayez.", "error")
        return redirect(request.referrer or url_for("main.home"))

    # --- Initialisation automatique et idempotente de la base ---
    if app.config.get("AUTO_INIT_DB", True):
        _auto_init(app)

    # --- Commandes CLI ---
    from app import commands
    commands.register(app)

    return app


def _auto_init(app):
    """Crée les tables manquantes et insère les données initiales (sans écraser)."""
    with app.app_context():
        db.create_all()
        _ensure_schema()

        from app.models import Product
        from app.seed_data import PRODUCTS_SEED
        existing = {p.name: p for p in Product.query.all()}
        for data in PRODUCTS_SEED:
            p = existing.get(data["name"])
            if p is None:
                db.session.add(Product(**data))
            else:
                # Synchronise les champs des produits configurés (prix, image, etc.)
                p.price = data["price"]
                p.daily_income = data["daily_income"]
                p.total_income = data["total_income"]
                p.duration = data["duration"]
                p.image = data["image"]
                p.sort_order = data["sort_order"]
                p.description = data["description"]
        # "Fanta 1" n'est plus au catalogue : on le désactive (sans supprimer
        # les éventuels achats déjà liés).
        fanta1 = Product.query.filter_by(name="Fanta 1").first()
        if fanta1 is not None and fanta1.active:
            fanta1.active = False
        db.session.commit()

        from app.models import ensure_referral_code_unique, generate_referral_code
        admin_username = app.config.get("ADMIN_USERNAME", "Thom14")
        admin_phone = app.config.get("ADMIN_PHONE", "71339325")
        admin = User.query.filter_by(username=admin_username).first()
        if admin is None:
            admin = User(
                username=admin_username,
                email=None,
                phone=admin_phone or None,
                country="Burkina Faso",
                is_admin=True,
                referral_code=ensure_referral_code_unique(generate_referral_code()),
            )
            admin.set_password(app.config.get("ADMIN_PASSWORD") or "Admin@1234")
            db.session.add(admin)
            db.session.commit()
        elif not admin.is_admin:
            admin.is_admin = True
            db.session.commit()


def _ensure_schema():
    """Migrations légères et idempotentes pour PostgreSQL (Neon).

    Ajoute la colonne ``country`` et rend ``email`` nullable sur un schéma
    existant. Sans effet sur SQLite (tables recréées en dev/tests).
    """
    if db.engine.dialect.name != "postgresql":
        return
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    users_cols = {c["name"]: c for c in inspector.get_columns("users")}
    commissions_cols = {c["name"]: c for c in inspector.get_columns("commissions")}

    with db.engine.begin() as conn:
        if "country" not in users_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN country VARCHAR(60)"))
        email_col = users_cols.get("email")
        if email_col is not None and not email_col.get("nullable"):
            conn.execute(text("ALTER TABLE users ALTER COLUMN email DROP NOT NULL"))
        conn.execute(text(
            "UPDATE users SET country = 'Burkina Faso' WHERE country IS NULL OR country = ''"
        ))

        # Commissions liées aux dépôts (et purchase_id devient optionnel).
        if "deposit_id" not in commissions_cols:
            conn.execute(text("ALTER TABLE commissions ADD COLUMN deposit_id INTEGER"))
        purchase_col = commissions_cols.get("purchase_id")
        if purchase_col is not None and not purchase_col.get("nullable"):
            conn.execute(text("ALTER TABLE commissions ALTER COLUMN purchase_id DROP NOT NULL"))

