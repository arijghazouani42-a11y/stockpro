"""Frais de scolarité: paiements, reçus, impayés."""
from flask import (Blueprint, render_template, request, redirect, url_for, flash, abort,
                   current_app, g)

from .calculs import soldes
from .db import get_db
from .utils import (login_required, gestion_required, admin_required, ecole, est_pro, paginer,
                    id_de_ecole, date_ok, nombre, aujourdhui, csv_response, journaliser, next_sur)

bp = Blueprint("paiements", __name__, url_prefix="/paiements")
MODES = ("especes", "cheque", "virement", "carte")

CORPS = """FROM paiements p JOIN eleves e ON e.id = p.eleve_id LEFT JOIN classes c ON c.id = e.classe_id
           LEFT JOIN utilisateurs u ON u.id = p.user_id WHERE p.ecole_id = ?"""
CHAMPS = "SELECT p.*, e.nom, e.prenom, e.matricule, c.nom AS classe_nom, u.nom AS user_nom "


def acces_finance():
    """Les enseignants n'ont pas accès aux finances."""
    if g.user["role"] == "enseignant":
        abort(403)


@bp.before_request
def verifier_acces():
    if g.user is not None:
        acces_finance()


@bp.route("/")
@login_required
def liste():
    db = get_db()
    statut = request.args.get("statut", "").strip()
    q = request.args.get("q", "").strip().lower()
    corps = CORPS + " AND (lower(e.nom) LIKE ? OR lower(e.prenom) LIKE ?)"
    params = [ecole(), f"%{q}%", f"%{q}%"]
    if statut in ("valide", "annule"):
        corps += " AND p.statut = ?"
        params.append(statut)
    page = paginer(db, CHAMPS + corps + " ORDER BY p.id DESC", "SELECT COUNT(*) AS n " + corps,
                   params, current_app.config["PAR_PAGE"])
    total = db.one("SELECT COALESCE(SUM(montant), 0) AS t FROM paiements WHERE ecole_id = ? AND statut = 'valide'",
                   (ecole(),))["t"]
    return render_template("paiements/liste.html", page=page, statut=statut, q=q, total=total)


@bp.route("/export")
@login_required
def export():
    if not est_pro():
        flash("L'export CSV est réservé au plan Pro.", "error")
        return redirect(url_for("abonnement.index"))
    rows = get_db().query(CHAMPS + CORPS + " ORDER BY p.id", (ecole(),))
    return csv_response("paiements.csv",
                        ["Reçu", "Date", "Élève", "Classe", "Montant", "Motif", "Mode", "Statut"],
                        [[f"REC-{p['numero']:04d}", p["date_paiement"], f"{p['prenom']} {p['nom']}",
                          p["classe_nom"] or "", p["montant"], p["motif"] or "", p["mode"], p["statut"]]
                         for p in rows])


@bp.route("/impayes")
@login_required
def impayes():
    lignes = [s for s in soldes(get_db(), ecole()) if s["reste"] > 0]
    lignes.sort(key=lambda s: s["reste"], reverse=True)
    return render_template("paiements/impayes.html", lignes=lignes,
                           total=sum(s["reste"] for s in lignes))


@bp.route("/nouveau", methods=["GET", "POST"])
@gestion_required
def nouveau():
    db = get_db()
    if request.method == "POST":
        eleve_id = id_de_ecole("eleves", request.form.get("eleve_id"))
        motif = request.form.get("motif", "").strip() or "Frais de scolarité"
        mode = request.form.get("mode") if request.form.get("mode") in MODES else "especes"
        jour = request.form.get("date_paiement", "").strip() or aujourdhui()
        try:
            montant = nombre(request.form.get("montant", ""))
        except ValueError:
            montant = 0
        retour = url_for("paiements.nouveau", eleve=eleve_id or "")
        if not eleve_id or montant <= 0 or not date_ok(jour):
            flash("Données invalides (élève, montant > 0, date).", "error")
            return redirect(retour)
        solde = soldes(db, ecole(), eleve_id)
        if not solde:
            flash("Cet élève est inactif.", "error")
            return redirect(retour)
        if montant > solde[0]["reste"] + 1e-9:
            flash(f"Le montant dépasse le reste à payer ({solde[0]['reste']:.2f} DT).", "error")
            return redirect(retour)
        numero = db.one("SELECT COALESCE(MAX(numero), 0) + 1 AS n FROM paiements WHERE ecole_id = ?",
                        (ecole(),))["n"]
        pid = db.insert(
            """INSERT INTO paiements (numero, eleve_id, montant, motif, mode, date_paiement, user_id, ecole_id)
               VALUES (?,?,?,?,?,?,?,?)""",
            (numero, eleve_id, round(montant, 2), motif, mode, jour, g.user["id"], ecole()))
        journaliser(db, "Paiement", f"REC-{numero:04d} · {montant:.2f} DT")
        db.commit()
        flash(f"Paiement REC-{numero:04d} enregistré.", "success")
        return redirect(url_for("paiements.recu", paiement_id=pid))
    lignes = soldes(db, ecole())
    return render_template("paiements/form.html", lignes=lignes, preselection=request.args.get("eleve", ""),
                           today=aujourdhui(), modes=MODES)


@bp.route("/<int:paiement_id>")
@login_required
def recu(paiement_id):
    p = get_db().one(CHAMPS + CORPS + " AND p.id = ?", (ecole(), paiement_id))
    if p is None:
        abort(404)
    solde = soldes(get_db(), ecole(), p["eleve_id"])
    return render_template("paiements/recu.html", p=p, solde=solde[0] if solde else None)


@bp.route("/<int:paiement_id>/annuler", methods=["POST"])
@admin_required
def annuler(paiement_id):
    db = get_db()
    p = db.one("SELECT * FROM paiements WHERE id = ? AND ecole_id = ?", (paiement_id, ecole()))
    if p is None:
        abort(404)
    cur = db.execute("UPDATE paiements SET statut = 'annule' WHERE id = ? AND ecole_id = ? AND statut = 'valide'",
                     (paiement_id, ecole()))
    if cur.rowcount:
        journaliser(db, "Paiement annulé", f"REC-{p['numero']:04d}")
        db.commit()
        flash("Paiement annulé.", "success")
    else:
        flash("Ce paiement est déjà annulé.", "error")
    return redirect(next_sur(request.form.get("next"), url_for("paiements.recu", paiement_id=paiement_id)))
