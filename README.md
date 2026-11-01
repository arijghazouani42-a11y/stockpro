# StockPro · Gestion de stock (SaaS)

Fonctionnalités: produits, catégories, fournisseurs, mouvements (entrées/sorties), ventes + factures imprimables,
clients, commandes fournisseurs (réception = stock), inventaire physique, import/export CSV, rapports,
équipe (rôles admin/employé), journal d'activité, plans Free/Pro, dark mode.

Flask + Supabase (PostgreSQL). Sans configuration, l'application utilise SQLite (`stock.db`).

## Lancer
```
pip install -r requirements.txt
python run.py
```
Puis ouvrir http://127.0.0.1:5000

## Connecter Supabase
1. supabase.com > New project (garder le mot de passe de la base).
2. Project Settings > Database > Connection string > URI (Session pooler).
3. Copier `.env.example` en `.env`, coller l'URL dans `DATABASE_URL` (remplacer [YOUR-PASSWORD]).
4. `python check_db.py` pour tester la connexion, puis `python run.py`.

## Structure
```
run.py                 point d'entrée
config.py              configuration (.env)
check_db.py            test de connexion à la base
supabase_schema.sql    schéma PostgreSQL (RLS activé)
app/
  __init__.py          create_app, CSRF, filtres
  db.py                couche base de données (Supabase / SQLite)
  auth.py              inscription, login, profil, équipe
  main.py              landing, dashboard, rapports
  produits.py          CRUD produits, export CSV
  referentiels.py      catégories, fournisseurs
  mouvements.py        entrées / sorties, export CSV
  ventes.py            ventes + factures
  commandes.py         bons de commande fournisseurs
  inventaire.py        inventaire physique
  import_csv.py        import CSV de produits
  journal.py           journal d'activité
  abonnement.py        plans Free / Pro
  templates/  static/
```
