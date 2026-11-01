"""Import CSV de produits (plan Pro)."""
import csv
import io
import unicodedata

from flask import (Blueprint, render_template, request, redirect, url_for, flash, g, Response)

from .db import get_db
from .utils import login_required, admin_required, org_id, est_pro, journaliser

bp = Blueprint("import_csv", __name__, url_prefix="/produits/import")
MAX_LIGNES = 500


def norm(texte):
    t = unicodedata.normalize("NFKD", (texte or "").strip().lower())
    return "".join(c for c in t if not unicodedata.combining(c)).replace(" ", "_")


def nombre(valeur, defaut=0.0):
    v = (valeur or "").strip().replace(",", ".")
    return float(v) if v else defaut


@bp.route("/", methods=["GET", "POST"])
@admin_required
def index():
    if request.method == "POST":
        if not est_pro():
            flash("L'import CSV est réservé au plan Pro.", "error")
            return redirect(url_for("abonnement.index"))
        fichier = request.files.get("fichier")
        if not fichier or not fichier.filename:
            flash("Choisissez un fichier CSV.", "error")
            return redirect(url_for("import_csv.index"))
        brut = fichier.read().decode("utf-8-sig", errors="replace")
        premiere = brut.splitlines()[0] if brut.strip() else ""
        delim = ";" if premiere.count(";") >= premiere.count(",") else ","
        lecteur = csv.DictReader(io.StringIO(brut), delimiter=delim)
        lecteur.fieldnames = [norm(n) for n in (lecteur.fieldnames or [])]
        if "nom" not in lecteur.fieldnames:
            flash("Colonne « nom » introuvable. Téléchargez le modèle CSV.", "error")
            return redirect(url_for("import_csv.index"))

        db = get_db()
        cats = {c["nom"].lower(): c["id"] for c in
                db.query("SELECT id, nom FROM categories WHERE organisation_id = ?", (org_id(),))}
        importes, erreurs = 0, []
        for i, ligne in enumerate(lecteur, start=2):
            if i - 1 > MAX_LIGNES:
                erreurs.append(f"Limite de {MAX_LIGNES} lignes atteinte, le reste est ignoré.")
                break
            nom = (ligne.get("nom") or "").strip()
            if not nom:
                continue
            try:
                pa, pv = nombre(ligne.get("prix_achat")), nombre(ligne.get("prix_vente"))
                qte = int(nombre(ligne.get("quantite")))
                seuil = int(nombre(ligne.get("seuil_alerte"), 5))
                if min(pa, pv, qte, seuil) < 0:
                    raise ValueError
            except ValueError:
                erreurs.append(f"Ligne {i} ({nom}): valeur numérique invalide")
                continue
            cat_nom = (ligne.get("categorie") or "").strip()
            cat_id = None
            if cat_nom:
                if cat_nom.lower() not in cats:
                    cats[cat_nom.lower()] = db.insert(
                        "INSERT INTO categories (nom, organisation_id) VALUES (?,?)", (cat_nom, org_id()))
                cat_id = cats[cat_nom.lower()]
            pid = db.insert(
                """INSERT INTO produits (nom, reference, prix_achat, prix_vente, quantite, seuil_alerte,
                   categorie_id, organisation_id) VALUES (?,?,?,?,?,?,?,?)""",
                (nom, (ligne.get("reference") or "").strip(), pa, pv, qte, seuil, cat_id, org_id()))
            if qte > 0:
                db.execute(
                    """INSERT INTO mouvements (produit_id, type, quantite, user_id, note, organisation_id)
                       VALUES (?,?,?,?,?,?)""", (pid, "entree", qte, g.user["id"], "Import CSV", org_id()))
            importes += 1
        if importes:
            journaliser(db, "Import CSV", f"{importes} produit(s) importé(s)")
        db.commit()
        flash(f"{importes} produit(s) importé(s)." + (f" {len(erreurs)} ligne(s) ignorée(s)." if erreurs else ""),
              "success" if importes else "error")
        for e in erreurs[:5]:
            flash(e, "error")
        return redirect(url_for("produits.liste"))
    return render_template("produits/import.html")


@bp.route("/modele")
@login_required
def modele():
    contenu = ("\ufeffnom;reference;categorie;prix_achat;prix_vente;quantite;seuil_alerte\n"
               "Stylo bleu;ST-001;Papeterie;0,5;1,2;100;20\n"
               "Cahier 100p;CA-100;Papeterie;1,8;3;50;10\n")
    return Response(contenu, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=modele_produits.csv"})
