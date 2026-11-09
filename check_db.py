"""Test el connexion lel base: python check_db.py"""
from app import create_app
from app.db import connect, init_db

app = create_app()
with app.app_context():
    print("Base:", app.config["DB_LABEL"])
    try:
        init_db(app)
        db = connect()
        n = db.one("SELECT COUNT(*) AS n FROM ecoles")["n"]
        print(f"OK: connexion réussie, {n} école(s) dans la base.")
        db.close()
    except Exception as e:
        print("ERREUR de connexion:\n", e)
        print("\nVérifie DATABASE_URL dans .env (mot de passe, URL pooler).")
