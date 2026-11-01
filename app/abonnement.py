from flask import Blueprint, render_template, request, redirect, url_for, flash, g, current_app

from .db import get_db
from .utils import login_required, admin_required, org_id, journaliser

bp = Blueprint("abonnement", __name__, url_prefix="/abonnement")


@bp.route("/")
@login_required
def index():
    db = get_db()
    usage = dict(
        produits=db.one("SELECT COUNT(*) AS n FROM produits WHERE organisation_id = ?", (org_id(),))["n"],
        membres=db.one("SELECT COUNT(*) AS n FROM users WHERE organisation_id = ?", (org_id(),))["n"],
    )
    return render_template("abonnement/index.html", usage=usage)


@bp.route("/changer", methods=["POST"])
@admin_required
def changer():
    plan = request.form.get("plan")
    db = get_db()
    if plan == "free":
        n_prod = db.one("SELECT COUNT(*) AS n FROM produits WHERE organisation_id = ?", (org_id(),))["n"]
        n_users = db.one("SELECT COUNT(*) AS n FROM users WHERE organisation_id = ?", (org_id(),))["n"]
        if n_prod > current_app.config["LIMITE_FREE"]:
            flash(f"Impossible: vous avez {n_prod} produits (limite Free: {current_app.config['LIMITE_FREE']}).", "error")
            return redirect(url_for("abonnement.index"))
        if n_users > current_app.config["MAX_EQUIPE_FREE"]:
            flash("Impossible: supprimez d'abord les membres de l'équipe (Free = 1 utilisateur).", "error")
            return redirect(url_for("abonnement.index"))
    if plan in ("free", "pro"):
        db.execute("UPDATE organisations SET plan = ? WHERE id = ?", (plan, org_id()))
        journaliser(db, "Abonnement", f"Plan {plan.upper()}")
        db.commit()
        flash(f"Plan changé: {plan.capitalize()}", "success")
    return redirect(url_for("abonnement.index"))
