from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, g, current_app)

from .db import get_db
from .utils import login_required, org_id, est_pro, paginer, id_de_org, csv_response, next_sur

bp = Blueprint("mouvements", __name__, url_prefix="/mouvements")

CORPS = """FROM mouvements m
           JOIN produits p ON p.id = m.produit_id
           LEFT JOIN users u ON u.id = m.user_id
           WHERE m.organisation_id = ?"""
CHAMPS = "SELECT m.*, p.nom AS produit_nom, u.nom AS user_nom "


@bp.route("/")
@login_required
def liste():
    db = get_db()
    produit = request.args.get("produit", "").strip()
    type_ = request.args.get("type", "").strip()
    corps, params = CORPS, [org_id()]
    if produit.isdigit():
        corps += " AND m.produit_id = ?"
        params.append(int(produit))
    if type_ in ("entree", "sortie"):
        corps += " AND m.type = ?"
        params.append(type_)
    page = paginer(db, CHAMPS + corps + " ORDER BY m.id DESC",
                   "SELECT COUNT(*) AS n " + corps, params, current_app.config["PAR_PAGE"])
    produits = db.query("SELECT id, nom, quantite FROM produits WHERE organisation_id = ? ORDER BY nom",
                        (org_id(),))
    return render_template("mouvements/liste.html", page=page, produits=produits,
                           filtre_produit=produit, filtre_type=type_)


@bp.route("/nouveau", methods=["POST"])
@login_required
def creer():
    db = get_db()
    retour = next_sur(request.form.get("next"), url_for("mouvements.liste"))
    try:
        qte = int(request.form["quantite"])
    except (ValueError, KeyError):
        flash("Quantité invalide", "error")
        return redirect(retour)
    pid = id_de_org("produits", request.form.get("produit_id"))
    type_ = request.form.get("type")
    note = request.form.get("note", "").strip()
    if pid is None or qte <= 0 or type_ not in ("entree", "sortie"):
        flash("Données invalides", "error")
        return redirect(retour)

    if type_ == "sortie":
        # UPDATE conditionnel: el stock ma yweliش négatif méme ken fama 2 users fi nafs el wa9t
        cur = db.execute(
            """UPDATE produits SET quantite = quantite - ?
               WHERE id = ? AND organisation_id = ? AND quantite >= ?""",
            (qte, pid, org_id(), qte))
        if cur.rowcount == 0:
            dispo = db.one("SELECT quantite FROM produits WHERE id = ?", (pid,))["quantite"]
            db.rollback()
            flash(f"Stock insuffisant ({dispo} disponible)", "error")
            return redirect(retour)
    else:
        db.execute("UPDATE produits SET quantite = quantite + ? WHERE id = ? AND organisation_id = ?",
                   (qte, pid, org_id()))
    db.execute(
        """INSERT INTO mouvements (produit_id, type, quantite, user_id, note, organisation_id)
           VALUES (?,?,?,?,?,?)""",
        (pid, type_, qte, g.user["id"], note, org_id()))
    db.commit()
    flash("Mouvement enregistré", "success")
    return redirect(retour)


@bp.route("/export")
@login_required
def export():
    if not est_pro():
        flash("L'export CSV est réservé au plan Pro.", "error")
        return redirect(url_for("abonnement.index"))
    rows = get_db().query(CHAMPS + CORPS + " ORDER BY m.id DESC", (org_id(),))
    return csv_response("mouvements.csv",
                        ["Date", "Produit", "Type", "Quantité", "Utilisateur", "Note"],
                        [[str(m["cree_le"])[:19], m["produit_nom"], m["type"], m["quantite"],
                          m["user_nom"] or "", m["note"] or ""] for m in rows])
