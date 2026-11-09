"""Couche base de données: Supabase (PostgreSQL) ken DATABASE_URL mawjoud, sinon SQLite.
Les tables de SchoolPro ont des noms propres (ecoles, utilisateurs, eleves...) pour ne pas
se mélanger avec d'autres projets dans la même base Supabase."""
import re
import sqlite3
from flask import current_app, g

SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS ecoles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT 'free',
    annee_scolaire TEXT,
    cree_le TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS utilisateurs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    mot_de_passe TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'admin',
    ecole_id INTEGER NOT NULL REFERENCES ecoles(id),
    cree_le TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    niveau TEXT,
    frais_annuels REAL DEFAULT 0,
    capacite INTEGER DEFAULT 30,
    ecole_id INTEGER NOT NULL REFERENCES ecoles(id)
);
CREATE TABLE IF NOT EXISTS matieres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    coefficient REAL DEFAULT 1,
    ecole_id INTEGER NOT NULL REFERENCES ecoles(id)
);
CREATE TABLE IF NOT EXISTS enseignants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    telephone TEXT,
    email TEXT,
    specialite TEXT,
    ecole_id INTEGER NOT NULL REFERENCES ecoles(id)
);
CREATE TABLE IF NOT EXISTS eleves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero INTEGER NOT NULL,
    matricule TEXT,
    nom TEXT NOT NULL,
    prenom TEXT NOT NULL,
    date_naissance TEXT,
    sexe TEXT,
    classe_id INTEGER REFERENCES classes(id),
    parent_nom TEXT,
    parent_tel TEXT,
    email TEXT,
    adresse TEXT,
    statut TEXT NOT NULL DEFAULT 'actif',
    ecole_id INTEGER NOT NULL REFERENCES ecoles(id),
    cree_le TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS seances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    classe_id INTEGER NOT NULL REFERENCES classes(id),
    matiere_id INTEGER NOT NULL REFERENCES matieres(id),
    enseignant_id INTEGER REFERENCES enseignants(id),
    jour INTEGER NOT NULL,
    debut TEXT NOT NULL,
    fin TEXT NOT NULL,
    salle TEXT,
    ecole_id INTEGER NOT NULL REFERENCES ecoles(id)
);
CREATE TABLE IF NOT EXISTS evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    classe_id INTEGER NOT NULL REFERENCES classes(id),
    matiere_id INTEGER NOT NULL REFERENCES matieres(id),
    titre TEXT NOT NULL,
    type TEXT DEFAULT 'DS',
    trimestre INTEGER NOT NULL DEFAULT 1,
    date_eval TEXT,
    bareme REAL NOT NULL DEFAULT 20,
    ecole_id INTEGER NOT NULL REFERENCES ecoles(id)
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_id INTEGER NOT NULL REFERENCES evaluations(id),
    eleve_id INTEGER NOT NULL REFERENCES eleves(id),
    valeur REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS absences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    eleve_id INTEGER NOT NULL REFERENCES eleves(id),
    date_abs TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'absence',
    justifiee INTEGER NOT NULL DEFAULT 0,
    motif TEXT,
    user_id INTEGER REFERENCES utilisateurs(id),
    ecole_id INTEGER NOT NULL REFERENCES ecoles(id),
    cree_le TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS paiements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero INTEGER NOT NULL,
    eleve_id INTEGER NOT NULL REFERENCES eleves(id),
    montant REAL NOT NULL,
    motif TEXT,
    mode TEXT DEFAULT 'especes',
    date_paiement TEXT NOT NULL,
    statut TEXT NOT NULL DEFAULT 'valide',
    user_id INTEGER REFERENCES utilisateurs(id),
    ecole_id INTEGER NOT NULL REFERENCES ecoles(id),
    cree_le TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS journal_ecole (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    detail TEXT,
    user_id INTEGER REFERENCES utilisateurs(id),
    cree_le TEXT DEFAULT CURRENT_TIMESTAMP,
    ecole_id INTEGER NOT NULL REFERENCES ecoles(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_notes ON notes(evaluation_id, eleve_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_eleves_num ON eleves(ecole_id, numero);
CREATE UNIQUE INDEX IF NOT EXISTS ux_paiements_num ON paiements(ecole_id, numero);
CREATE INDEX IF NOT EXISTS idx_eleves_ecole ON eleves(ecole_id);
CREATE INDEX IF NOT EXISTS idx_absences_ecole ON absences(ecole_id);
CREATE INDEX IF NOT EXISTS idx_journal_ecole ON journal_ecole(ecole_id);
"""

TABLES = re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", SCHEMA_SQLITE)

# Schéma PostgreSQL = même schéma, types adaptés
SCHEMA_PG = (SCHEMA_SQLITE
             .replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
             .replace("cree_le TEXT DEFAULT CURRENT_TIMESTAMP", "cree_le TIMESTAMPTZ DEFAULT now()")
             .replace(" REAL", " DOUBLE PRECISION"))
SCHEMA_PG += ("\n-- Sécurité Supabase: RLS actif sans policy = l'API publique (anon key) ma tشouf chay.\n"
              "-- L'application tconnecti b rôle postgres (BYPASSRLS), donc tkhdem normalement.\n"
              + "".join(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;\n" for t in TABLES))


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
