"""Inventaire physique: on saisit les quantités comptées, el app tخلق les ajustements."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g

from .db import get_db
from .utils import admin_required, org_id, journaliser

bp = Blueprint("inventaire", __name__, url_prefix="/inventaire")


@bp.route("/", methods=["GET", "POST"])
@admin_required
def index():
    db = get_db()
    if request.method == "POST":
        ajustes = 0
        for p in db.query("SELECT id, nom, quantite FROM produits WHERE organisation_id = ?", (org_id(),)):
            valeur = request.form.get(f"compte_{p['id']}", "").strip()
            if valeur == "":
                continue
            try:
                compte = int(valeur)
            except ValueError:
                continue
            if compte < 0 or compte == p["quantite"]:
                continue
            ecart = compte - p["quantite"]
            db.execute("UPDATE produits SET quantite = ? WHERE id = ? AND organisation_id = ?",
                       (compte, p["id"], org_id()))
            db.execute(
                """INSERT INTO mouvements (produit_id, type, quantite, user_id, note, organisation_id)
                   VALUES (?,?,?,?,?,?)""",
                (p["id"], "entree" if ecart > 0 else "sortie", abs(ecart), g.user["id"],
                 f"Ajustement inventaire (compté: {compte})", org_id()))
            ajustes += 1
        if ajustes:
            journaliser(db, "Inventaire", f"{ajustes} produit(s) ajusté(s)")
            db.commit()
            flash(f"Inventaire enregistré: {ajustes} produit(s) ajusté(s).", "success")
        else:
            flash("Aucun écart détecté.", "info")
        return redirect(url_for("inventaire.index"))

    q = request.args.get("q", "").strip().lower()
    produits = db.query(
        """SELECT * FROM produits WHERE organisation_id = ? AND lower(nom) LIKE ? ORDER BY nom""",
        (org_id(), f"%{q}%"))
    return render_template("inventaire/index.html", produits=produits, q=q)
