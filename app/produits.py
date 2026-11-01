from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, abort, g, current_app)

from .db import get_db
from .utils import (login_required, admin_required, org_id, est_pro, paginer,
                    id_de_org, csv_response, journaliser)

bp = Blueprint("produits", __name__, url_prefix="/produits")

TRIS = {
    "nom": "p.nom ASC",
    "stock": "p.quantite ASC",
    "stock_desc": "p.quantite DESC",
    "prix": "p.prix_vente DESC",
    "recent": "p.id DESC",
}
CORPS = """FROM produits p
           LEFT JOIN categories c ON c.id = p.categorie_id
           LEFT JOIN fournisseurs f ON f.id = p.fournisseur_id
           WHERE p.organisation_id = ?"""
CHAMPS = "SELECT p.*, c.nom AS categorie_nom, f.nom AS fournisseur_nom "


@bp.route("/")
@login_required
def liste():
    db = get_db()
    q = request.args.get("q", "").strip().lower()
    cat = request.args.get("categorie", "").strip()
    alerte = request.args.get("alerte") == "1"
    tri = request.args.get("tri", "nom")
    if tri not in TRIS:
        tri = "nom"

    corps = CORPS + " AND (lower(p.nom) LIKE ? OR lower(COALESCE(p.reference, '')) LIKE ?)"
    params = [org_id(), f"%{q}%", f"%{q}%"]
    if cat.isdigit():
        corps += " AND p.categorie_id = ?"
        params.append(int(cat))
    if alerte:
        corps += " AND p.quantite <= p.seuil_alerte"

    page = paginer(db, CHAMPS + corps + " ORDER BY " + TRIS[tri],
                   "SELECT COUNT(*) AS n " + corps, params, current_app.config["PAR_PAGE"])
    cats = db.query("SELECT * FROM categories WHERE organisation_id = ? ORDER BY nom", (org_id(),))
    return render_template("produits/liste.html", page=page, q=q, cat=cat,
                           alerte=alerte, tri=tri, categories=cats)


@bp.route("/export")
@login_required
def export():
    if not est_pro():
        flash("L'export CSV est réservé au plan Pro.", "error")
        return redirect(url_for("abonnement.index"))
    rows = get_db().query(CHAMPS + CORPS + " ORDER BY p.nom", (org_id(),))
    return csv_response("produits.csv",
                        ["Nom", "Référence", "Catégorie", "Fournisseur", "Prix achat",
                         "Prix vente", "Quantité", "Seuil alerte"],
                        [[p["nom"], p["reference"] or "", p["categorie_nom"] or "",
                          p["fournisseur_nom"] or "", p["prix_achat"], p["prix_vente"],
                          p["quantite"], p["seuil_alerte"]] for p in rows])


def lire_formulaire():
    f = request.form
    try:
        d = dict(
            nom=f["nom"].strip(),
            reference=f["reference"].strip(),
            prix_achat=float(f["prix_achat"] or 0),
            prix_vente=float(f["prix_vente"] or 0),
            seuil_alerte=int(f["seuil_alerte"] or 0),
            quantite=int(f.get("quantite") or 0),
            categorie_id=id_de_org("categories", f.get("categorie_id")),
            fournisseur_id=id_de_org("fournisseurs", f.get("fournisseur_id")),
        )
    except ValueError:
        return None
    if not d["nom"] or min(d["prix_achat"], d["prix_vente"], d["seuil_alerte"], d["quantite"]) < 0:
        return None
    return d


def listes_formulaire():
    db = get_db()
    return (db.query("SELECT * FROM categories WHERE organisation_id = ? ORDER BY nom", (org_id(),)),
            db.query("SELECT * FROM fournisseurs WHERE organisation_id = ? ORDER BY nom", (org_id(),)))


