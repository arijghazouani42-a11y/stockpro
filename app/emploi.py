"""Emploi du temps avec détection des conflits (classe / enseignant)."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from .db import get_db
from .utils import (login_required, gestion_required, ecole, id_de_ecole, heure_ok,
                    journaliser, JOURS)

bp = Blueprint("emploi", __name__, url_prefix="/emploi")


@bp.route("/")
@login_required
def index():
    db = get_db()
    classe = request.args.get("classe", "").strip()
    ens = request.args.get("enseignant", "").strip()
    sql = """SELECT s.*, c.nom AS classe_nom, m.nom AS matiere_nom, en.nom AS ens_nom
             FROM seances s JOIN classes c ON c.id = s.classe_id JOIN matieres m ON m.id = s.matiere_id
             LEFT JOIN enseignants en ON en.id = s.enseignant_id WHERE s.ecole_id = ?"""
    params = [ecole()]
    if classe.isdigit():
        sql += " AND s.classe_id = ?"
        params.append(int(classe))
    if ens.isdigit():
        sql += " AND s.enseignant_id = ?"
        params.append(int(ens))
    par_jour = {j: [] for j in JOURS}
    for s in db.query(sql + " ORDER BY s.jour, s.debut", params):
        par_jour[s["jour"]].append(s)
    return render_template("emploi/index.html", par_jour=par_jour, classe=classe, ens=ens,
                           classes=db.query("SELECT * FROM classes WHERE ecole_id = ? ORDER BY nom", (ecole(),)),
                           matieres=db.query("SELECT * FROM matieres WHERE ecole_id = ? ORDER BY nom", (ecole(),)),
                           enseignants=db.query("SELECT * FROM enseignants WHERE ecole_id = ? ORDER BY nom", (ecole(),)))


@bp.route("/ajouter", methods=["POST"])
@gestion_required
def ajouter():
    db = get_db()
    f = request.form
    classe_id = id_de_ecole("classes", f.get("classe_id"))
    matiere_id = id_de_ecole("matieres", f.get("matiere_id"))
    ens_id = id_de_ecole("enseignants", f.get("enseignant_id"))
    debut, fin = f.get("debut", ""), f.get("fin", "")
    retour = url_for("emploi.index", classe=classe_id or "")
    try:
        jour = int(f.get("jour", 0))
    except ValueError:
        jour = 0
    if not classe_id or not matiere_id or jour not in JOURS or not heure_ok(debut) or not heure_ok(fin):
        flash("Données invalides (classe, matière, jour et heures HH:MM).", "error")
        return redirect(retour)
    if fin <= debut:
        flash("L'heure de fin doit être après l'heure de début.", "error")
        return redirect(retour)

    # conflit: même classe OU même enseignant au même moment
    sql = """SELECT s.*, c.nom AS classe_nom, en.nom AS ens_nom FROM seances s
             JOIN classes c ON c.id = s.classe_id LEFT JOIN enseignants en ON en.id = s.enseignant_id
             WHERE s.ecole_id = ? AND s.jour = ? AND s.debut < ? AND s.fin > ?
             AND (s.classe_id = ?"""
    params = [ecole(), jour, fin, debut, classe_id]
    if ens_id:
        sql += " OR s.enseignant_id = ?"
        params.append(ens_id)
    conflit = db.one(sql + ")", params)
    if conflit:
        qui = "la classe" if conflit["classe_id"] == classe_id else "l'enseignant"
        flash(f"Conflit: {qui} a déjà une séance ({conflit['classe_nom']}, {conflit['debut']}-{conflit['fin']}) à ce moment.",
              "error")
        return redirect(retour)

    db.insert(
        """INSERT INTO seances (classe_id, matiere_id, enseignant_id, jour, debut, fin, salle, ecole_id)
           VALUES (?,?,?,?,?,?,?,?)""",
        (classe_id, matiere_id, ens_id, jour, debut, fin, f.get("salle", "").strip(), ecole()))
    journaliser(db, "Séance ajoutée", f"{JOURS[jour]} {debut}-{fin}")
    db.commit()
    flash("Séance ajoutée", "success")
    return redirect(retour)


@bp.route("/<int:seance_id>/supprimer", methods=["POST"])
@gestion_required
def supprimer(seance_id):
    db = get_db()
    s = db.one("SELECT * FROM seances WHERE id = ? AND ecole_id = ?", (seance_id, ecole()))
    if s is None:
        abort(404)
    db.execute("DELETE FROM seances WHERE id = ?", (seance_id,))
    db.commit()
    flash("Séance supprimée", "success")
    return redirect(url_for("emploi.index", classe=s["classe_id"]))
