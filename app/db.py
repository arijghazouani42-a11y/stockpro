"""Couche base de données: Supabase (PostgreSQL) ken DATABASE_URL mawjoud, sinon SQLite."""
import sqlite3
from flask import current_app, g

SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS organisations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT 'free',
    cree_le TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    mot_de_passe TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'admin',
    organisation_id INTEGER NOT NULL REFERENCES organisations(id),
    cree_le TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    organisation_id INTEGER NOT NULL REFERENCES organisations(id)
);
CREATE TABLE IF NOT EXISTS fournisseurs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    telephone TEXT,
    email TEXT,
    organisation_id INTEGER NOT NULL REFERENCES organisations(id)
);
CREATE TABLE IF NOT EXISTS produits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    reference TEXT,
    prix_achat REAL DEFAULT 0,
    prix_vente REAL DEFAULT 0,
    quantite INTEGER DEFAULT 0,
    seuil_alerte INTEGER DEFAULT 5,
    categorie_id INTEGER REFERENCES categories(id),
    fournisseur_id INTEGER REFERENCES fournisseurs(id),
    organisation_id INTEGER NOT NULL REFERENCES organisations(id),
    cree_le TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS mouvements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produit_id INTEGER NOT NULL REFERENCES produits(id),
    type TEXT NOT NULL,
    quantite INTEGER NOT NULL,
    cree_le TEXT DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER REFERENCES users(id),
    note TEXT,
    organisation_id INTEGER NOT NULL REFERENCES organisations(id)
);
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    telephone TEXT,
    email TEXT,
    adresse TEXT,
    organisation_id INTEGER NOT NULL REFERENCES organisations(id)
);
CREATE TABLE IF NOT EXISTS ventes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero INTEGER NOT NULL,
    client_id INTEGER REFERENCES clients(id),
    statut TEXT NOT NULL DEFAULT 'payee',
    total REAL DEFAULT 0,
    cree_le TEXT DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER REFERENCES users(id),
    organisation_id INTEGER NOT NULL REFERENCES organisations(id)
);
CREATE TABLE IF NOT EXISTS vente_lignes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vente_id INTEGER NOT NULL REFERENCES ventes(id),
    produit_id INTEGER NOT NULL REFERENCES produits(id),
    quantite INTEGER NOT NULL,
    prix_unitaire REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS commandes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero INTEGER NOT NULL,
    fournisseur_id INTEGER REFERENCES fournisseurs(id),
    statut TEXT NOT NULL DEFAULT 'brouillon',
    total REAL DEFAULT 0,
    cree_le TEXT DEFAULT CURRENT_TIMESTAMP,
    recue_le TEXT,
    user_id INTEGER REFERENCES users(id),
    organisation_id INTEGER NOT NULL REFERENCES organisations(id)
);
CREATE TABLE IF NOT EXISTS commande_lignes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    commande_id INTEGER NOT NULL REFERENCES commandes(id),
    produit_id INTEGER NOT NULL REFERENCES produits(id),
    quantite INTEGER NOT NULL,
    prix_achat REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    detail TEXT,
    user_id INTEGER REFERENCES users(id),
    cree_le TEXT DEFAULT CURRENT_TIMESTAMP,
    organisation_id INTEGER NOT NULL REFERENCES organisations(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_ventes_num ON ventes(organisation_id, numero);
CREATE UNIQUE INDEX IF NOT EXISTS ux_commandes_num ON commandes(organisation_id, numero);
CREATE INDEX IF NOT EXISTS idx_journal_org ON journal(organisation_id);
CREATE INDEX IF NOT EXISTS idx_produits_org ON produits(organisation_id);
CREATE INDEX IF NOT EXISTS idx_mouvements_org ON mouvements(organisation_id);
"""

SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS organisations (
    id SERIAL PRIMARY KEY,
    nom TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT 'free',
    cree_le TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    nom TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    mot_de_passe TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'admin',
    organisation_id INTEGER NOT NULL REFERENCES organisations(id),
    cree_le TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    nom TEXT NOT NULL,
    organisation_id INTEGER NOT NULL REFERENCES organisations(id)
);
CREATE TABLE IF NOT EXISTS fournisseurs (
    id SERIAL PRIMARY KEY,
    nom TEXT NOT NULL,
    telephone TEXT,
    email TEXT,
    organisation_id INTEGER NOT NULL REFERENCES organisations(id)
);
CREATE TABLE IF NOT EXISTS produits (
    id SERIAL PRIMARY KEY,
    nom TEXT NOT NULL,
    reference TEXT,
    prix_achat DOUBLE PRECISION DEFAULT 0,
    prix_vente DOUBLE PRECISION DEFAULT 0,
    quantite INTEGER DEFAULT 0,
    seuil_alerte INTEGER DEFAULT 5,
    categorie_id INTEGER REFERENCES categories(id),
    fournisseur_id INTEGER REFERENCES fournisseurs(id),
    organisation_id INTEGER NOT NULL REFERENCES organisations(id),
    cree_le TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS mouvements (
    id SERIAL PRIMARY KEY,
    produit_id INTEGER NOT NULL REFERENCES produits(id),
    type TEXT NOT NULL,
    quantite INTEGER NOT NULL,
    cree_le TIMESTAMPTZ DEFAULT now(),
    user_id INTEGER REFERENCES users(id),
    note TEXT,
    organisation_id INTEGER NOT NULL REFERENCES organisations(id)
);
CREATE TABLE IF NOT EXISTS clients (
    id SERIAL PRIMARY KEY,
    nom TEXT NOT NULL,
    telephone TEXT,
    email TEXT,
    adresse TEXT,
    organisation_id INTEGER NOT NULL REFERENCES organisations(id)
);
CREATE TABLE IF NOT EXISTS ventes (
    id SERIAL PRIMARY KEY,
    numero INTEGER NOT NULL,
    client_id INTEGER REFERENCES clients(id),
    statut TEXT NOT NULL DEFAULT 'payee',
    total DOUBLE PRECISION DEFAULT 0,
    cree_le TIMESTAMPTZ DEFAULT now(),
    user_id INTEGER REFERENCES users(id),
    organisation_id INTEGER NOT NULL REFERENCES organisations(id)
);
CREATE TABLE IF NOT EXISTS vente_lignes (
    id SERIAL PRIMARY KEY,
    vente_id INTEGER NOT NULL REFERENCES ventes(id),
    produit_id INTEGER NOT NULL REFERENCES produits(id),
    quantite INTEGER NOT NULL,
    prix_unitaire DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS commandes (
    id SERIAL PRIMARY KEY,
    numero INTEGER NOT NULL,
    fournisseur_id INTEGER REFERENCES fournisseurs(id),
    statut TEXT NOT NULL DEFAULT 'brouillon',
    total DOUBLE PRECISION DEFAULT 0,
    cree_le TIMESTAMPTZ DEFAULT now(),
    recue_le TIMESTAMPTZ,
    user_id INTEGER REFERENCES users(id),
    organisation_id INTEGER NOT NULL REFERENCES organisations(id)
);
CREATE TABLE IF NOT EXISTS commande_lignes (
    id SERIAL PRIMARY KEY,
    commande_id INTEGER NOT NULL REFERENCES commandes(id),
    produit_id INTEGER NOT NULL REFERENCES produits(id),
    quantite INTEGER NOT NULL,
    prix_achat DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS journal (
    id SERIAL PRIMARY KEY,
    action TEXT NOT NULL,
    detail TEXT,
    user_id INTEGER REFERENCES users(id),
    cree_le TIMESTAMPTZ DEFAULT now(),
    organisation_id INTEGER NOT NULL REFERENCES organisations(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_ventes_num ON ventes(organisation_id, numero);
CREATE UNIQUE INDEX IF NOT EXISTS ux_commandes_num ON commandes(organisation_id, numero);
CREATE INDEX IF NOT EXISTS idx_journal_org ON journal(organisation_id);
CREATE INDEX IF NOT EXISTS idx_produits_org ON produits(organisation_id);
CREATE INDEX IF NOT EXISTS idx_mouvements_org ON mouvements(organisation_id);

-- Sécurité Supabase: RLS actif sans policy = l'API publique (anon key) ma tشouf chay.
-- El application tconnecti b rôle postgres (BYPASSRLS), donc tkhdem normalement.
ALTER TABLE organisations ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE fournisseurs ENABLE ROW LEVEL SECURITY;
ALTER TABLE produits ENABLE ROW LEVEL SECURITY;
ALTER TABLE mouvements ENABLE ROW LEVEL SECURITY;
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE ventes ENABLE ROW LEVEL SECURITY;
ALTER TABLE vente_lignes ENABLE ROW LEVEL SECURITY;
ALTER TABLE commandes ENABLE ROW LEVEL SECURITY;
ALTER TABLE commande_lignes ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal ENABLE ROW LEVEL SECURITY;
"""


class Database:
    """Wrapper sghir: nafs el SQL (placeholders `?`) yخdem 3la SQLite w PostgreSQL."""

    def __init__(self, conn, pg):
        self.conn = conn
        self.pg = pg

    def _sql(self, sql):
        return sql.replace("?", "%s") if self.pg else sql

    def query(self, sql, params=()):
        return self.conn.execute(self._sql(sql), tuple(params)).fetchall()

    def one(self, sql, params=()):
        return self.conn.execute(self._sql(sql), tuple(params)).fetchone()

    def execute(self, sql, params=()):
        return self.conn.execute(self._sql(sql), tuple(params))

    def insert(self, sql, params=()):
        """INSERT w yرجّa3 el id jdid."""
        if self.pg:
            cur = self.conn.execute(self._sql(sql) + " RETURNING id", tuple(params))
            return cur.fetchone()["id"]
        return self.conn.execute(sql, tuple(params)).lastrowid

    def il_y_a(self, jours):
        """Expression SQL 'maintenant - N jours' (compatible zouz bases)."""
        jours = int(jours)
        if self.pg:
            return f"(now() - interval '{jours} days')"
        return f"datetime('now','-{jours} days')"

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()


def connect():
    cfg = current_app.config
    if cfg["DATABASE_URL"]:
        import psycopg
        from psycopg.rows import dict_row
        conn = psycopg.connect(cfg["DATABASE_URL"], row_factory=dict_row,
                               connect_timeout=15, prepare_threshold=None)
        return Database(conn, pg=True)
    conn = sqlite3.connect(cfg["SQLITE_PATH"])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return Database(conn, pg=False)


def get_db():
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    """Yخلe9 el tables ken mawjoudin (IF NOT EXISTS)."""
    with app.app_context():
        db = connect()
        if db.pg:
            db.conn.execute(SCHEMA_PG)
        else:
            db.conn.executescript(SCHEMA_SQLITE)
        db.commit()
        db.close()
