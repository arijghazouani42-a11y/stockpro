from datetime import timedelta

from flask import Blueprint, render_template, redirect, url_for, g, current_app, request, flash

from .calculs import soldes, moyennes_classe, nb_alertes_absences
from .db import get_db
from .utils import login_required, roles_required, ecole, aujourdhui, est_pro, TUNIS
from datetime import datetime

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    if g.user:
        return redirect(url_for("main.dashboard"))
    return render_template("main/landing.html")


def mois_precedents(n):
    d = datetime.now(TUNIS).date().replace(day=1)
    mois = []
    for _ in range(n):
        mois.append(d.strftime("%Y-%m"))
        d = (d - timedelta(days=1)).replace(day=1)
    return list(reversed(mois))


@bp.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    ec = ecole()
    nb_eleves = db.one("SELECT COUNT(*) AS n FROM eleves WHERE ecole_id = ? AND statut = 'actif'", (ec,))["n"]
    nb_ens = db.one("SELECT COUNT(*) AS n FROM enseignants WHERE ecole_id = ?", (ec,))["n"]
    nb_classes = db.one("SELECT COUNT(*) AS n FROM classes WHERE ecole_id = ?", (ec,))["n"]
    garcons = db.one("SELECT COUNT(*) AS n FROM eleves WHERE ecole_id = ? AND statut = 'actif' AND sexe = 'M'", (ec,))["n"]
    filles = db.one("SELECT COUNT(*) AS n FROM eleves WHERE ecole_id = ? AND statut = 'actif' AND sexe = 'F'", (ec,))["n"]

    effectif = db.query(
        """SELECT c.nom, c.capacite, COUNT(e.id) AS n FROM classes c
           LEFT JOIN eleves e ON e.classe_id = c.id AND e.statut = 'actif'
           WHERE c.ecole_id = ? GROUP BY c.id, c.nom, c.capacite ORDER BY c.nom""", (ec,))
    chart_effectif = dict(labels=[r["nom"] for r in effectif], valeurs=[r["n"] for r in effectif])

    # absences des 7 derniers jours
    aujourdhui_d = datetime.now(TUNIS).date()
    jours = [aujourdhui_d - timedelta(days=i) for i in range(6, -1, -1)]
    par_jour = {str(j): 0 for j in jours}
    for r in db.query(
            """SELECT date_abs, COUNT(*) AS n FROM absences
               WHERE ecole_id = ? AND type = 'absence' AND date_abs >= ? GROUP BY date_abs""",
            (ec, str(jours[0]))):
        if str(r["date_abs"]) in par_jour:
            par_jour[str(r["date_abs"])] = int(r["n"])
    chart_abs = dict(labels=[j.strftime("%d/%m") for j in jours], valeurs=list(par_jour.values()))
    absents_aujourdhui = db.one(
        "SELECT COUNT(*) AS n FROM absences WHERE ecole_id = ? AND date_abs = ? AND type = 'absence'",
        (ec, aujourdhui()))["n"]

    finance = None
    chart_paiements = None
    if g.user["role"] != "enseignant":
        lignes = soldes(db, ec)
        du = sum(s["du"] for s in lignes)
        paye = sum(s["paye"] for s in lignes)
        mois = mois_precedents(6)
        totaux = {m: 0.0 for m in mois}
        for r in db.query(
                """SELECT substr(date_paiement, 1, 7) AS mois, SUM(montant) AS total FROM paiements
                   WHERE ecole_id = ? AND statut = 'valide' AND date_paiement >= ?
                   GROUP BY substr(date_paiement, 1, 7)""", (ec, mois[0] + "-01")):
            if r["mois"] in totaux:
                totaux[r["mois"]] = round(float(r["total"]), 2)
        finance = dict(du=du, paye=paye, reste=max(du - paye, 0),
                       nb_impayes=sum(1 for s in lignes if s["reste"] > 0))
        chart_paiements = dict(labels=mois, valeurs=list(totaux.values()))

    alertes = db.query(
        """SELECT e.id, e.nom, e.prenom, c.nom AS classe_nom, COUNT(a.id) AS n
           FROM absences a JOIN eleves e ON e.id = a.eleve_id LEFT JOIN classes c ON c.id = e.classe_id
           WHERE a.ecole_id = ? AND a.type = 'absence' AND a.justifiee = 0
           GROUP BY e.id, e.nom, e.prenom, c.nom HAVING COUNT(a.id) >= ? ORDER BY n DESC LIMIT 6""",
        (ec, current_app.config["SEUIL_ABSENCES"]))
    dernieres_eval = db.query(
        """SELECT ev.id, ev.titre, ev.date_eval, c.nom AS classe_nom, m.nom AS matiere_nom
           FROM evaluations ev JOIN classes c ON c.id = ev.classe_id JOIN matieres m ON m.id = ev.matiere_id
           WHERE ev.ecole_id = ? ORDER BY ev.id DESC LIMIT 5""", (ec,))
    return render_template("main/dashboard.html", nb_eleves=nb_eleves, nb_ens=nb_ens, nb_classes=nb_classes,
                           garcons=garcons, filles=filles, effectif=effectif, chart_effectif=chart_effectif,
                           chart_abs=chart_abs, absents_aujourdhui=absents_aujourdhui, finance=finance,
                           chart_paiements=chart_paiements, alertes=alertes, dernieres_eval=dernieres_eval)


@bp.route("/rapports")
@roles_required("admin", "secretaire")
def rapports():
    db = get_db()
    ec = ecole()
    trimestre = request.args.get("trimestre", 0, type=int)
    if trimestre not in (0, 1, 2, 3):
        trimestre = 0
    par_classe = []
    top = []
    for c in db.query("SELECT * FROM classes WHERE ecole_id = ? ORDER BY nom", (ec,)):
        calc = moyennes_classe(db, ec, c["id"], trimestre)
        notes_gen = [(r["generale"], i) for i, r in calc["resultats"].items() if r["generale"] is not None]
        reussis = sum(1 for v, _ in notes_gen if v >= 10)
        par_classe.append(dict(nom=c["nom"], effectif=len(calc["resultats"]), notes=len(notes_gen),
                               moyenne=calc["moyenne_classe"],
                               reussite=(100 * reussis / len(notes_gen)) if notes_gen else None))
        for v, i in notes_gen:
            top.append((v, i, c["nom"]))
    top.sort(reverse=True)
    noms = {e["id"]: f"{e['prenom']} {e['nom']}" for e in
            db.query("SELECT id, nom, prenom FROM eleves WHERE ecole_id = ?", (ec,))}
    top5 = [dict(nom=noms.get(i, "?"), classe=cn, moyenne=v) for v, i, cn in top[:5]]
    lignes = soldes(db, ec)
    effectifs = db.query(
        """SELECT c.nom, COUNT(e.id) AS n FROM classes c LEFT JOIN eleves e ON e.classe_id = c.id AND e.statut = 'actif'
           WHERE c.ecole_id = ? GROUP BY c.id, c.nom ORDER BY c.nom""", (ec,))
    finance = dict(du=sum(s["du"] for s in lignes), paye=sum(s["paye"] for s in lignes))
    finance["reste"] = max(finance["du"] - finance["paye"], 0)
    finance["taux"] = (100 * finance["paye"] / finance["du"]) if finance["du"] else None
    return render_template("main/rapports.html", par_classe=par_classe, top5=top5, trimestre=trimestre,
                           finance=finance, effectifs=effectifs)
