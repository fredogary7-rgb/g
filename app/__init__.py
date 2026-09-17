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

        from app.models import Product
        if Product.query.count() == 0:
            from app.seed_data import PRODUCTS_SEED
            for data in PRODUCTS_SEED:
                db.session.add(Product(**data))
            db.session.commit()

        admin_password = app.config.get("ADMIN_PASSWORD")
        if admin_password and User.query.filter_by(is_admin=True).count() == 0:
            from app.models import ensure_referral_code_unique, generate_referral_code
            admin = User(
                username=app.config.get("ADMIN_USERNAME", "admin"),
                email=app.config.get("ADMIN_EMAIL", "admin@fanta.app"),
                is_admin=True,
                referral_code=ensure_referral_code_unique(generate_referral_code()),
            )
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()

