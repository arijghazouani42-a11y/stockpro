"""Catégories + Fournisseurs."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from .db import get_db
from .utils import login_required, admin_required, org_id

bp_cat = Blueprint("categories", __name__, url_prefix="/categories")
bp_four = Blueprint("fournisseurs", __name__, url_prefix="/fournisseurs")
bp_client = Blueprint("clients", __name__, url_prefix="/clients")


# ---------- Catégories ----------
@bp_cat.route("/", methods=["GET", "POST"])
@login_required
def liste():
    db = get_db()
    if request.method == "POST":
        nom = request.form["nom"].strip()
        if not nom:
            flash("Nom obligatoire", "error")
        elif db.one("SELECT id FROM categories WHERE organisation_id = ? AND lower(nom) = ?",
                    (org_id(), nom.lower())):
            flash("Cette catégorie existe déjà", "error")
        else:
            db.insert("INSERT INTO categories (nom, organisation_id) VALUES (?,?)", (nom, org_id()))
            db.commit()
            flash("Catégorie ajoutée", "success")
        return redirect(url_for("categories.liste"))
    rows = db.query(
        """SELECT c.*, (SELECT COUNT(*) FROM produits p WHERE p.categorie_id = c.id) AS nb
           FROM categories c WHERE c.organisation_id = ? ORDER BY c.nom""", (org_id(),))
    return render_template("referentiels/categories.html", categories=rows)


@bp_cat.route("/<int:cat_id>/supprimer", methods=["POST"])
@admin_required
def supprimer(cat_id):
    db = get_db()
    if not db.one("SELECT id FROM categories WHERE id = ? AND organisation_id = ?", (cat_id, org_id())):
        abort(404)
    db.execute("UPDATE produits SET categorie_id = NULL WHERE categorie_id = ?", (cat_id,))
    db.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
    db.commit()
    flash("Catégorie supprimée", "success")
    return redirect(url_for("categories.liste"))


# ---------- Fournisseurs ----------
@bp_four.route("/", methods=["GET", "POST"])
@login_required
def liste():
    db = get_db()
    if request.method == "POST":
        nom = request.form["nom"].strip()
        if not nom:
            flash("Nom obligatoire", "error")
        else:
            db.insert("INSERT INTO fournisseurs (nom, telephone, email, organisation_id) VALUES (?,?,?,?)",
                      (nom, request.form["telephone"].strip(), request.form["email"].strip(), org_id()))
            db.commit()
            flash("Fournisseur ajouté", "success")
        return redirect(url_for("fournisseurs.liste"))
    rows = db.query(
        """SELECT f.*, (SELECT COUNT(*) FROM produits p WHERE p.fournisseur_id = f.id) AS nb
           FROM fournisseurs f WHERE f.organisation_id = ? ORDER BY f.nom""", (org_id(),))
    return render_template("referentiels/fournisseurs.html", fournisseurs=rows)


@bp_four.route("/<int:f_id>/modifier", methods=["GET", "POST"])
@login_required
def modifier(f_id):
    db = get_db()
    f = db.one("SELECT * FROM fournisseurs WHERE id = ? AND organisation_id = ?", (f_id, org_id()))
    if f is None:
        abort(404)
    if request.method == "POST":
        nom = request.form["nom"].strip()
        if not nom:
            flash("Nom obligatoire", "error")
            return redirect(url_for("fournisseurs.modifier", f_id=f_id))
        db.execute("UPDATE fournisseurs SET nom=?, telephone=?, email=? WHERE id=? AND organisation_id=?",
                   (nom, request.form["telephone"].strip(), request.form["email"].strip(), f_id, org_id()))
        db.commit()
        flash("Fournisseur modifié", "success")
        return redirect(url_for("fournisseurs.liste"))
    return render_template("referentiels/fournisseur_form.html", f=f)


@bp_four.route("/<int:f_id>/supprimer", methods=["POST"])
@admin_required
def supprimer(f_id):
    db = get_db()
    if not db.one("SELECT id FROM fournisseurs WHERE id = ? AND organisation_id = ?", (f_id, org_id())):
        abort(404)
    db.execute("UPDATE produits SET fournisseur_id = NULL WHERE fournisseur_id = ?", (f_id,))
    db.execute("UPDATE commandes SET fournisseur_id = NULL WHERE fournisseur_id = ?", (f_id,))
    db.execute("DELETE FROM fournisseurs WHERE id = ?", (f_id,))
    db.commit()
    flash("Fournisseur supprimé", "success")
    return redirect(url_for("fournisseurs.liste"))


# ---------- Clients ----------
@bp_client.route("/", methods=["GET", "POST"])
@login_required
def liste():
    db = get_db()
    if request.method == "POST":
        nom = request.form["nom"].strip()
        if not nom:
            flash("Nom obligatoire", "error")
        else:
            db.insert("INSERT INTO clients (nom, telephone, email, adresse, organisation_id) VALUES (?,?,?,?,?)",
                      (nom, request.form["telephone"].strip(), request.form["email"].strip(),
                       request.form["adresse"].strip(), org_id()))
            db.commit()
            flash("Client ajouté", "success")
        return redirect(url_for("clients.liste"))
    rows = db.query(
        """SELECT c.*,
                  (SELECT COUNT(*) FROM ventes v WHERE v.client_id = c.id AND v.statut <> 'annulee') AS nb,
                  (SELECT COALESCE(SUM(v.total), 0) FROM ventes v WHERE v.client_id = c.id AND v.statut <> 'annulee') AS ca
           FROM clients c WHERE c.organisation_id = ? ORDER BY c.nom""", (org_id(),))
    return render_template("referentiels/clients.html", clients=rows)


@bp_client.route("/<int:c_id>/modifier", methods=["GET", "POST"])
@login_required
def modifier(c_id):
    db = get_db()
    c = db.one("SELECT * FROM clients WHERE id = ? AND organisation_id = ?", (c_id, org_id()))
    if c is None:
        abort(404)
    if request.method == "POST":
        nom = request.form["nom"].strip()
        if not nom:
            flash("Nom obligatoire", "error")
            return redirect(url_for("clients.modifier", c_id=c_id))
        db.execute("UPDATE clients SET nom=?, telephone=?, email=?, adresse=? WHERE id=? AND organisation_id=?",
                   (nom, request.form["telephone"].strip(), request.form["email"].strip(),
                    request.form["adresse"].strip(), c_id, org_id()))
        db.commit()
        flash("Client modifié", "success")
        return redirect(url_for("clients.liste"))
    return render_template("referentiels/client_form.html", c=c)


@bp_client.route("/<int:c_id>/supprimer", methods=["POST"])
@admin_required
def supprimer(c_id):
    db = get_db()
    if not db.one("SELECT id FROM clients WHERE id = ? AND organisation_id = ?", (c_id, org_id())):
        abort(404)
    db.execute("UPDATE ventes SET client_id = NULL WHERE client_id = ?", (c_id,))
    db.execute("DELETE FROM clients WHERE id = ?", (c_id,))
    db.commit()
    flash("Client supprimé", "success")
    return redirect(url_for("clients.liste"))
