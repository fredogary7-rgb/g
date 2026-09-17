"""Test fonctionnel de bout en bout de l'application FANTA.

Lancement :  python tests/smoke_test.py
Base SQLite temporaire ; CSRF désactivé pour les tests d'intégration.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Commission, Deposit, Product, Purchase, User, Withdrawal
from app.seed_data import PRODUCTS_SEED

PHONE = {"alice": "70100001", "bob": "70100002", "carol": "70100003", "dave": "70100004"}


class TestConfig:
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///test_fanta.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED = False
    APP_NAME = "FANTA"
    CURRENCY = "FCFA"
    PAYMENT_MODE = "sandbox"
    PAYMENT_METHODS = ["Orange Money"]
    WITHDRAWAL_METHODS = ["Orange Money", "MTN Mobile Money", "Moov Money", "Wave", "Banque"]
    REFERRAL_LEVEL_1 = 0.18
    REFERRAL_LEVEL_2 = 0.02
    REFERRAL_LEVEL_3 = 0.01
    REFERRAL_LEVELS = [0.18, 0.02, 0.01]
    COUNTRIES = ["Burkina Faso"]
    AUTO_INIT_DB = False


app = create_app(TestConfig)
client = app.test_client()
results = []


def check(label, condition):
    results.append((label, bool(condition)))
    print(("PASS" if condition else "FAIL") + "  " + label)


with app.app_context():
    db.drop_all()
    db.create_all()
    for data in PRODUCTS_SEED:
        db.session.add(Product(**data))
    admin = User(username="admin", phone="70000000", email="admin@fanta.app",
                 is_admin=True, referral_code="ADMIN0001")
    admin.set_password("admin123")
    db.session.add(admin)
    db.session.commit()


def register(phone, ref=None):
    c = app.test_client()
    data = dict(phone=phone, country="Burkina Faso",
                password="secret123", confirm_password="secret123", accept="1")
    if ref:
        data["referral_code"] = ref
    return c.post("/inscription", data=data, follow_redirects=False)


def login(identifier, password="secret123"):
    return client.post("/connexion", data=dict(identifier=identifier, password=password),
                       follow_redirects=False)


def logout():
    return client.post("/deconnexion", follow_redirects=False)


# --- Pages publiques ---
check("GET / (accueil) -> 200", client.get("/").status_code == 200)
check("GET /inscription -> 200", client.get("/inscription").status_code == 200)
check("GET /connexion -> 200", client.get("/connexion").status_code == 200)
check("CSRF token présent", b"csrf_token" in client.get("/inscription").data)

# --- Inscription (alice -> bob -> carol -> dave) ---
check("Inscription alice -> 302", register(PHONE["alice"]).status_code == 302)
with app.app_context():
    a_code = User.query.filter_by(phone=PHONE["alice"]).first().referral_code

check("Inscription bob -> 302", register(PHONE["bob"], a_code).status_code == 302)
with app.app_context():
    b_code = User.query.filter_by(phone=PHONE["bob"]).first().referral_code

check("Inscription carol -> 302", register(PHONE["carol"], b_code).status_code == 302)
with app.app_context():
    c_code = User.query.filter_by(phone=PHONE["carol"]).first().referral_code

check("Inscription dave -> 302", register(PHONE["dave"], c_code).status_code == 302)
with app.app_context():
    d = User.query.filter_by(phone=PHONE["dave"]).first()
    check("dave -> niveau 1 = carol", d.referrer.phone == PHONE["carol"])
    check("dave -> niveau 2 = bob", d.referrer.referrer.phone == PHONE["bob"])
    check("dave -> niveau 3 = alice", d.referrer.referrer.referrer.phone == PHONE["alice"])


# --- Connexion / pages membres ---
check("Connexion dave -> 302", login(PHONE["dave"]).status_code == 302)
for path in ["/dashboard", "/produits", "/produit/1", "/produit/1/confirmation",
             "/portefeuille", "/historique", "/equipe", "/parrainage",
             "/profil", "/parametres", "/notifications"]:
    check(f"GET {path} -> 200", client.get(path).status_code == 200)

# --- Dépôt manuel Orange Money (dave) ---
check("POST /depot -> 200 (instructions)", client.post("/depot",
      data=dict(amount="8000", method="Orange Money", phone="70123456"),
      follow_redirects=False).status_code == 200)
with app.app_context():
    dave = User.query.filter_by(phone=PHONE["dave"]).first()
    dep = Deposit.query.filter_by(user_id=dave.id).first()
    check("Dépôt créé au statut pending", dep is not None and dep.status == "pending")
    dep_id = dep.id

# --- Admin approuve le dépôt ---
logout()
login("admin", "admin123")
check("Admin approuve dépôt -> 302", client.post(f"/admin/deposits/{dep_id}/approve",
     follow_redirects=False).status_code == 302)
with app.app_context():
    dep = db.session.get(Deposit, dep_id)
    check("Dépôt approuvé", dep.status == "approved")
    dave = User.query.filter_by(phone=PHONE["dave"]).first()
    check("Solde dave = 8000", float(dave.balance) == 8000.0)

# --- dave achète le produit 1 (Fanta 2 = 8000) ---
logout()
login(PHONE["dave"])
check("POST /produit/1/confirmation -> 302",
      client.post("/produit/1/confirmation", follow_redirects=False).status_code == 302)
with app.app_context():
    dave = User.query.filter_by(phone=PHONE["dave"]).first()
    purchase = Purchase.query.filter_by(user_id=dave.id).first()
    check("Achat enregistré", purchase is not None)
    check("Solde dave débité (0)", float(dave.balance) == 0.0)
    purchase_id = purchase.id

    commissions = Commission.query.filter_by(purchase_id=purchase.id).order_by(Commission.level).all()
    check("3 commissions créées (pas de doublon)", len(commissions) == 3)
    if len(commissions) == 3:
        check("N1 -> bénéficiaire carol", commissions[0].level == 1 and commissions[0].beneficiary.phone == PHONE["carol"])
        check("N1 -> taux 18%", float(commissions[0].rate) == 0.18)
        check("N1 -> montant 1440", float(commissions[0].amount) == 1440.0)
        check("N2 -> bénéficiaire bob", commissions[1].level == 2 and commissions[1].beneficiary.phone == PHONE["bob"])
        check("N3 -> bénéficiaire alice", commissions[2].level == 3 and commissions[2].beneficiary.phone == PHONE["alice"])

# --- Approuver une commission ---
with app.app_context():
    comm_id = Commission.query.filter_by(purchase_id=purchase_id, level=1).first().id
logout()
login("admin", "admin123")
client.post(f"/admin/commissions/{comm_id}/approve", follow_redirects=False)
with app.app_context():
    comm = db.session.get(Commission, comm_id)
    check("Commission approuvée", comm.status == "approved")
    carol = User.query.filter_by(phone=PHONE["carol"]).first()
    check("Solde carol = 1440", float(carol.balance) == 1440.0)


# --- Retrait : création + rejet (carol dispose de 1440) ---
logout()
login(PHONE["carol"])
check("POST /retrait (carol, 200) -> 302", client.post("/retrait",
     data=dict(amount="200", method="Orange Money", destination="0700000001"),
     follow_redirects=False).status_code == 302)
with app.app_context():
    carol = User.query.filter_by(phone=PHONE["carol"]).first()
    wd = Withdrawal.query.filter_by(user_id=carol.id).first()
    check("Retrait pending créé", wd is not None and wd.status == "pending")
    check("Solde carol immobilisé (1240)", float(carol.balance) == 1240.0)
    wd_id = wd.id
logout()
login("admin", "admin123")
check("Admin rejette retrait -> 302", client.post(f"/admin/withdrawals/{wd_id}/reject",
     follow_redirects=False).status_code == 302)
with app.app_context():
    wd = db.session.get(Withdrawal, wd_id)
    check("Retrait rejeté", wd.status == "rejected")
    carol = User.query.filter_by(phone=PHONE["carol"]).first()
    check("Solde carol recrédité (1440)", float(carol.balance) == 1440.0)

# --- Retrait (solde insuffisant) ---
logout()
login(PHONE["dave"])
check("POST /retrait (solde insuffisant) -> 200", client.post("/retrait",
     data=dict(amount="99999", method="Orange Money", destination="0700000000"),
     follow_redirects=False).status_code == 200)

# --- Admin : pages protégées ---
logout()
login(PHONE["dave"])
check("GET /admin (non-admin) -> 403", client.get("/admin").status_code == 403)
logout()
login("admin", "admin123")
for path in ["/admin", "/admin/users", "/admin/products", "/admin/deposits",
             "/admin/withdrawals", "/admin/commissions", "/admin/transactions", "/admin/actions"]:
    check(f"GET {path} -> 200", client.get(path).status_code == 200)

# --- Actions admin : créditer / débiter / nommer admin ---
with app.app_context():
    dave_id = User.query.filter_by(phone=PHONE["dave"]).first().id
    bob_id = User.query.filter_by(phone=PHONE["bob"]).first().id

check("Admin crédite dave +5000 -> 302", client.post(f"/admin/users/{dave_id}/credit",
     data=dict(amount="5000"), follow_redirects=False).status_code == 302)
with app.app_context():
    dave = User.query.filter_by(phone=PHONE["dave"]).first()
    check("Solde dave = 5000", float(dave.balance) == 5000.0)

check("Admin débite dave -2000 -> 302", client.post(f"/admin/users/{dave_id}/debit",
     data=dict(amount="2000"), follow_redirects=False).status_code == 302)
with app.app_context():
    dave = User.query.filter_by(phone=PHONE["dave"]).first()
    check("Solde dave = 3000", float(dave.balance) == 3000.0)

check("Admin nomme bob admin -> 302", client.post(f"/admin/users/{bob_id}/toggle-admin",
     follow_redirects=False).status_code == 302)
with app.app_context():
    bob = User.query.filter_by(phone=PHONE["bob"]).first()
    check("bob est administrateur", bob.is_admin is True)

check("GET /produit/9999 -> 404", client.get("/produit/9999").status_code == 404)

# --- Bilan ---
failed = [label for label, ok in results if not ok]
print("\n----------------------------------------")
print(f"Résultat : {len(results) - len(failed)}/{len(results)} tests OK")
if failed:
    print("Échecs :")
    for f in failed:
        print("  - " + f)
    sys.exit(1)
print("Tous les tests passent")
