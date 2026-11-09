-- SchoolPro: schéma Supabase (PostgreSQL), 12 tables
-- Idempotent (IF NOT EXISTS). L'application yخلe9 les tables toute seule au démarrage,
-- donc ce fichier ikhtiyari. Les noms ne rentrent pas en conflit avec l'ancien projet de stock.

CREATE TABLE IF NOT EXISTS ecoles (
    id SERIAL PRIMARY KEY,
    nom TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT 'free',
    annee_scolaire TEXT,
    cree_le TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS utilisateurs (
    id SERIAL PRIMARY KEY,
    nom TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    mot_de_passe TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'admin',
    ecole_id INTEGER NOT NULL REFERENCES ecoles(id),
    cree_le TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS classes (
    id SERIAL PRIMARY KEY,
    nom TEXT NOT NULL,
    niveau TEXT,
    frais_annuels DOUBLE PRECISION DEFAULT 0,
    capacite INTEGER DEFAULT 30,
    ecole_id INTEGER NOT NULL REFERENCES ecoles(id)
);
CREATE TABLE IF NOT EXISTS matieres (
    id SERIAL PRIMARY KEY,
    nom TEXT NOT NULL,
    coefficient DOUBLE PRECISION DEFAULT 1,
    ecole_id INTEGER NOT NULL REFERENCES ecoles(id)
);
CREATE TABLE IF NOT EXISTS enseignants (
    id SERIAL PRIMARY KEY,
    nom TEXT NOT NULL,
    telephone TEXT,
    email TEXT,
    specialite TEXT,
    ecole_id INTEGER NOT NULL REFERENCES ecoles(id)
);
CREATE TABLE IF NOT EXISTS eleves (
    id SERIAL PRIMARY KEY,
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
    cree_le TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS seances (
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
    classe_id INTEGER NOT NULL REFERENCES classes(id),
    matiere_id INTEGER NOT NULL REFERENCES matieres(id),
    titre TEXT NOT NULL,
    type TEXT DEFAULT 'DS',
    trimestre INTEGER NOT NULL DEFAULT 1,
    date_eval TEXT,
    bareme DOUBLE PRECISION NOT NULL DEFAULT 20,
    ecole_id INTEGER NOT NULL REFERENCES ecoles(id)
);
CREATE TABLE IF NOT EXISTS notes (
    id SERIAL PRIMARY KEY,
    evaluation_id INTEGER NOT NULL REFERENCES evaluations(id),
    eleve_id INTEGER NOT NULL REFERENCES eleves(id),
    valeur DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS absences (
    id SERIAL PRIMARY KEY,
    eleve_id INTEGER NOT NULL REFERENCES eleves(id),
    date_abs TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'absence',
    justifiee INTEGER NOT NULL DEFAULT 0,
    motif TEXT,
    user_id INTEGER REFERENCES utilisateurs(id),
    ecole_id INTEGER NOT NULL REFERENCES ecoles(id),
    cree_le TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS paiements (
    id SERIAL PRIMARY KEY,
    numero INTEGER NOT NULL,
    eleve_id INTEGER NOT NULL REFERENCES eleves(id),
    montant DOUBLE PRECISION NOT NULL,
    motif TEXT,
    mode TEXT DEFAULT 'especes',
    date_paiement TEXT NOT NULL,
    statut TEXT NOT NULL DEFAULT 'valide',
    user_id INTEGER REFERENCES utilisateurs(id),
    ecole_id INTEGER NOT NULL REFERENCES ecoles(id),
    cree_le TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS journal_ecole (
    id SERIAL PRIMARY KEY,
    action TEXT NOT NULL,
    detail TEXT,
    user_id INTEGER REFERENCES utilisateurs(id),
    cree_le TIMESTAMPTZ DEFAULT now(),
    ecole_id INTEGER NOT NULL REFERENCES ecoles(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_notes ON notes(evaluation_id, eleve_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_eleves_num ON eleves(ecole_id, numero);
CREATE UNIQUE INDEX IF NOT EXISTS ux_paiements_num ON paiements(ecole_id, numero);
CREATE INDEX IF NOT EXISTS idx_eleves_ecole ON eleves(ecole_id);
CREATE INDEX IF NOT EXISTS idx_absences_ecole ON absences(ecole_id);
CREATE INDEX IF NOT EXISTS idx_journal_ecole ON journal_ecole(ecole_id);

-- Sécurité Supabase: RLS actif sans policy = l'API publique (anon key) ma tشouf chay.
-- L'application tconnecti b rôle postgres (BYPASSRLS), donc tkhdem normalement.
ALTER TABLE ecoles ENABLE ROW LEVEL SECURITY;
ALTER TABLE utilisateurs ENABLE ROW LEVEL SECURITY;
ALTER TABLE classes ENABLE ROW LEVEL SECURITY;
ALTER TABLE matieres ENABLE ROW LEVEL SECURITY;
ALTER TABLE enseignants ENABLE ROW LEVEL SECURITY;
ALTER TABLE eleves ENABLE ROW LEVEL SECURITY;
ALTER TABLE seances ENABLE ROW LEVEL SECURITY;
ALTER TABLE evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE absences ENABLE ROW LEVEL SECURITY;
ALTER TABLE paiements ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal_ecole ENABLE ROW LEVEL SECURITY;
