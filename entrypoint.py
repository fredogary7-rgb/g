"""Point d'entrée de production.

Lance gunicorn en lisant le port depuis la variable d'environnement ``PORT``
(8000 par défaut). Résout le port **en Python**, ce qui évite tout problème
d'expansion de ``$PORT`` par le shell sur Render, Railway, Koyeb, Fly.io, etc.

Usage (production) :  python entrypoint.py
"""
import os

from gunicorn.app.wsgiapp import WSGIApplication


class FantaServer(WSGIApplication):
    def __init__(self, app_uri, options=None):
        self.options = options or {}
        self.app_uri = app_uri
        super().__init__()

    def load_config(self):
        config = {
            key: value
            for key, value in self.options.items()
            if key in self.cfg.settings and value is not None
        }
        for key, value in config.items():
            self.cfg.set(key.lower(), value)


def main():
    port = os.environ.get("PORT", "8000")
    workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
    options = {
        "bind": f"0.0.0.0:{port}",
        "workers": workers,
        "timeout": 120,
        "accesslog": "-",
        "errorlog": "-",
    }
    FantaServer("wsgi:app", options).run()


if __name__ == "__main__":
    main()
