"""Évaluations et saisie des notes."""
from flask import (Blueprint, render_template, request, redirect, url_for, flash, abort, current_app)

from .db import get_db
from .utils import (login_required, pedagogie_required, ecole, paginer, id_de_ecole,
                    date_ok, nombre, journaliser, aujourdhui)

bp = Blueprint("notes", __name__, url_prefix="/notes")
TYPES = ("DS", "Devoir", "Examen", "Oral", "TP")

CORPS = """FROM evaluations ev JOIN classes c ON c.id = ev.classe_id
           JOIN matieres m ON m.id = ev.matiere_id WHERE ev.ecole_id = ?"""
CHAMPS = """SELECT ev.*, c.nom AS classe_nom, m.nom AS matiere_nom,
            (SELECT COUNT(*) FROM notes n WHERE n.evaluation_id = ev.id) AS nb_notes """


@bp.route("/")
@login_required
def liste():
    db = get_db()
    classe = request.args.get("classe", "").strip()
    trimestre = request.args.get("trimestre", "").strip()
    corps, params = CORPS, [ecole()]
    if classe.isdigit():
        corps += " AND ev.classe_id = ?"
        params.append(int(classe))
    if trimestre in ("1", "2", "3"):
        corps += " AND ev.trimestre = ?"
        params.append(int(trimestre))
    page = paginer(db, CHAMPS + corps + " ORDER BY ev.id DESC", "SELECT COUNT(*) AS n " + corps,
                   params, current_app.config["PAR_PAGE"])
    classes = db.query("SELECT * FROM classes WHERE ecole_id = ? ORDER BY nom", (ecole(),))
    return render_template("notes/liste.html", page=page, classe=classe, trimestre=trimestre, classes=classes)


@bp.route("/nouvelle", methods=["GET", "POST"])
@pedagogie_required
def nouvelle():
    db = get_db()
    if request.method == "POST":
        f = request.form
        classe_id = id_de_ecole("classes", f.get("classe_id"))
        matiere_id = id_de_ecole("matieres", f.get("matiere_id"))
        titre = f.get("titre", "").strip()
        type_ = f.get("type") if f.get("type") in TYPES else "DS"
        date_eval = f.get("date_eval", "").strip() or aujourdhui()
        try:
            trimestre, bareme = int(f.get("trimestre", 1)), nombre(f.get("bareme") or 20)
        except ValueError:
            trimestre, bareme = 0, 0
        if not classe_id or not matiere_id or not titre or trimestre not in (1, 2, 3) or bareme <= 0 or not date_ok(date_eval):
            flash("Données invalides (classe, matière, titre, trimestre, barème, date).", "error")
            return redirect(url_for("notes.nouvelle"))
        eid = db.insert(
            """INSERT INTO evaluations (classe_id, matiere_id, titre, type, trimestre, date_eval, bareme, ecole_id)
               VALUES (?,?,?,?,?,?,?,?)""",
            (classe_id, matiere_id, titre, type_, trimestre, date_eval, bareme, ecole()))
        journaliser(db, "Évaluation créée", titre)
        db.commit()
        flash("Évaluation créée. Saisissez maintenant les notes.", "success")
        return redirect(url_for("notes.saisie", eval_id=eid))
    return render_template("notes/form.html", types=TYPES, today=aujourdhui(),
                           classes=db.query("SELECT * FROM classes WHERE ecole_id = ? ORDER BY nom", (ecole(),)),
                           matieres=db.query("SELECT * FROM matieres WHERE ecole_id = ? ORDER BY nom", (ecole(),)))


def get_eval_ou_404(eval_id):
    ev = get_db().one(CHAMPS + CORPS + " AND ev.id = ?", (ecole(), eval_id))
    if ev is None:
        abort(404)
    return ev


@bp.route("/<int:eval_id>", methods=["GET", "POST"])
@login_required
def saisie(eval_id):
    ev = get_eval_ou_404(eval_id)
    db = get_db()
    eleves = db.query(
        "SELECT id, nom, prenom, matricule FROM eleves WHERE ecole_id = ? AND classe_id = ? AND statut = 'actif' ORDER BY nom, prenom",
        (ecole(), ev["classe_id"]))
    if request.method == "POST":
        from flask import g
        if g.user["role"] not in ("admin", "enseignant"):
            flash("Action non autorisée pour votre rôle.", "error")
            return redirect(url_for("notes.saisie", eval_id=eval_id))
        bareme = float(ev["bareme"])
        valeurs, erreurs = {}, []
        for e in eleves:
            brut = request.form.get(f"note_{e['id']}", "").strip()
            if brut == "":
                continue
            try:
                v = nombre(brut)
            except ValueError:
                erreurs.append(f"{e['nom']} {e['prenom']}: note invalide")
                continue
            if v < 0 or v > bareme:
                erreurs.append(f"{e['nom']} {e['prenom']}: la note doit être entre 0 et {bareme:g}")
                continue
            valeurs[e["id"]] = v
        if erreurs:
            for m in erreurs[:4]:
                flash(m, "error")
            return redirect(url_for("notes.saisie", eval_id=eval_id))
        db.execute("DELETE FROM notes WHERE evaluation_id = ?", (eval_id,))
        for eid, v in valeurs.items():
            db.execute("INSERT INTO notes (evaluation_id, eleve_id, valeur) VALUES (?,?,?)", (eval_id, eid, v))
        journaliser(db, "Notes saisies", f"{ev['titre']} ({len(valeurs)} notes)")
        db.commit()
        flash(f"{len(valeurs)} note(s) enregistrée(s).", "success")
        return redirect(url_for("notes.saisie", eval_id=eval_id))

    existantes = {n["eleve_id"]: float(n["valeur"]) for n in
                  db.query("SELECT eleve_id, valeur FROM notes WHERE evaluation_id = ?", (eval_id,))}
    vals = list(existantes.values())
    bareme = float(ev["bareme"])
    stats = dict(n=len(vals), moyenne=(sum(vals) / len(vals)) if vals else None,
                 maxi=max(vals) if vals else None, mini=min(vals) if vals else None,
                 reussite=(100 * sum(1 for v in vals if v >= bareme / 2) / len(vals)) if vals else None)
    return render_template("notes/saisie.html", ev=ev, eleves=eleves, existantes=existantes, stats=stats)


@bp.route("/<int:eval_id>/supprimer", methods=["POST"])
@pedagogie_required
def supprimer(eval_id):
    ev = get_eval_ou_404(eval_id)
    db = get_db()
    db.execute("DELETE FROM notes WHERE evaluation_id = ?", (eval_id,))
    db.execute("DELETE FROM evaluations WHERE id = ? AND ecole_id = ?", (eval_id, ecole()))
    journaliser(db, "Évaluation supprimée", ev["titre"])
    db.commit()
    flash("Évaluation supprimée", "success")
    return redirect(url_for("notes.liste"))
