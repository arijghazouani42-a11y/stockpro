"""Appel (présence / absence / retard), historique, justification."""
from flask import (Blueprint, render_template, request, redirect, url_for, flash, abort,
                   current_app, g)

from .db import get_db
from .utils import (login_required, vie_scolaire_required, ecole, paginer, id_de_ecole,
                    date_ok, aujourdhui, journaliser)

bp = Blueprint("absences", __name__, url_prefix="/absences")


@bp.route("/", methods=["GET", "POST"])
@login_required
def appel():
    db = get_db()
    if request.method == "POST":
        if g.user["role"] not in ("admin", "secretaire", "enseignant"):
            abort(403)
        classe_id = id_de_ecole("classes", request.form.get("classe_id"))
        jour = request.form.get("date", "")
        if not classe_id or not date_ok(jour):
            flash("Classe et date valides obligatoires.", "error")
            return redirect(url_for("absences.appel"))
        eleves = db.query("SELECT id FROM eleves WHERE ecole_id = ? AND classe_id = ? AND statut = 'actif'",
                          (ecole(), classe_id))
        nb = 0
        for e in eleves:
            statut = request.form.get(f"statut_{e['id']}", "present")
            db.execute("DELETE FROM absences WHERE eleve_id = ? AND date_abs = ? AND ecole_id = ?",
                       (e["id"], jour, ecole()))
            if statut in ("absence", "retard"):
                db.execute(
                    """INSERT INTO absences (eleve_id, date_abs, type, justifiee, motif, user_id, ecole_id)
                       VALUES (?,?,?,?,?,?,?)""",
                    (e["id"], jour, statut, 1 if request.form.get(f"just_{e['id']}") else 0,
                     request.form.get(f"motif_{e['id']}", "").strip(), g.user["id"], ecole()))
                nb += 1
        journaliser(db, "Appel", f"{jour}: {nb} absence(s)/retard(s)")
        db.commit()
        flash(f"Appel enregistré: {nb} absence(s) / retard(s).", "success")
        return redirect(url_for("absences.appel", classe=classe_id, date=jour))

    classes = db.query("SELECT * FROM classes WHERE ecole_id = ? ORDER BY nom", (ecole(),))
    classe = request.args.get("classe", "").strip()
    jour = request.args.get("date", "").strip()
    if not date_ok(jour):
        jour = aujourdhui()
    eleves, existant = [], {}
    if classe.isdigit() and id_de_ecole("classes", classe):
        eleves = db.query(
            "SELECT id, nom, prenom, matricule FROM eleves WHERE ecole_id = ? AND classe_id = ? AND statut = 'actif' ORDER BY nom, prenom",
            (ecole(), int(classe)))
        for a in db.query("SELECT * FROM absences WHERE ecole_id = ? AND date_abs = ?", (ecole(), jour)):
            existant[a["eleve_id"]] = a
    return render_template("absences/appel.html", classes=classes, classe=classe, jour=jour,
                           eleves=eleves, existant=existant)


@bp.route("/historique")
@login_required
def historique():
    db = get_db()
    classe = request.args.get("classe", "").strip()
    type_ = request.args.get("type", "").strip()
    just = request.args.get("justifiee", "").strip()
    corps = """FROM absences a JOIN eleves e ON e.id = a.eleve_id
               LEFT JOIN classes c ON c.id = e.classe_id WHERE a.ecole_id = ?"""
    params = [ecole()]
    if classe.isdigit():
        corps += " AND e.classe_id = ?"
        params.append(int(classe))
    if type_ in ("absence", "retard"):
        corps += " AND a.type = ?"
        params.append(type_)
    if just in ("0", "1"):
        corps += " AND a.justifiee = ?"
        params.append(int(just))
    page = paginer(db, "SELECT a.*, e.nom, e.prenom, c.nom AS classe_nom " + corps + " ORDER BY a.date_abs DESC, a.id DESC",
                   "SELECT COUNT(*) AS n " + corps, params, current_app.config["PAR_PAGE"])
    # élèves en alerte (trop d'absences non justifiées)
    alertes = db.query(
        """SELECT e.id, e.nom, e.prenom, c.nom AS classe_nom, COUNT(a.id) AS n
           FROM absences a JOIN eleves e ON e.id = a.eleve_id LEFT JOIN classes c ON c.id = e.classe_id
           WHERE a.ecole_id = ? AND a.type = 'absence' AND a.justifiee = 0
           GROUP BY e.id, e.nom, e.prenom, c.nom HAVING COUNT(a.id) >= ? ORDER BY n DESC""",
        (ecole(), current_app.config["SEUIL_ABSENCES"]))
    classes = db.query("SELECT * FROM classes WHERE ecole_id = ? ORDER BY nom", (ecole(),))
    return render_template("absences/historique.html", page=page, classe=classe, type_=type_,
                           just=just, classes=classes, alertes=alertes)


@bp.route("/<int:absence_id>/justifier", methods=["POST"])
@vie_scolaire_required
def justifier(absence_id):
    db = get_db()
    a = db.one("SELECT * FROM absences WHERE id = ? AND ecole_id = ?", (absence_id, ecole()))
    if a is None:
        abort(404)
    nouveau = 0 if a["justifiee"] else 1
    db.execute("UPDATE absences SET justifiee = ? WHERE id = ?", (nouveau, absence_id))
    journaliser(db, "Justification", f"Absence #{absence_id} {'justifiée' if nouveau else 'non justifiée'}")
    db.commit()
    flash("Absence justifiée." if nouveau else "Justification retirée.", "success")
    return redirect(request.form.get("next") or url_for("absences.historique"))
