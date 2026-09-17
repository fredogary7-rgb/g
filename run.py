"""Point d'entrée de l'application FANTA."""
from app import create_app

app = create_app()

if __name__ == "__main__":
    # host=0.0.0.0 pour tester depuis un mobile sur le même réseau local.
    app.run(debug=True, host="0.0.0.0", port=5000)
