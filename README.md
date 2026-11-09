# SchoolPro · Gestion d'école (SaaS)

Flask + Supabase (PostgreSQL). Sans configuration, l'application utilise SQLite (`ecole.db`).

Fonctionnalités: élèves, classes, matières, enseignants, notes et bulletins (moyennes pondérées, rang),
absences et alertes, emploi du temps (détection de conflits), frais de scolarité (reçus, impayés),
équipe avec rôles (admin / secrétaire / enseignant), journal d'activité, import/export CSV,
rapports, plans Free/Pro, dark mode.

## Lancer
    pip install -r requirements.txt
    python run.py
Puis http://127.0.0.1:5000

## Supabase
Copier `.env.example` en `.env`, renseigner `DATABASE_URL` (Session pooler), puis `python check_db.py`.

## Déploiement (Render)
Build: `pip install -r requirements.txt` · Start: `gunicorn wsgi:app`
Variables: `SECRET_KEY`, `DATABASE_URL`.

## Structure
    run.py / wsgi.py / config.py / check_db.py
    app/  __init__ db utils calculs auth main referentiels eleves emploi notes absences paiements abonnement journal
          templates/  static/
