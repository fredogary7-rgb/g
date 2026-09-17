from app import create_app

# Point d'entrée WSGI pour les serveurs de production (gunicorn, waitress, etc.).
# Usage local :  python run.py
# Usage prod  :  gunicorn wsgi:app --bind 0.0.0.0:$PORT
app = create_app()
