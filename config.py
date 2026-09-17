"""Configuration centrale de l'application FANTA.

Toutes les valeurs sensibles proviennent des variables d'environnement
(fichier .env). Aucun secret n'est écrit en dur dans le code.
"""
import os
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from dotenv import load_dotenv

load_dotenv()


def _normalize_database_url(raw: str | None) -> str | None:
    """Normalise l'URL PostgreSQL pour SQLAlchemy + psycopg2.

    - Convertit ``postgres://`` en ``postgresql://``.
    - Retire le paramètre ``channel_binding`` qui n'est pas reconnu par
      certaines versions de libpq embarquées avec psycopg2 (le SSL requis
      reste assuré par ``sslmode=require``).
    """
    if not raw:
        return None
    url = raw.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    # Suppression du paramètre non supporté par psycopg2.
    qs.pop("channel_binding", None)
    # Reconstruction d'une query string propre.
    query = urlencode(qs, doseq=True)
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment)
    )


_database_url = _normalize_database_url(os.getenv("DATABASE_URL"))


class Config:
    """Configuration de base (développement sécurisé)."""

    APP_NAME = "FANTA"
    CURRENCY = "FCFA"

    # --- Sécurité / sessions ---
    # Valeur de développement uniquement : remplacez-la par SECRET_KEY dans .env
    # en production (sinon les sessions et le CSRF perdent leur intégrité).
    SECRET_KEY = os.getenv("SECRET_KEY") or "dev-only-insecure-secret-change-me"

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False  # passer à True si HTTPS forcé
    REMEMBER_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 7  # 7 jours

    # --- Base de données ---
    # Priorité : DATABASE_URL (Neon PostgreSQL). Fallback local SQLite
    # uniquement pour pouvoir tester le projet sans base distante.
    SQLALCHEMY_DATABASE_URI = _database_url or "sqlite:///fanta.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    # --- Parrainage (3 niveaux, config centralisée) ---
    REFERRAL_LEVEL_1 = 0.18
    REFERRAL_LEVEL_2 = 0.02
    REFERRAL_LEVEL_3 = 0.01
    # Liste ordonnée niveau 1 -> niveau 3.
    REFERRAL_LEVELS = [REFERRAL_LEVEL_1, REFERRAL_LEVEL_2, REFERRAL_LEVEL_3]

    # --- Paiement ---
    # "sandbox" = mode test, aucune transaction réelle. "live" sera branché
    # dans app/services/payment_service.py lorsque vous fournirez l'API.
    PAYMENT_MODE = os.getenv("PAYMENT_MODE", "sandbox")
    PAYMENT_METHODS = ["Orange Money", "MTN Mobile Money", "Moov Money", "Wave"]
    WITHDRAWAL_METHODS = ["Orange Money", "MTN Mobile Money", "Moov Money", "Wave", "Banque"]

    # --- Initialisation automatique (idempotente) au démarrage ---
    # Crée les tables manquantes et insère les produits si la base est vide.
    AUTO_INIT_DB = True
    # Compte admin créé automatiquement UNIQUEMENT si ADMIN_PASSWORD est défini.
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@fanta.app")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")  # None = pas de création auto

    # --- Parrainage : taux affichés ---
    @staticmethod
    def referral_rate(level: int):
        if level == 1:
            return Config.REFERRAL_LEVEL_1
        if level == 2:
            return Config.REFERRAL_LEVEL_2
        if level == 3:
            return Config.REFERRAL_LEVEL_3
        return 0.0
