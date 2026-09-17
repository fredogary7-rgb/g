"""Test fonctionnel de bout en bout de l'application FANTA.

Lancement :  python tests/smoke_test.py
Utilise une base SQLite temporaire et désactive le CSRF pour simplifier
les tests d'intégration (le CSRF est vérifié séparément).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Commission, Deposit, Product, Purchase, User, Withdrawal
from app.seed_data import PRODUCTS_SEED


class TestConfig:
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///test_fanta.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED = False
    APP_NAME = "FANTA"
    CURRENCY = "FCFA"
    PAYMENT_MODE = "sandbox"
    PAYMENT_METHODS = ["Orange Money", "MTN Mobile Money", "Moov Money", "Wave"]
    WITHDRAWAL_METHODS = ["Orange Money", "MTN Mobile Money", "Moov Money", "Wave", "Banque"]
    REFERRAL_LEVEL_1 = 0.18
    REFERRAL_LEVEL_2 = 0.02
    REFERRAL_LEVEL_3 = 0.01
    REFERRAL_LEVELS = [0.18, 0.02, 0.01]


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
    admin = User(username="admin", email="admin@fanta.app", is_admin=True, referral_code="ADMIN0001")
    admin.set_password("admin123")
    db.session.add(admin)
    db.session.commit()


def register(username, ref=None):
    # Client frais : l'inscription redirige si un utilisateur est déjà connecté.
    c = app.test_client()
    data = dict(username=username, phone="+226 70 12 34 56", country="Burkina Faso",
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
check("CSRF token présent dans le formulaire", b"csrf_token" in client.get("/inscription").data)

# --- Inscription (chaîne A -> B -> C -> D) ---
check("Inscription A -> 302", register("alice").status_code == 302)
with app.app_context():
    a_code = User.query.filter_by(username="alice").first().referral_code

check("Inscription B parrainé par A -> 302", register("bob", a_code).status_code == 302)
with app.app_context():
    b_code = User.query.filter_by(username="bob").first().referral_code

check("Inscription C parrainé par B -> 302", register("carol", b_code).status_code == 302)
with app.app_context():
    c_code = User.query.filter_by(username="carol").first().referral_code

check("Inscription D parrainé par C -> 302", register("dave", c_code).status_code == 302)
with app.app_context():
    d = User.query.filter_by(username="dave").first()
    check("D -> niveau 1 = C", d.referrer.username == "carol")
    check("D -> niveau 2 = B", d.referrer.referrer.username == "bob")
    check("D -> niveau 3 = A", d.referrer.referrer.referrer.username == "alice")

# --- Connexion / pages membres ---
check("Connexion D -> 302", login("dave").status_code == 302)
for path in ["/dashboard", "/produits", "/produit/1", "/produit/1/confirmation",
             "/portefeuille", "/historique", "/equipe", "/parrainage",
             "/profil", "/parametres", "/notifications"]:
    check(f"GET {path} -> 200", client.get(path).status_code == 200)


# --- Dépôt sandbox (D) ---
check("POST /depot -> 302", client.post("/depot", data=dict(amount="4000", method="Orange Money"),
                                        follow_redirects=False).status_code == 302)
with app.app_context():
    dep = Deposit.query.filter_by(user_id=d.id).first()
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
    d = User.query.filter_by(username="dave").first()
    check("Solde D crédité de 4000", float(d.balance) == 4000.0)

# --- D achète le produit 1 ---
logout()
login("dave")
check("POST /produit/1/confirmation -> 302",
      client.post("/produit/1/confirmation", follow_redirects=False).status_code == 302)

with app.app_context():
    purchase = Purchase.query.filter_by(user_id=d.id).first()
    check("Achat enregistré", purchase is not None)
    d = User.query.filter_by(username="dave").first()
    check("Solde D débité (0)", float(d.balance) == 0.0)

    commissions = Commission.query.filter_by(purchase_id=purchase.id).order_by(Commission.level).all()
    check("3 commissions créées (pas de doublon)", len(commissions) == 3)
    if len(commissions) == 3:
        check("N1 -> bénéficiaire C", commissions[0].level == 1 and commissions[0].beneficiary.username == "carol")
        check("N1 -> taux 18%", float(commissions[0].rate) == 0.18)
        check("N1 -> montant 720", float(commissions[0].amount) == 720.0)
        check("N2 -> bénéficiaire B", commissions[1].level == 2 and commissions[1].beneficiary.username == "bob")
        check("N3 -> bénéficiaire A", commissions[2].level == 3 and commissions[2].beneficiary.username == "alice")

# --- Approuver une commission ---
with app.app_context():
    comm_id = Commission.query.filter_by(purchase_id=purchase.id, level=1).first().id
logout()
login("admin", "admin123")
client.post(f"/admin/commissions/{comm_id}/approve", follow_redirects=False)
with app.app_context():
    comm = db.session.get(Commission, comm_id)
    check("Commission approuvée", comm.status == "approved")
    c = User.query.filter_by(username="carol").first()
    check("Solde C crédité de 720", float(c.balance) == 720.0)

# --- Retrait complet : création + rejet (carol dispose de 720 FCFA) ---
logout()
login("carol")
check("POST /retrait (carol, 200) -> 302", client.post("/retrait",
     data=dict(amount="200", method="Orange Money", destination="0700000001"),
     follow_redirects=False).status_code == 302)
with app.app_context():
    carol = User.query.filter_by(username="carol").first()
    wd = Withdrawal.query.filter_by(user_id=carol.id).first()
    check("Retrait pending créé", wd is not None and wd.status == "pending")
    check("Solde carol immobilisé (520)", float(carol.balance) == 520.0)
    wd_id = wd.id
logout()
login("admin", "admin123")
check("Admin rejette retrait -> 302", client.post(f"/admin/withdrawals/{wd_id}/reject",
     follow_redirects=False).status_code == 302)
with app.app_context():
    wd = db.session.get(Withdrawal, wd_id)
    check("Retrait rejeté", wd.status == "rejected")
    carol = User.query.filter_by(username="carol").first()
    check("Solde carol recrédité (720)", float(carol.balance) == 720.0)

# --- Retrait (solde insuffisant : re-rendu du formulaire avec erreur) ---
logout()
login("dave")
check("POST /retrait (solde insuffisant) -> 200", client.post("/retrait",
     data=dict(amount="99999", method="Orange Money", destination="0700000000"),
     follow_redirects=False).status_code == 200)

# --- Admin : pages protégées ---
logout()
login("dave")
check("GET /admin (non-admin) -> 403", client.get("/admin").status_code == 403)
logout()
login("admin", "admin123")
for path in ["/admin", "/admin/users", "/admin/products", "/admin/deposits",
             "/admin/withdrawals", "/admin/commissions", "/admin/transactions", "/admin/actions"]:
    check(f"GET {path} -> 200", client.get(path).status_code == 200)

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
print("Tous les tests passent ✓")


