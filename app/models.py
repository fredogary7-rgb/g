"""Modèles SQLAlchemy de l'application FANTA."""
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_referral_code(length: int = 8) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


def generate_reference(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    phone = db.Column(db.String(30), nullable=True)
    country = db.Column(db.String(60), default="Burkina Faso", nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    referral_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    referred_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    avatar = db.Column(db.String(255), nullable=True)

    balance = db.Column(db.Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    total_deposit = db.Column(db.Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    total_income = db.Column(db.Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    total_commission = db.Column(db.Numeric(14, 2), default=Decimal("0.00"), nullable=False)

    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_banned = db.Column(db.Boolean, default=False, nullable=False)

    # Relation hiérarchique de parrainage :
    #  user.referrer -> le parent, user.referrals -> les filleuls directs.
    referrer = db.relationship(
        "User",
        remote_side=[id],
        backref=db.backref("referrals", lazy="dynamic"),
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def referrer_at(self, level: int):
        """Retourne l'ancêtre au niveau ``level`` (1 = parent direct)."""
        node = self
        for _ in range(level):
            node = node.referrer if node is not None else None
        return node

    def referral_chain(self, max_level: int = 3):
        """Retourne ``[(niveau, Utilisateur)]`` pour la lignée parrainante."""
        chain = []
        node = self.referrer
        level = 1
        while node is not None and level <= max_level:
            chain.append((level, node))
            node = node.referrer
            level += 1
        return chain

    def __repr__(self):
        return f"<User {self.username}>"


class Product(TimestampMixin, db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    price = db.Column(db.Numeric(14, 2), nullable=False)
    daily_income = db.Column(db.Numeric(14, 2), nullable=False)
    total_income = db.Column(db.Numeric(14, 2), nullable=False)
    duration = db.Column(db.Integer, nullable=False, default=35)
    image = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)

    purchases = db.relationship("Purchase", backref="product", lazy="dynamic")

    def __repr__(self):
        return f"<Product {self.name}>"


class Purchase(TimestampMixin, db.Model):
    """Souscription : l'utilisateur a activé un produit (investissement)."""

    __tablename__ = "purchases"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    reference = db.Column(db.String(40), unique=True, nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    daily_income = db.Column(db.Numeric(14, 2), nullable=False)
    total_income = db.Column(db.Numeric(14, 2), nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.DateTime(timezone=True), nullable=False)
    end_date = db.Column(db.DateTime(timezone=True), nullable=False)
    last_credited_date = db.Column(db.DateTime(timezone=True), nullable=True)
    status = db.Column(db.String(20), default="active", nullable=False)  # active/completed/cancelled

    user = db.relationship("User", backref=db.backref("purchases", lazy="dynamic"))
    commissions = db.relationship("Commission", backref="purchase", lazy="dynamic")

    def __repr__(self):
        return f"<Purchase {self.reference}>"


class Deposit(TimestampMixin, db.Model):
    __tablename__ = "deposits"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    method = db.Column(db.String(50), nullable=False, default="sandbox")
    reference = db.Column(db.String(40), unique=True, nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)  # pending/approved/rejected
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    processed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    user = db.relationship("User", backref=db.backref("deposits", lazy="dynamic"))

    def __repr__(self):
        return f"<Deposit {self.reference}>"


class Withdrawal(TimestampMixin, db.Model):
    __tablename__ = "withdrawals"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    method = db.Column(db.String(50), nullable=False)
    destination = db.Column(db.String(120), nullable=False)  # numéro / compte
    reference = db.Column(db.String(40), unique=True, nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)  # pending/approved/rejected
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    processed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    user = db.relationship("User", backref=db.backref("withdrawals", lazy="dynamic"))

    def __repr__(self):
        return f"<Withdrawal {self.reference}>"


class Transaction(TimestampMixin, db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    # deposit / withdrawal / purchase / income / commission / refund
    type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)  # signé (+ crédit, - débit)
    balance_after = db.Column(db.Numeric(14, 2), nullable=True)
    reference = db.Column(db.String(40), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default="completed", nullable=False)

    user = db.relationship("User", backref=db.backref("transactions", lazy="dynamic"))

    def __repr__(self):
        return f"<Transaction {self.type} {self.amount}>"


class Commission(db.Model):
    __tablename__ = "commissions"

    id = db.Column(db.Integer, primary_key=True)
    beneficiary_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    source_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey("purchases.id"), nullable=True, index=True)
    deposit_id = db.Column(db.Integer, db.ForeignKey("deposits.id"), nullable=True, index=True)
    level = db.Column(db.Integer, nullable=False)
    rate = db.Column(db.Numeric(6, 4), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    reference = db.Column(db.String(40), unique=True, nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)  # pending/approved/cancelled
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    beneficiary = db.relationship(
        "User", foreign_keys=[beneficiary_id], backref=db.backref("earned_commissions", lazy="dynamic")
    )
    source_user = db.relationship("User", foreign_keys=[source_user_id])

    def __repr__(self):
        return f"<Commission {self.reference} level={self.level}>"


class Referral(db.Model):
    """Trace explicite de chaque relation de parrainage directe."""

    __tablename__ = "referrals"

    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    referred_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    referrer = db.relationship("User", foreign_keys=[referrer_id])
    referred = db.relationship("User", foreign_keys=[referred_id])

    def __repr__(self):
        return f"<Referral {self.referrer_id} -> {self.referred_id}>"


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)  # NULL = annonce globale
    type = db.Column(db.String(20), nullable=False, default="info")
    title = db.Column(db.String(160), nullable=False)
    message = db.Column(db.Text, nullable=True)
    link = db.Column(db.String(255), nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    user = db.relationship("User", backref=db.backref("notifications", lazy="dynamic"))

    def __repr__(self):
        return f"<Notification {self.title}>"


class AdminAction(db.Model):
    __tablename__ = "admin_actions"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action = db.Column(db.String(60), nullable=False)
    target_type = db.Column(db.String(40), nullable=False)
    target_id = db.Column(db.Integer, nullable=True)
    detail = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    admin = db.relationship("User", foreign_keys=[admin_id])

    def __repr__(self):
        return f"<AdminAction {self.action}>"


def ensure_referral_code_unique(code: str) -> str:
    """Évite toute collision de code de parrainage."""
    while User.query.filter_by(referral_code=code).first() is not None:
        code = generate_referral_code()
    return code