@bp.route("/ajouter", methods=["GET", "POST"])
@login_required
def ajouter():
    db = get_db()
    if request.method == "POST":
        if g.user["plan"] == "free":
            n = db.one("SELECT COUNT(*) AS n FROM produits WHERE organisation_id = ?", (org_id(),))["n"]
            if n >= current_app.config["LIMITE_FREE"]:
                flash(f"Limite de {current_app.config['LIMITE_FREE']} produits atteinte. Passez au Pro.", "error")
                return redirect(url_for("abonnement.index"))
        d = lire_formulaire()
        if d is None:
            flash("Données invalides, vérifiez le formulaire", "error")
            return redirect(url_for("produits.ajouter"))
        pid = db.insert(
            """INSERT INTO produits (nom, reference, prix_achat, prix_vente, quantite,
               seuil_alerte, categorie_id, fournisseur_id, organisation_id)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (d["nom"], d["reference"], d["prix_achat"], d["prix_vente"], d["quantite"],
             d["seuil_alerte"], d["categorie_id"], d["fournisseur_id"], org_id()))
        if d["quantite"] > 0:  # stock initial = premier mouvement (traçabilité)
            db.execute(
                """INSERT INTO mouvements (produit_id, type, quantite, user_id, note, organisation_id)
                   VALUES (?,?,?,?,?,?)""",
                (pid, "entree", d["quantite"], g.user["id"], "Stock initial", org_id()))
        db.commit()
        flash("Produit ajouté", "success")
        return redirect(url_for("produits.detail", produit_id=pid))
    cats, fours = listes_formulaire()
    return render_template("produits/form.html", p=None, categories=cats, fournisseurs=fours)


def get_produit_ou_404(produit_id):
    p = get_db().one(CHAMPS + CORPS + " AND p.id = ?", (org_id(), produit_id))
    if p is None:
        abort(404)
    return p


@bp.route("/<int:produit_id>")
@login_required
def detail(produit_id):
    p = get_produit_ou_404(produit_id)
    historique = get_db().query(
        """SELECT m.*, u.nom AS user_nom FROM mouvements m
           LEFT JOIN users u ON u.id = m.user_id
           WHERE m.produit_id = ? AND m.organisation_id = ?
           ORDER BY m.id DESC LIMIT 15""", (produit_id, org_id()))
    return render_template("produits/detail.html", p=p, historique=historique)


@bp.route("/<int:produit_id>/modifier", methods=["GET", "POST"])
@login_required
def modifier(produit_id):
    p = get_produit_ou_404(produit_id)
    if request.method == "POST":
        d = lire_formulaire()
        if d is None:
            flash("Données invalides, vérifiez le formulaire", "error")
            return redirect(url_for("produits.modifier", produit_id=produit_id))
        db = get_db()
        db.execute(
            """UPDATE produits SET nom=?, reference=?, prix_achat=?, prix_vente=?,
               seuil_alerte=?, categorie_id=?, fournisseur_id=?
               WHERE id=? AND organisation_id=?""",
            (d["nom"], d["reference"], d["prix_achat"], d["prix_vente"], d["seuil_alerte"],
             d["categorie_id"], d["fournisseur_id"], produit_id, org_id()))
        db.commit()
        flash("Produit modifié", "success")
        return redirect(url_for("produits.detail", produit_id=produit_id))
    cats, fours = listes_formulaire()
    return render_template("produits/form.html", p=p, categories=cats, fournisseurs=fours)


@bp.route("/<int:produit_id>/supprimer", methods=["POST"])
@admin_required
def supprimer(produit_id):
    p = get_produit_ou_404(produit_id)
    db = get_db()
    utilise = (db.one("SELECT COUNT(*) AS n FROM vente_lignes WHERE produit_id = ?", (produit_id,))["n"]
               + db.one("SELECT COUNT(*) AS n FROM commande_lignes WHERE produit_id = ?", (produit_id,))["n"])
    if utilise:
        flash("Impossible de supprimer: ce produit figure dans des ventes ou des commandes. "
              "Mettez son stock à 0 à la place.", "error")
        return redirect(url_for("produits.detail", produit_id=produit_id))
    journaliser(db, "Produit supprimé", p["nom"])
    db.execute("DELETE FROM mouvements WHERE produit_id = ?", (produit_id,))
    db.execute("DELETE FROM produits WHERE id = ? AND organisation_id = ?", (produit_id, org_id()))
    db.commit()
    flash("Produit supprimé", "success")
    return redirect(url_for("produits.liste"))
