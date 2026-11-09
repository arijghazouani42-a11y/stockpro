"""Calculs pédagogiques et financiers (moyennes, rang, soldes)."""
from collections import defaultdict


def appreciation(moy):
    if moy is None:
        return "-"
    if moy >= 16:
        return "Excellent"
    if moy >= 14:
        return "Très bien"
    if moy >= 12:
        return "Bien"
    if moy >= 10:
        return "Passable"
    return "Insuffisant"


def moyennes_classe(db, ecole_id, classe_id, trimestre=0):
    """Moyennes par matière (coefficients) + moyenne générale + rang, pour une classe.
    trimestre = 1, 2, 3 ou 0 (toute l'année)."""
    matieres = {m["id"]: m for m in db.query(
        "SELECT * FROM matieres WHERE ecole_id = ?", (ecole_id,))}
    sql = """SELECT n.eleve_id, e.matiere_id, n.valeur, e.bareme
             FROM notes n JOIN evaluations e ON e.id = n.evaluation_id
             WHERE e.ecole_id = ? AND e.classe_id = ?"""
    params = [ecole_id, classe_id]
    if trimestre in (1, 2, 3):
        sql += " AND e.trimestre = ?"
        params.append(trimestre)
    brut = defaultdict(lambda: defaultdict(list))
    for r in db.query(sql, params):
        brut[r["eleve_id"]][r["matiere_id"]].append(float(r["valeur"]) / float(r["bareme"]) * 20)

    resultats = {}
    for el in db.query("SELECT id FROM eleves WHERE ecole_id = ? AND classe_id = ? AND statut = 'actif'",
                       (ecole_id, classe_id)):
        par = {mid: sum(v) / len(v) for mid, v in brut.get(el["id"], {}).items() if mid in matieres}
        coefs = sum(float(matieres[mid]["coefficient"]) for mid in par)
        gen = (sum(par[mid] * float(matieres[mid]["coefficient"]) for mid in par) / coefs) if coefs else None
        resultats[el["id"]] = dict(par_matiere=par, generale=gen)

    # rang (ex aequo = même rang)
    ordre = sorted(((round(r["generale"], 2), i) for i, r in resultats.items()
                    if r["generale"] is not None), reverse=True)
    rang, precedent, position = {}, None, 0
    for idx, (val, i) in enumerate(ordre, start=1):
        if val != precedent:
            position, precedent = idx, val
        rang[i] = position
    moyennes = [r["generale"] for r in resultats.values() if r["generale"] is not None]
    return dict(matieres=matieres, resultats=resultats, rang=rang, effectif=len(moyennes),
                moyenne_classe=(sum(moyennes) / len(moyennes)) if moyennes else None)


def soldes(db, ecole_id, eleve_id=None):
    """Situation financière des élèves actifs: dû (frais de la classe), payé, reste."""
    sql = """SELECT e.id, e.nom, e.prenom, e.matricule, e.classe_id, c.nom AS classe_nom,
                    COALESCE(c.frais_annuels, 0) AS du,
                    COALESCE((SELECT SUM(p.montant) FROM paiements p
                              WHERE p.eleve_id = e.id AND p.statut = 'valide'), 0) AS paye
             FROM eleves e LEFT JOIN classes c ON c.id = e.classe_id
             WHERE e.ecole_id = ? AND e.statut = 'actif'"""
    params = [ecole_id]
    if eleve_id is not None:
        sql += " AND e.id = ?"
        params.append(eleve_id)
    lignes = []
    for r in db.query(sql + " ORDER BY e.nom, e.prenom", params):
        d = dict(r)
        d["du"], d["paye"] = float(d["du"]), float(d["paye"])
        d["reste"] = max(d["du"] - d["paye"], 0.0)
        lignes.append(d)
    return lignes


def nb_alertes_absences(db, ecole_id, seuil):
    return db.one(
        """SELECT COUNT(*) AS n FROM (
               SELECT eleve_id FROM absences
               WHERE ecole_id = ? AND type = 'absence' AND justifiee = 0
               GROUP BY eleve_id HAVING COUNT(*) >= ?) t""", (ecole_id, seuil))["n"]
