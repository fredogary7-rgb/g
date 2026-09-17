# FANTA

Application web **mobile-first** de démonstration (Python + Flask + PostgreSQL),
avec l'univers visuel Fanta (orange / jaune / blanc / anthracite).

> ⚠️ **Avertissement** : FANTA est une application **indépendante de démonstration**.
> Elle n'est ni affiliée ni approuvée par la marque Fanta® ni par The Coca-Cola Company.
> Les dépôts/retraits fonctionnent en **mode sandbox** : aucun argent réel n'est déplacé.

## Fonctionnalités

Inscription / connexion / déconnexion · tableau de bord · catalogue produits ·
détail & confirmation · portefeuille (dépôt, retrait, historique) · équipe &
parrainage à 3 niveaux (18 % / 2 % / 1 %) · notifications · profil · paramètres ·
espace administrateur (utilisateurs, produits, dépôts, retraits, commissions,
transactions, journal).

## Stack

- Python 3.12 · Flask · Flask-SQLAlchemy · Flask-Login · Flask-WTF (CSRF)
- PostgreSQL (Neon) via `psycopg2-binary` · Jinja2 · Werkzeug · python-dotenv

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

## Configuration

1. Copiez `.env.example` vers `.env`.
2. Renseignez :
   - `DATABASE_URL=`  → votre URL Neon PostgreSQL
   - `SECRET_KEY=`    → `python -c "import secrets; print(secrets.token_hex(32))"`
   - `PAYMENT_MODE=sandbox` (ne pas passer en `live` sans prestataire branché)
   - `ADMIN_PASSWORD=` (optionnel, pour `flask seed`)

> Note Neon : le paramètre `channel_binding=require` présent dans certaines URL
> Neon est retiré automatiquement par `config.py` (non reconnu par psycopg2).
> Le SSL reste assuré par `sslmode=require`.

## Première initialisation

```bash
python -m flask --app run.py init-db     # crée les tables
python -m flask --app run.py seed        # insère les 8 produits + le compte admin
python run.py                             # lance le serveur (http://localhost:5000)
```

Compte administrateur créé par `seed` : **admin** / **Admin@1234** (changez-le !).

## Commandes CLI

| Commande | Rôle |
| --- | --- |
| `flask --app run.py init-db` | Créer les tables |
| `flask --app run.py seed` | Insérer produits + admin |
| `flask --app run.py process-income` | Créditer un jour de revenu aux produits actifs |

## Déploiement en production

L'application est prête pour **Render**, **Railway**, **Fly.io**, **Koyeb**, etc.

- **Serveur WSGI** : `gunicorn` (installé automatiquement hors Windows grâce à
  `requirements.txt`). Point d'entrée : `entrypoint.py` (le port est lu en
  Python via `PORT`, donc pas de souci d'expansion `$PORT`).
- **Commande de démarrage** (ou `Procfile`) :
  `python entrypoint.py`
- **Docker** : un `Dockerfile` + `.dockerignore` sont fournis.

Variables d'environnement requises sur l'hébergeur :

| Variable | Rôle |
| --- | --- |
| `DATABASE_URL` | URL PostgreSQL Neon |
| `SECRET_KEY` | chaîne longue et aléatoire |
| `PAYMENT_MODE` | `sandbox` (défaut) |
| `ADMIN_PASSWORD` | (recommandé) crée le compte admin au démarrage |
| `ADMIN_USERNAME` / `ADMIN_EMAIL` | identifiants admin (défaut `admin` / `admin@fanta.app`) |

> Au démarrage, l'app crée **automatiquement** les tables manquantes et insère
> les 8 produits si la base est vide (`AUTO_INIT_DB=True`). Aucune table
> existante n'est supprimée. Le compte admin n'est créé que si
> `ADMIN_PASSWORD` est défini.

### Railway (recommandé)

Un fichier `railway.json` est fourni : il force la commande `python entrypoint.py`
(port résolu en Python) et utilise Nixpacks. Déployez simplement le dépôt.

Si l'erreur `'$PORT' n'est pas un numéro de port valide` persiste :

1. Ouvrez votre service sur Railway → onglet **Settings**.
2. Rubrique **Deploy** → **Start Command** : mettez `python entrypoint.py`
   (ou videz le champ pour que le `Procfile` du dépôt soit utilisé).
3. Lancez un **nouveau déploiement** (bouton Deploy, pas un simple restart)
   pour reconstruire l'image avec les nouveaux fichiers.

## Tests

```bash
python tests/smoke_test.py   # 50 tests de bout en bout
```

## Notes importantes

- **Parrainage** : taux centralisés dans `config.py` (`REFERRAL_LEVEL_1..3`).
  Hiérarchie D → C (N1, 18 %) → B (N2, 2 %) → A (N3, 1 %). Anti-doublon inclus.
- **Produit « Fanta 2 »** : 980 × 35 = 34 300 FCFA, mais la valeur fournie est
  32 100 FCFA. Les deux valeurs sont configurables ; la valeur stockée par défaut
  est celle fournie (32 100), modifiable depuis Admin → Produits.
- **Images** : les visuels `app/static/images/*.svg` sont des *placeholders* de la
  marque. Remplacez-les par vos vraies photos Fanta (mêmes noms de fichiers, ou
  adaptez le champ `image` des produits).
- **Paiement** : `app/services/payment_service.py` expose une interface
  `PaymentProvider`. Le prestataire réel (API/clé/token/URL) viendra s'y brancher
  plus tard ; les secrets resteront dans `.env`.

## Structure

```
app/
  __init__.py          # factory + filtres + handlers + CSRF + login
  models.py            # modèles SQLAlchemy
  routes/              # auth, main, wallet, team, account, admin
  services/            # payment, withdrawal, referral, finance, income, notification
  templates/           # base, auth, dashboard, produits, admin, erreurs…
  static/              # css, js, images
config.py              # configuration + normalisation URL Neon
run.py                 # point d'entrée
tests/smoke_test.py    # tests fonctionnels
```
