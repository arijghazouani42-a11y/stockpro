-- StockPro: schéma Supabase (PostgreSQL), 12 tables
-- Idempotent (IF NOT EXISTS): tnجem tعawedou kol mara.
-- L'application yخلe9 les tables toute seule au démarrage (python run.py),
-- donc ce fichier ikhtiyari: Supabase > SQL Editor > New query > Run.

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
