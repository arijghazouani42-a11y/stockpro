"""Classes, matières, enseignants."""
from flask import (Blueprint, render_template, request, redirect, url_for, flash, abort)

from .db import get_db
from .utils import (login_required, gestion_required, admin_required, ecole,
                    journaliser, nombre)

bp_classe = Blueprint("classes", __name__, url_prefix="/classes")
bp_matiere = Blueprint("matieres", __name__, url_prefix="/matieres")
bp_ens = Blueprint("enseignants", __name__, url_prefix="/enseignants")


# ============ Classes ============
@bp_classe.route("/")
@login_required
def liste():
    rows = get_db().query(
        """SELECT c.*,
                  (SELECT COUNT(*) FROM eleves e WHERE e.classe_id = c.id AND e.statut = 'actif') AS nb
           FROM classes c WHERE c.ecole_id = ? ORDER BY c.nom""", (ecole(),))
    return render_template("classes/liste.html", classes=rows)


def lire_classe():
    f = request.form
    try:
        d = dict(nom=f["nom"].strip(), niveau=f.get("niveau", "").strip(),
                 frais=nombre(f.get("frais_annuels") or 0), capacite=int(f.get("capacite") or 30))
    except ValueError:
        return None
    if not d["nom"] or d["frais"] < 0 or d["capacite"] < 1:
        return None
    return d


@bp_classe.route("/ajouter", methods=["GET", "POST"])
@gestion_required
def ajouter():
    if request.method == "POST":
        d = lire_classe()
        db = get_db()
        if d is None:
            flash("Données invalides", "error")
        elif db.one("SELECT id FROM classes WHERE ecole_id = ? AND lower(nom) = ?", (ecole(), d["nom"].lower())):
            flash("Cette classe existe déjà", "error")
        else:
            cid = db.insert(
                "INSERT INTO classes (nom, niveau, frais_annuels, capacite, ecole_id) VALUES (?,?,?,?,?)",
                (d["nom"], d["niveau"], d["frais"], d["capacite"], ecole()))
            journaliser(db, "Classe créée", d["nom"])
            db.commit()
            flash("Classe ajoutée", "success")
            return redirect(url_for("classes.detail", classe_id=cid))
        return redirect(url_for("classes.ajouter"))
    return render_template("classes/form.html", c=None)


def get_classe_ou_404(classe_id):
    c = get_db().one("SELECT * FROM classes WHERE id = ? AND ecole_id = ?", (classe_id, ecole()))
    if c is None:
        abort(404)
    return c


@bp_classe.route("/<int:classe_id>")
@login_required
def detail(classe_id):
    c = get_classe_ou_404(classe_id)
    db = get_db()
    eleves = db.query(
        "SELECT * FROM eleves WHERE classe_id = ? AND ecole_id = ? AND statut = 'actif' ORDER BY nom, prenom",
        (classe_id, ecole()))
    matieres = db.query(
        """SELECT DISTINCT m.nom, en.nom AS ens_nom FROM seances s
           JOIN matieres m ON m.id = s.matiere_id LEFT JOIN enseignants en ON en.id = s.enseignant_id
           WHERE s.classe_id = ? AND s.ecole_id = ? ORDER BY m.nom""", (classe_id, ecole()))
    return render_template("classes/detail.html", c=c, eleves=eleves, matieres=matieres)


@bp_classe.route("/<int:classe_id>/modifier", methods=["GET", "POST"])
@gestion_required
def modifier(classe_id):
    c = get_classe_ou_404(classe_id)
    if request.method == "POST":
        d = lire_classe()
        if d is None:
            flash("Données invalides", "error")
            return redirect(url_for("classes.modifier", classe_id=classe_id))
        db = get_db()
        db.execute("UPDATE classes SET nom=?, niveau=?, frais_annuels=?, capacite=? WHERE id=? AND ecole_id=?",
                   (d["nom"], d["niveau"], d["frais"], d["capacite"], classe_id, ecole()))
        journaliser(db, "Classe modifiée", d["nom"])
        db.commit()
        flash("Classe modifiée", "success")
        return redirect(url_for("classes.detail", classe_id=classe_id))
    return render_template("classes/form.html", c=c)


@bp_classe.route("/<int:classe_id>/supprimer", methods=["POST"])
@admin_required
def supprimer(classe_id):
    c = get_classe_ou_404(classe_id)
    db = get_db()
    if db.one("SELECT COUNT(*) AS n FROM eleves WHERE classe_id = ?", (classe_id,))["n"]:
        flash("Impossible: cette classe contient des élèves. Transférez-les d'abord.", "error")
        return redirect(url_for("classes.detail", classe_id=classe_id))
    db.execute("DELETE FROM notes WHERE evaluation_id IN (SELECT id FROM evaluations WHERE classe_id = ?)", (classe_id,))
    db.execute("DELETE FROM evaluations WHERE classe_id = ?", (classe_id,))
    db.execute("DELETE FROM seances WHERE classe_id = ?", (classe_id,))
    db.execute("DELETE FROM classes WHERE id = ? AND ecole_id = ?", (classe_id, ecole()))
    journaliser(db, "Classe supprimée", c["nom"])
    db.commit()
    flash("Classe supprimée", "success")
    return redirect(url_for("classes.liste"))


