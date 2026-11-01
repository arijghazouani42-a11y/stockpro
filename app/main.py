from datetime import datetime, timedelta, timezone

from flask import Blueprint, render_template, redirect, url_for, g

from .db import get_db
from .utils import login_required, org_id

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    if g.user:
        return redirect(url_for("main.dashboard"))
    return render_template("main/landing.html")


@bp.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    org = org_id()  # multi-tenancy: dima nfiltriw bih
    produits = db.query("SELECT * FROM produits WHERE organisation_id = ?", (org,))

    valeur_achat = sum(p["quantite"] * float(p["prix_achat"] or 0) for p in produits)
    valeur_vente = sum(p["quantite"] * float(p["prix_vente"] or 0) for p in produits)
    en_alerte = [p for p in produits if p["quantite"] <= p["seuil_alerte"]]
    top = sorted(produits, key=lambda p: p["quantite"], reverse=True)[:6]
    max_q = max([p["quantite"] for p in top] + [1])

    stats = {"entree": 0, "sortie": 0}
    for r in db.query(
            f"""SELECT type, COALESCE(SUM(quantite),0) AS total FROM mouvements
                WHERE organisation_id = ? AND cree_le >= {db.il_y_a(30)} GROUP BY type""", (org,)):
        stats[r["type"]] = int(r["total"])

    # Chart 1: mouvements des 7 derniers jours
    aujourdhui = datetime.now(timezone.utc).date()
    jours = [aujourdhui - timedelta(days=i) for i in range(6, -1, -1)]
    par_jour = {(str(j), t): 0 for j in jours for t in ("entree", "sortie")}
    for r in db.query(
            f"""SELECT date(cree_le) AS jour, type, SUM(quantite) AS total FROM mouvements
                WHERE organisation_id = ? AND cree_le >= {db.il_y_a(8)}
                GROUP BY date(cree_le), type""", (org,)):
        cle = (str(r["jour"]), r["type"])
        if cle in par_jour:
            par_jour[cle] = int(r["total"])
    chart_jours = dict(
        labels=[j.strftime("%d/%m") for j in jours],
        entrees=[par_jour[(str(j), "entree")] for j in jours],
        sorties=[par_jour[(str(j), "sortie")] for j in jours],
    )

    # Chart 2: valeur du stock par catégorie
    chart_cat = {"labels": [], "valeurs": []}
    for r in db.query(
            """SELECT COALESCE(c.nom, 'Sans catégorie') AS nom,
                      SUM(p.quantite * p.prix_achat) AS valeur
               FROM produits p LEFT JOIN categories c ON c.id = p.categorie_id
               WHERE p.organisation_id = ?
               GROUP BY COALESCE(c.nom, 'Sans catégorie')""", (org,)):
        if r["valeur"] and float(r["valeur"]) > 0:
            chart_cat["labels"].append(r["nom"])
            chart_cat["valeurs"].append(round(float(r["valeur"]), 2))

    ca30 = db.one(
        f"""SELECT COALESCE(SUM(total), 0) AS ca FROM ventes
            WHERE organisation_id = ? AND statut <> 'annulee' AND cree_le >= {db.il_y_a(30)}""", (org,))["ca"]
    impayes = db.one(
        """SELECT COUNT(*) AS n, COALESCE(SUM(total), 0) AS montant FROM ventes
           WHERE organisation_id = ? AND statut = 'impayee'""", (org,))
    commandes_attente = db.one(
        "SELECT COUNT(*) AS n FROM commandes WHERE organisation_id = ? AND statut IN ('brouillon','envoyee')",
        (org,))["n"]

    derniers = db.query(
        """SELECT m.*, p.nom AS produit_nom, u.nom AS user_nom FROM mouvements m
           JOIN produits p ON p.id = m.produit_id
           LEFT JOIN users u ON u.id = m.user_id
           WHERE m.organisation_id = ? ORDER BY m.id DESC LIMIT 6""", (org,))
    return render_template("main/dashboard.html", nb_produits=len(produits),
                           valeur_achat=valeur_achat, valeur_vente=valeur_vente,
                           en_alerte=en_alerte, top=top, max_q=max_q, stats=stats,
                           chart_jours=chart_jours, chart_cat=chart_cat, derniers=derniers,
                           ca30=float(ca30), impayes=impayes, commandes_attente=commandes_attente)


@bp.route("/rapports")
@login_required
def rapports():
    db = get_db()
    org = org_id()
    lignes = db.query(
        """SELECT p.nom, p.quantite, p.prix_achat, p.prix_vente,
                  p.quantite * p.prix_achat AS val_achat,
                  p.quantite * p.prix_vente AS val_vente,
                  p.quantite * (p.prix_vente - p.prix_achat) AS marge
           FROM produits p WHERE p.organisation_id = ? ORDER BY marge DESC""", (org,))
    totaux = dict(
        achat=sum(float(r["val_achat"] or 0) for r in lignes),
        vente=sum(float(r["val_vente"] or 0) for r in lignes),
        marge=sum(float(r["marge"] or 0) for r in lignes),
    )
    ruptures = db.query("SELECT * FROM produits WHERE organisation_id = ? AND quantite = 0 ORDER BY nom", (org,))
    dormants = db.query(
        f"""SELECT p.* FROM produits p WHERE p.organisation_id = ?
            AND NOT EXISTS (SELECT 1 FROM mouvements m WHERE m.produit_id = p.id
                            AND m.cree_le >= {db.il_y_a(30)})
            ORDER BY p.nom""", (org,))
    top_produits = db.query(
        f"""SELECT p.nom, SUM(l.quantite) AS qte, SUM(l.quantite * l.prix_unitaire) AS ca
            FROM vente_lignes l JOIN ventes v ON v.id = l.vente_id JOIN produits p ON p.id = l.produit_id
            WHERE v.organisation_id = ? AND v.statut <> 'annulee' AND v.cree_le >= {db.il_y_a(30)}
            GROUP BY p.id, p.nom ORDER BY qte DESC LIMIT 5""", (org,))
    top_clients = db.query(
        """SELECT c.nom, COUNT(v.id) AS nb, SUM(v.total) AS ca
           FROM ventes v JOIN clients c ON c.id = v.client_id
           WHERE v.organisation_id = ? AND v.statut <> 'annulee'
           GROUP BY c.id, c.nom ORDER BY ca DESC LIMIT 5""", (org,))
    return render_template("main/rapports.html", lignes=lignes, totaux=totaux,
                           ruptures=ruptures, dormants=dormants,
                           top_produits=top_produits, top_clients=top_clients)
