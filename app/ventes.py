"""Ventes / factures: chaque vente diminue le stock automatiquement."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, current_app, abort

from .db import get_db
from .utils import (login_required, admin_required, org_id, paginer, id_de_org,
                    lire_lignes, journaliser)

bp = Blueprint("ventes", __name__, url_prefix="/ventes")


def get_vente_ou_404(vente_id):
    v = get_db().one(
        """SELECT v.*, c.nom AS client_nom, c.telephone AS client_tel, c.email AS client_email,
                  c.adresse AS client_adresse, u.nom AS user_nom
           FROM ventes v LEFT JOIN clients c ON c.id = v.client_id
           LEFT JOIN users u ON u.id = v.user_id
           WHERE v.id = ? AND v.organisation_id = ?""", (vente_id, org_id()))
    if v is None:
        abort(404)
    return v


@bp.route("/")
@login_required
def liste():
    db = get_db()
    statut = request.args.get("statut", "").strip()
    corps = """FROM ventes v LEFT JOIN clients c ON c.id = v.client_id WHERE v.organisation_id = ?"""
    params = [org_id()]
    if statut in ("payee", "impayee", "annulee"):
        corps += " AND v.statut = ?"
        params.append(statut)
    page = paginer(db, "SELECT v.*, c.nom AS client_nom " + corps + " ORDER BY v.id DESC",
                   "SELECT COUNT(*) AS n " + corps, params, current_app.config["PAR_PAGE"])
    totaux = db.one(
        """SELECT COALESCE(SUM(CASE WHEN statut = 'payee' THEN total ELSE 0 END), 0) AS payees,
                  COALESCE(SUM(CASE WHEN statut = 'impayee' THEN total ELSE 0 END), 0) AS impayees
           FROM ventes WHERE organisation_id = ?""", (org_id(),))
    return render_template("ventes/liste.html", page=page, statut=statut, totaux=totaux)


@bp.route("/nouvelle", methods=["GET", "POST"])
@login_required
def nouvelle():
    db = get_db()
    if request.method == "POST":
        lignes = lire_lignes()
        if not lignes:
            flash("Ajoutez au moins une ligne valide (produit, quantité, prix).", "error")
            return redirect(url_for("ventes.nouvelle"))
        client_id = id_de_org("clients", request.form.get("client_id"))
        statut = "impayee" if request.form.get("statut") == "impayee" else "payee"

        # 1) sorties de stock (conditionnelles: jamais de stock négatif)
        for l in lignes:
            cur = db.execute(
                """UPDATE produits SET quantite = quantite - ?
                   WHERE id = ? AND organisation_id = ? AND quantite >= ?""",
                (l["quantite"], l["produit_id"], org_id(), l["quantite"]))
            if cur.rowcount == 0:
                p = db.one("SELECT nom, quantite FROM produits WHERE id = ?", (l["produit_id"],))
                db.rollback()
                flash(f"Stock insuffisant pour « {p['nom']} » ({p['quantite']} disponible).", "error")
                return redirect(url_for("ventes.nouvelle"))

        # 2) la vente + ses lignes + les mouvements
        numero = db.one("SELECT COALESCE(MAX(numero), 0) + 1 AS n FROM ventes WHERE organisation_id = ?",
                        (org_id(),))["n"]
        total = round(sum(l["quantite"] * l["prix"] for l in lignes), 2)
        vid = db.insert(
            "INSERT INTO ventes (numero, client_id, statut, total, user_id, organisation_id) VALUES (?,?,?,?,?,?)",
            (numero, client_id, statut, total, g.user["id"], org_id()))
        for l in lignes:
            db.execute("INSERT INTO vente_lignes (vente_id, produit_id, quantite, prix_unitaire) VALUES (?,?,?,?)",
                       (vid, l["produit_id"], l["quantite"], l["prix"]))
            db.execute(
                """INSERT INTO mouvements (produit_id, type, quantite, user_id, note, organisation_id)
                   VALUES (?,?,?,?,?,?)""",
                (l["produit_id"], "sortie", l["quantite"], g.user["id"], f"Vente FAC-{numero:04d}", org_id()))
        journaliser(db, "Vente", f"FAC-{numero:04d} · {total:.2f} DT · {statut}")
        db.commit()
        flash(f"Vente FAC-{numero:04d} enregistrée. Le stock a été mis à jour.", "success")
        return redirect(url_for("ventes.detail", vente_id=vid))

    produits = db.query("SELECT id, nom, prix_vente, quantite FROM produits WHERE organisation_id = ? ORDER BY nom",
                        (org_id(),))
    clients = db.query("SELECT id, nom FROM clients WHERE organisation_id = ? ORDER BY nom", (org_id(),))
    produits_json = [dict(id=p["id"], nom=p["nom"], prix=float(p["prix_vente"] or 0), stock=p["quantite"])
                     for p in produits]
    return render_template("ventes/form.html", produits_json=produits_json, clients=clients)


@bp.route("/<int:vente_id>")
@login_required
def detail(vente_id):
    v = get_vente_ou_404(vente_id)
    lignes = get_db().query(
        """SELECT l.*, p.nom AS produit_nom, p.reference FROM vente_lignes l
           JOIN produits p ON p.id = l.produit_id WHERE l.vente_id = ? ORDER BY l.id""", (vente_id,))
    return render_template("ventes/facture.html", v=v, lignes=lignes)


@bp.route("/<int:vente_id>/payer", methods=["POST"])
@login_required
def payer(vente_id):
    get_vente_ou_404(vente_id)
    db = get_db()
    cur = db.execute("UPDATE ventes SET statut = 'payee' WHERE id = ? AND organisation_id = ? AND statut = 'impayee'",
                     (vente_id, org_id()))
    if cur.rowcount:
        journaliser(db, "Paiement", f"Vente #{vente_id} marquée payée")
        db.commit()
        flash("Vente marquée comme payée.", "success")
    return redirect(url_for("ventes.detail", vente_id=vente_id))


@bp.route("/<int:vente_id>/annuler", methods=["POST"])
@admin_required
def annuler(vente_id):
    v = get_vente_ou_404(vente_id)
    db = get_db()
    cur = db.execute("UPDATE ventes SET statut = 'annulee' WHERE id = ? AND organisation_id = ? AND statut <> 'annulee'",
                     (vente_id, org_id()))
    if cur.rowcount == 0:
        flash("Cette vente est déjà annulée.", "error")
    else:  # on remet le stock
        for l in db.query("SELECT produit_id, quantite FROM vente_lignes WHERE vente_id = ?", (vente_id,)):
            db.execute("UPDATE produits SET quantite = quantite + ? WHERE id = ? AND organisation_id = ?",
                       (l["quantite"], l["produit_id"], org_id()))
            db.execute(
                """INSERT INTO mouvements (produit_id, type, quantite, user_id, note, organisation_id)
                   VALUES (?,?,?,?,?,?)""",
                (l["produit_id"], "entree", l["quantite"], g.user["id"],
                 f"Annulation FAC-{v['numero']:04d}", org_id()))
        journaliser(db, "Annulation vente", f"FAC-{v['numero']:04d}")
        db.commit()
        flash("Vente annulée. Le stock a été remis.", "success")
    return redirect(url_for("ventes.detail", vente_id=vente_id))