# ============ Matières ============
@bp_matiere.route("/", methods=["GET", "POST"])
@login_required
def liste():
    db = get_db()
    if request.method == "POST":
        if g_role() not in ("admin", "secretaire"):
            flash("Action non autorisée pour votre rôle.", "error")
            return redirect(url_for("matieres.liste"))
        nom = request.form["nom"].strip()
        try:
            coef = nombre(request.form.get("coefficient") or 1)
        except ValueError:
            coef = -1
        if not nom or coef <= 0:
            flash("Nom et coefficient (> 0) obligatoires", "error")
        elif db.one("SELECT id FROM matieres WHERE ecole_id = ? AND lower(nom) = ?", (ecole(), nom.lower())):
            flash("Cette matière existe déjà", "error")
        else:
            db.insert("INSERT INTO matieres (nom, coefficient, ecole_id) VALUES (?,?,?)", (nom, coef, ecole()))
            db.commit()
            flash("Matière ajoutée", "success")
        return redirect(url_for("matieres.liste"))
    rows = db.query(
        """SELECT m.*, (SELECT COUNT(*) FROM evaluations e WHERE e.matiere_id = m.id) AS nb_eval
           FROM matieres m WHERE m.ecole_id = ? ORDER BY m.nom""", (ecole(),))
    return render_template("classes/matieres.html", matieres=rows)


def g_role():
    from flask import g
    return g.user["role"]


@bp_matiere.route("/<int:m_id>/supprimer", methods=["POST"])
@admin_required
def supprimer(m_id):
    db = get_db()
    m = db.one("SELECT * FROM matieres WHERE id = ? AND ecole_id = ?", (m_id, ecole()))
    if m is None:
        abort(404)
    utilise = (db.one("SELECT COUNT(*) AS n FROM evaluations WHERE matiere_id = ?", (m_id,))["n"]
               + db.one("SELECT COUNT(*) AS n FROM seances WHERE matiere_id = ?", (m_id,))["n"])
    if utilise:
        flash("Impossible: cette matière est utilisée (emploi du temps ou évaluations).", "error")
    else:
        db.execute("DELETE FROM matieres WHERE id = ?", (m_id,))
        db.commit()
        flash("Matière supprimée", "success")
    return redirect(url_for("matieres.liste"))


# ============ Enseignants ============
@bp_ens.route("/", methods=["GET", "POST"])
@login_required
def liste():
    db = get_db()
    if request.method == "POST":
        if g_role() not in ("admin", "secretaire"):
            flash("Action non autorisée pour votre rôle.", "error")
            return redirect(url_for("enseignants.liste"))
        nom = request.form["nom"].strip()
        if not nom:
            flash("Nom obligatoire", "error")
        else:
            db.insert("INSERT INTO enseignants (nom, telephone, email, specialite, ecole_id) VALUES (?,?,?,?,?)",
                      (nom, request.form["telephone"].strip(), request.form["email"].strip(),
                       request.form["specialite"].strip(), ecole()))
            journaliser(db, "Enseignant ajouté", nom)
            db.commit()
            flash("Enseignant ajouté", "success")
        return redirect(url_for("enseignants.liste"))
    rows = db.query(
        """SELECT en.*, (SELECT COUNT(*) FROM seances s WHERE s.enseignant_id = en.id) AS nb_seances
           FROM enseignants en WHERE en.ecole_id = ? ORDER BY en.nom""", (ecole(),))
    return render_template("enseignants/liste.html", enseignants=rows)


@bp_ens.route("/<int:e_id>/modifier", methods=["GET", "POST"])
@gestion_required
def modifier(e_id):
    db = get_db()
    en = db.one("SELECT * FROM enseignants WHERE id = ? AND ecole_id = ?", (e_id, ecole()))
    if en is None:
        abort(404)
    if request.method == "POST":
        nom = request.form["nom"].strip()
        if not nom:
            flash("Nom obligatoire", "error")
            return redirect(url_for("enseignants.modifier", e_id=e_id))
        db.execute("UPDATE enseignants SET nom=?, telephone=?, email=?, specialite=? WHERE id=? AND ecole_id=?",
                   (nom, request.form["telephone"].strip(), request.form["email"].strip(),
                    request.form["specialite"].strip(), e_id, ecole()))
        db.commit()
        flash("Enseignant modifié", "success")
        return redirect(url_for("enseignants.liste"))
    return render_template("enseignants/form.html", en=en)


@bp_ens.route("/<int:e_id>/supprimer", methods=["POST"])
@admin_required
def supprimer(e_id):
    db = get_db()
    en = db.one("SELECT * FROM enseignants WHERE id = ? AND ecole_id = ?", (e_id, ecole()))
    if en is None:
        abort(404)
    db.execute("UPDATE seances SET enseignant_id = NULL WHERE enseignant_id = ?", (e_id,))
    db.execute("DELETE FROM enseignants WHERE id = ?", (e_id,))
    journaliser(db, "Enseignant supprimé", en["nom"])
    db.commit()
    flash("Enseignant supprimé", "success")
    return redirect(url_for("enseignants.liste"))
