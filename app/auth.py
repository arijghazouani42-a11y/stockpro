from datetime import datetime

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, session, g, current_app, abort)
from werkzeug.security import generate_password_hash, check_password_hash

from .db import get_db
from .utils import (login_required, admin_required, ecole, journaliser, ROLES, TUNIS)

bp = Blueprint("auth", __name__)


def annee_scolaire_courante():
    maintenant = datetime.now(TUNIS)
    debut = maintenant.year if maintenant.month >= 8 else maintenant.year - 1
    return f"{debut}-{debut + 1}"


@bp.before_app_request
def charger_user():
    g.user = None
    if request.endpoint in (None, "static"):
        return
    uid = session.get("user_id")
    if uid:
        g.user = get_db().one(
            """SELECT u.*, e.nom AS ecole_nom, e.plan, e.annee_scolaire
               FROM utilisateurs u JOIN ecoles e ON e.id = u.ecole_id
               WHERE u.id = ?""", (uid,))
        if g.user is None:
            session.pop("user_id", None)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        nom = request.form["nom"].strip()
        ecole_nom = request.form["ecole"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        db = get_db()
        if not nom or not ecole_nom or not email:
            flash("Tous les champs sont obligatoires", "error")
        elif len(password) < 6:
            flash("Le mot de passe doit contenir au moins 6 caractères", "error")
        elif db.one("SELECT id FROM utilisateurs WHERE email = ?", (email,)):
            flash("Email déjà utilisé", "error")
        else:
            eid = db.insert("INSERT INTO ecoles (nom, annee_scolaire) VALUES (?, ?)",
                            (ecole_nom, annee_scolaire_courante()))
            uid = db.insert(
                "INSERT INTO utilisateurs (nom, email, mot_de_passe, role, ecole_id) VALUES (?,?,?,?,?)",
                (nom, email, generate_password_hash(password), "admin", eid))
            db.commit()
            session.clear()
            session["user_id"] = uid
            flash("Bienvenue ! Votre école a été créée.", "success")
            return redirect(url_for("main.dashboard"))
        return redirect(url_for("auth.register"))
    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        user = get_db().one("SELECT * FROM utilisateurs WHERE email = ?", (email,))
        if user and check_password_hash(user["mot_de_passe"], password):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("main.dashboard"))
        flash("Email ou mot de passe incorrect", "error")
        return redirect(url_for("auth.login"))
    return render_template("auth/login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.index"))


@bp.route("/profil", methods=["GET", "POST"])
@login_required
def profil():
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "profil":
            nom = request.form["nom"].strip()
            if nom:
                db.execute("UPDATE utilisateurs SET nom = ? WHERE id = ?", (nom, g.user["id"]))
                db.commit()
                flash("Profil mis à jour", "success")
        elif action == "mdp":
            actuel, nouveau = request.form["actuel"], request.form["nouveau"]
            fiche = db.one("SELECT mot_de_passe FROM utilisateurs WHERE id = ?", (g.user["id"],))
            if not check_password_hash(fiche["mot_de_passe"], actuel):
                flash("Mot de passe actuel incorrect", "error")
            elif len(nouveau) < 6:
                flash("Le nouveau mot de passe doit contenir 6 caractères minimum", "error")
            else:
                db.execute("UPDATE utilisateurs SET mot_de_passe = ? WHERE id = ?",
                           (generate_password_hash(nouveau), g.user["id"]))
                db.commit()
                flash("Mot de passe modifié", "success")
        elif action == "ecole" and g.user["role"] == "admin":
            nom = request.form["ecole_nom"].strip()
            annee = request.form.get("annee_scolaire", "").strip()
            if nom:
                db.execute("UPDATE ecoles SET nom = ?, annee_scolaire = ? WHERE id = ?",
                           (nom, annee or g.user["annee_scolaire"], ecole()))
                db.commit()
                flash("École mise à jour", "success")
        return redirect(url_for("auth.profil"))
    return render_template("auth/profil.html")


@bp.route("/equipe", methods=["GET", "POST"])
@admin_required
def equipe():
    db = get_db()
    membres = db.query("SELECT * FROM utilisateurs WHERE ecole_id = ? ORDER BY id", (ecole(),))
    if request.method == "POST":
        nom = request.form["nom"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        role = request.form.get("role", "enseignant")
        if role not in ROLES:
            role = "enseignant"
        if g.user["plan"] == "free" and len(membres) >= current_app.config["MAX_EQUIPE_FREE"]:
            flash("Le plan Free est limité à 1 utilisateur. Passez au Pro pour ajouter des membres.", "error")
            return redirect(url_for("abonnement.index"))
        if not nom or not email:
            flash("Nom et email obligatoires", "error")
        elif len(password) < 6:
            flash("Mot de passe: 6 caractères minimum", "error")
        elif db.one("SELECT id FROM utilisateurs WHERE email = ?", (email,)):
            flash("Email déjà utilisé", "error")
        else:
            db.insert(
                "INSERT INTO utilisateurs (nom, email, mot_de_passe, role, ecole_id) VALUES (?,?,?,?,?)",
                (nom, email, generate_password_hash(password), role, ecole()))
            journaliser(db, "Équipe", f"Ajout de {nom} ({role})")
            db.commit()
            flash(f"{nom} a été ajouté à l'équipe", "success")
        return redirect(url_for("auth.equipe"))
    return render_template("auth/equipe.html", membres=membres)


@bp.route("/equipe/<int:user_id>/supprimer", methods=["POST"])
@admin_required
def equipe_supprimer(user_id):
    db = get_db()
    if db.one("SELECT id FROM utilisateurs WHERE id = ? AND ecole_id = ?", (user_id, ecole())) is None:
        abort(404)
    if user_id == g.user["id"]:
        flash("Vous ne pouvez pas vous supprimer vous-même.", "error")
    else:
        for table in ("absences", "paiements", "journal_ecole"):
            db.execute(f"UPDATE {table} SET user_id = NULL WHERE user_id = ?", (user_id,))
        journaliser(db, "Équipe", f"Suppression d'un membre (#{user_id})")
        db.execute("DELETE FROM utilisateurs WHERE id = ?", (user_id,))
        db.commit()
        flash("Membre supprimé", "success")
    return redirect(url_for("auth.equipe"))
