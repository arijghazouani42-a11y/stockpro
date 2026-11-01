"""Commandes fournisseurs (bons de commande): la réception ajoute le stock."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, current_app, abort

from .db import get_db
from .utils import login_required, org_id, paginer, id_de_org, lire_lignes, journaliser

bp = Blueprint("commandes", __name__, url_prefix="/commandes")


def get_commande_ou_404(cid):
    c = get_db().one(
        """SELECT c.*, f.nom AS fournisseur_nom, f.telephone AS f_tel, f.email AS f_email, u.nom AS user_nom
           FROM commandes c LEFT JOIN fournisseurs f ON f.id = c.fournisseur_id
           LEFT JOIN users u ON u.id = c.user_id
           WHERE c.id = ? AND c.organisation_id = ?""", (cid, org_id()))
    if c is None:
        abort(404)
    return c


@bp.route("/")
@login_required
def liste():
    db = get_db()
    statut = request.args.get("statut", "").strip()
    corps = "FROM commandes c LEFT JOIN fournisseurs f ON f.id = c.fournisseur_id WHERE c.organisation_id = ?"
    params = [org_id()]
    if statut in ("brouillon", "envoyee", "recue", "annulee"):
        corps += " AND c.statut = ?"
        params.append(statut)
    page = paginer(db, "SELECT c.*, f.nom AS fournisseur_nom " + corps + " ORDER BY c.id DESC",
                   "SELECT COUNT(*) AS n " + corps, params, current_app.config["PAR_PAGE"])
    return render_template("commandes/liste.html", page=page, statut=statut)


@bp.route("/nouvelle", methods=["GET", "POST"])
@login_required
def nouvelle():
    db = get_db()
    if request.method == "POST":
        lignes = lire_lignes()
        if not lignes:
            flash("Ajoutez au moins une ligne valide (produit, quantité, prix).", "error")
            return redirect(url_for("commandes.nouvelle"))
        fournisseur_id = id_de_org("fournisseurs", request.form.get("fournisseur_id"))
        statut = "envoyee" if request.form.get("action") == "envoyer" else "brouillon"
        numero = db.one("SELECT COALESCE(MAX(numero), 0) + 1 AS n FROM commandes WHERE organisation_id = ?",
                        (org_id(),))["n"]
        total = round(sum(l["quantite"] * l["prix"] for l in lignes), 2)
        cid = db.insert(
            "INSERT INTO commandes (numero, fournisseur_id, statut, total, user_id, organisation_id) VALUES (?,?,?,?,?,?)",
            (numero, fournisseur_id, statut, total, g.user["id"], org_id()))
        for l in lignes:
            db.execute("INSERT INTO commande_lignes (commande_id, produit_id, quantite, prix_achat) VALUES (?,?,?,?)",
                       (cid, l["produit_id"], l["quantite"], l["prix"]))
        journaliser(db, "Commande fournisseur", f"BC-{numero:04d} · {total:.2f} DT · {statut}")
        db.commit()
        flash(f"Commande BC-{numero:04d} créée.", "success")
        return redirect(url_for("commandes.detail", commande_id=cid))

    produits = db.query(
        "SELECT id, nom, prix_achat, quantite, seuil_alerte FROM produits WHERE organisation_id = ? ORDER BY nom",
        (org_id(),))
    fournisseurs = db.query("SELECT id, nom FROM fournisseurs WHERE organisation_id = ? ORDER BY nom", (org_id(),))
    produits_json = [dict(id=p["id"], nom=p["nom"], prix=float(p["prix_achat"] or 0), stock=p["quantite"])
                     for p in produits]
    lignes_init = []
    if request.args.get("alertes") == "1":   # commande automatique des produits en alerte
        for p in produits:
            if p["quantite"] <= p["seuil_alerte"]:
                lignes_init.append(dict(produit_id=p["id"], quantite=max(p["seuil_alerte"] * 2 - p["quantite"], 1),
                                        prix=float(p["prix_achat"] or 0)))
    return render_template("commandes/form.html", produits_json=produits_json,
                           fournisseurs=fournisseurs, lignes_init=lignes_init)


@bp.route("/<int:commande_id>")
@login_required
def detail(commande_id):
    c = get_commande_ou_404(commande_id)
    lignes = get_db().query(
        """SELECT l.*, p.nom AS produit_nom, p.reference FROM commande_lignes l
           JOIN produits p ON p.id = l.produit_id WHERE l.commande_id = ? ORDER BY l.id""", (commande_id,))
    return render_template("commandes/detail.html", c=c, lignes=lignes)


@bp.route("/<int:commande_id>/envoyer", methods=["POST"])
@login_required
def envoyer(commande_id):
    get_commande_ou_404(commande_id)
    db = get_db()
    cur = db.execute("UPDATE commandes SET statut = 'envoyee' WHERE id = ? AND organisation_id = ? AND statut = 'brouillon'",
                     (commande_id, org_id()))
    if cur.rowcount:
        journaliser(db, "Commande envoyée", f"Commande #{commande_id}")
        db.commit()
        flash("Commande marquée comme envoyée au fournisseur.", "success")
    return redirect(url_for("commandes.detail", commande_id=commande_id))


@bp.route("/<int:commande_id>/recevoir", methods=["POST"])
@login_required
def recevoir(commande_id):
    c = get_commande_ou_404(commande_id)
    db = get_db()
    # UPDATE conditionnel: impossible de réceptionner 2 fois
    cur = db.execute(
        """UPDATE commandes SET statut = 'recue', recue_le = CURRENT_TIMESTAMP
           WHERE id = ? AND organisation_id = ? AND statut IN ('brouillon', 'envoyee')""",
        (commande_id, org_id()))
    if cur.rowcount == 0:
        flash("Cette commande ne peut pas être réceptionnée.", "error")
        return redirect(url_for("commandes.detail", commande_id=commande_id))
    for l in db.query("SELECT produit_id, quantite, prix_achat FROM commande_lignes WHERE commande_id = ?",
                      (commande_id,)):
        db.execute("UPDATE produits SET quantite = quantite + ?, prix_achat = ? WHERE id = ? AND organisation_id = ?",
                   (l["quantite"], l["prix_achat"], l["produit_id"], org_id()))
        db.execute(
            """INSERT INTO mouvements (produit_id, type, quantite, user_id, note, organisation_id)
               VALUES (?,?,?,?,?,?)""",
            (l["produit_id"], "entree", l["quantite"], g.user["id"],
             f"Réception BC-{c['numero']:04d}", org_id()))
    journaliser(db, "Réception commande", f"BC-{c['numero']:04d}")
    db.commit()
    flash("Commande réceptionnée: le stock a été augmenté.", "success")
    return redirect(url_for("commandes.detail", commande_id=commande_id))


@bp.route("/<int:commande_id>/annuler", methods=["POST"])
@login_required
def annuler(commande_id):
    c = get_commande_ou_404(commande_id)
    db = get_db()
    cur = db.execute(
        "UPDATE commandes SET statut = 'annulee' WHERE id = ? AND organisation_id = ? AND statut IN ('brouillon', 'envoyee')",
        (commande_id, org_id()))
    if cur.rowcount:
        journaliser(db, "Commande annulée", f"BC-{c['numero']:04d}")
        db.commit()
        flash("Commande annulée.", "success")
    return redirect(url_for("commandes.detail", commande_id=commande_id))
