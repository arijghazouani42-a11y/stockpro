"""Élèves: CRUD, fiche, bulletin, import / export CSV."""
import csv
import io
import unicodedata

from flask import (Blueprint, render_template, request, redirect, url_for, flash,
                   abort, g, current_app)

from .calculs import moyennes_classe, appreciation, soldes
from .db import get_db
from .utils import (login_required, gestion_required, admin_required, ecole, est_pro, paginer,
                    id_de_ecole, csv_response, journaliser, date_ok)

bp = Blueprint("eleves", __name__, url_prefix="/eleves")

TRIS = {"nom": "e.nom ASC, e.prenom ASC", "recent": "e.id DESC", "classe": "c.nom ASC, e.nom ASC"}
CORPS = "FROM eleves e LEFT JOIN classes c ON c.id = e.classe_id WHERE e.ecole_id = ?"
CHAMPS = "SELECT e.*, c.nom AS classe_nom "


@bp.route("/")
@login_required
def liste():
    db = get_db()
    q = request.args.get("q", "").strip().lower()
    classe = request.args.get("classe", "").strip()
    statut = request.args.get("statut", "actif").strip()
    tri = request.args.get("tri", "nom")
    if tri not in TRIS:
        tri = "nom"
    corps = CORPS + " AND (lower(e.nom) LIKE ? OR lower(e.prenom) LIKE ? OR lower(COALESCE(e.matricule, '')) LIKE ?)"
    params = [ecole(), f"%{q}%", f"%{q}%", f"%{q}%"]
    if classe.isdigit():
        corps += " AND e.classe_id = ?"
        params.append(int(classe))
    if statut in ("actif", "inactif"):
        corps += " AND e.statut = ?"
        params.append(statut)
    page = paginer(db, CHAMPS + corps + " ORDER BY " + TRIS[tri], "SELECT COUNT(*) AS n " + corps,
                   params, current_app.config["PAR_PAGE"])
    classes = db.query("SELECT * FROM classes WHERE ecole_id = ? ORDER BY nom", (ecole(),))
    return render_template("eleves/liste.html", page=page, q=q, classe=classe, statut=statut,
                           tri=tri, classes=classes)


@bp.route("/export")
@login_required
def export():
    if not est_pro():
        flash("L'export CSV est réservé au plan Pro.", "error")
        return redirect(url_for("abonnement.index"))
    rows = get_db().query(CHAMPS + CORPS + " ORDER BY e.nom, e.prenom", (ecole(),))
    return csv_response("eleves.csv",
                        ["Matricule", "Nom", "Prénom", "Date naissance", "Sexe", "Classe", "Parent",
                         "Tél parent", "Email", "Adresse", "Statut"],
                        [[e["matricule"], e["nom"], e["prenom"], e["date_naissance"] or "", e["sexe"] or "",
                          e["classe_nom"] or "", e["parent_nom"] or "", e["parent_tel"] or "",
                          e["email"] or "", e["adresse"] or "", e["statut"]] for e in rows])


def classe_pleine(db, classe_id, exclure_eleve=None):
    """Règle métier: une classe ne dépasse pas sa capacité."""
    if not classe_id:
        return False
    c = db.one("SELECT capacite FROM classes WHERE id = ?", (classe_id,))
    sql = "SELECT COUNT(*) AS n FROM eleves WHERE classe_id = ? AND statut = 'actif'"
    params = [classe_id]
    if exclure_eleve:
        sql += " AND id <> ?"
        params.append(exclure_eleve)
    return db.one(sql, params)["n"] >= (c["capacite"] or 0)


def lire_formulaire():
    f = request.form
    d = dict(
        nom=f["nom"].strip(), prenom=f["prenom"].strip(),
        date_naissance=f.get("date_naissance", "").strip(),
        sexe=f.get("sexe") if f.get("sexe") in ("M", "F") else "",
        classe_id=id_de_ecole("classes", f.get("classe_id")),
        parent_nom=f.get("parent_nom", "").strip(), parent_tel=f.get("parent_tel", "").strip(),
        email=f.get("email", "").strip(), adresse=f.get("adresse", "").strip(),
        statut="inactif" if f.get("statut") == "inactif" else "actif",
    )
    if not d["nom"] or not d["prenom"]:
        return None
    if d["date_naissance"] and not date_ok(d["date_naissance"]):
        return None
    return d


@bp.route("/ajouter", methods=["GET", "POST"])
@gestion_required
def ajouter():
    db = get_db()
    if request.method == "POST":
        if g.user["plan"] == "free":
            n = db.one("SELECT COUNT(*) AS n FROM eleves WHERE ecole_id = ?", (ecole(),))["n"]
            if n >= current_app.config["LIMITE_FREE"]:
                flash(f"Limite de {current_app.config['LIMITE_FREE']} élèves atteinte. Passez au Pro.", "error")
                return redirect(url_for("abonnement.index"))
        d = lire_formulaire()
        if d is None:
            flash("Données invalides (nom, prénom et date au format AAAA-MM-JJ)", "error")
            return redirect(url_for("eleves.ajouter"))
        if d["statut"] == "actif" and classe_pleine(db, d["classe_id"]):
            flash("Cette classe est complète (capacité atteinte).", "error")
            return redirect(url_for("eleves.ajouter"))
        numero = db.one("SELECT COALESCE(MAX(numero), 0) + 1 AS n FROM eleves WHERE ecole_id = ?", (ecole(),))["n"]
        debut = (g.user["annee_scolaire"] or "")[:4] or "0000"
        eid = db.insert(
            """INSERT INTO eleves (numero, matricule, nom, prenom, date_naissance, sexe, classe_id, parent_nom,
               parent_tel, email, adresse, statut, ecole_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (numero, f"{debut}-{numero:04d}", d["nom"], d["prenom"], d["date_naissance"], d["sexe"],
             d["classe_id"], d["parent_nom"], d["parent_tel"], d["email"], d["adresse"], d["statut"], ecole()))
        journaliser(db, "Élève inscrit", f"{d['prenom']} {d['nom']}")
        db.commit()
        flash("Élève inscrit", "success")
        return redirect(url_for("eleves.detail", eleve_id=eid))
    classes = db.query("SELECT * FROM classes WHERE ecole_id = ? ORDER BY nom", (ecole(),))
    return render_template("eleves/form.html", e=None, classes=classes)


def get_eleve_ou_404(eleve_id):
    e = get_db().one(CHAMPS + CORPS + " AND e.id = ?", (ecole(), eleve_id))
    if e is None:
        abort(404)
    return e


@bp.route("/<int:eleve_id>")
@login_required
def detail(eleve_id):
    e = get_eleve_ou_404(eleve_id)
    db = get_db()
    abs_stats = db.one(
        """SELECT COALESCE(SUM(CASE WHEN type = 'absence' AND justifiee = 0 THEN 1 ELSE 0 END), 0) AS non_just,
                  COALESCE(SUM(CASE WHEN type = 'absence' AND justifiee = 1 THEN 1 ELSE 0 END), 0) AS just,
                  COALESCE(SUM(CASE WHEN type = 'retard' THEN 1 ELSE 0 END), 0) AS retards
           FROM absences WHERE eleve_id = ? AND ecole_id = ?""", (eleve_id, ecole()))
    absences = db.query("SELECT * FROM absences WHERE eleve_id = ? AND ecole_id = ? ORDER BY date_abs DESC LIMIT 8",
                        (eleve_id, ecole()))
    notes = db.query(
        """SELECT n.valeur, ev.titre, ev.bareme, ev.trimestre, ev.date_eval, m.nom AS matiere_nom
           FROM notes n JOIN evaluations ev ON ev.id = n.evaluation_id
           JOIN matieres m ON m.id = ev.matiere_id
           WHERE n.eleve_id = ? AND ev.ecole_id = ? ORDER BY ev.id DESC LIMIT 8""", (eleve_id, ecole()))
    paiements = db.query(
        "SELECT * FROM paiements WHERE eleve_id = ? AND ecole_id = ? ORDER BY id DESC LIMIT 8", (eleve_id, ecole()))
    solde = soldes(db, ecole(), eleve_id)
    solde = solde[0] if solde else dict(du=0, paye=0, reste=0)
    return render_template("eleves/detail.html", e=e, abs_stats=abs_stats, absences=absences,
                           notes=notes, paiements=paiements, solde=solde)


@bp.route("/<int:eleve_id>/modifier", methods=["GET", "POST"])
@gestion_required
def modifier(eleve_id):
    e = get_eleve_ou_404(eleve_id)
    db = get_db()
    if request.method == "POST":
        d = lire_formulaire()
        if d is None:
            flash("Données invalides", "error")
            return redirect(url_for("eleves.modifier", eleve_id=eleve_id))
        if (d["statut"] == "actif" and d["classe_id"] != e["classe_id"]
                and classe_pleine(db, d["classe_id"], exclure_eleve=eleve_id)):
            flash("Cette classe est complète (capacité atteinte).", "error")
            return redirect(url_for("eleves.modifier", eleve_id=eleve_id))
        db.execute(
            """UPDATE eleves SET nom=?, prenom=?, date_naissance=?, sexe=?, classe_id=?, parent_nom=?,
               parent_tel=?, email=?, adresse=?, statut=? WHERE id=? AND ecole_id=?""",
            (d["nom"], d["prenom"], d["date_naissance"], d["sexe"], d["classe_id"], d["parent_nom"],
             d["parent_tel"], d["email"], d["adresse"], d["statut"], eleve_id, ecole()))
        journaliser(db, "Élève modifié", f"{d['prenom']} {d['nom']}")
        db.commit()
        flash("Élève modifié", "success")
        return redirect(url_for("eleves.detail", eleve_id=eleve_id))
    classes = db.query("SELECT * FROM classes WHERE ecole_id = ? ORDER BY nom", (ecole(),))
    return render_template("eleves/form.html", e=e, classes=classes)


@bp.route("/<int:eleve_id>/supprimer", methods=["POST"])
@admin_required
def supprimer(eleve_id):
    e = get_eleve_ou_404(eleve_id)
    db = get_db()
    if db.one("SELECT COUNT(*) AS n FROM paiements WHERE eleve_id = ?", (eleve_id,))["n"]:
        flash("Impossible de supprimer: cet élève a des paiements. Passez-le en « inactif » à la place.", "error")
        return redirect(url_for("eleves.detail", eleve_id=eleve_id))
    db.execute("DELETE FROM notes WHERE eleve_id = ?", (eleve_id,))
    db.execute("DELETE FROM absences WHERE eleve_id = ?", (eleve_id,))
    db.execute("DELETE FROM eleves WHERE id = ? AND ecole_id = ?", (eleve_id, ecole()))
    journaliser(db, "Élève supprimé", f"{e['prenom']} {e['nom']}")
    db.commit()
    flash("Élève supprimé", "success")
    return redirect(url_for("eleves.liste"))


@bp.route("/<int:eleve_id>/bulletin")
@login_required
def bulletin(eleve_id):
    e = get_eleve_ou_404(eleve_id)
    trimestre = request.args.get("trimestre", 1, type=int)
    if trimestre not in (0, 1, 2, 3):
        trimestre = 1
    db = get_db()
    calc = None
    lignes = []
    if e["classe_id"]:
        calc = moyennes_classe(db, ecole(), e["classe_id"], trimestre)
        res = calc["resultats"].get(eleve_id, dict(par_matiere={}, generale=None))
        # moyenne de la classe par matière
        for mid, moy in sorted(res["par_matiere"].items(), key=lambda x: calc["matieres"][x[0]]["nom"]):
            autres = [r["par_matiere"][mid] for r in calc["resultats"].values() if mid in r["par_matiere"]]
            lignes.append(dict(matiere=calc["matieres"][mid]["nom"], coef=calc["matieres"][mid]["coefficient"],
                               moyenne=moy, moy_classe=sum(autres) / len(autres), appreciation=appreciation(moy)))
        generale = res["generale"]
    else:
        generale = None
    abs_n = db.one(
        "SELECT COUNT(*) AS n FROM absences WHERE eleve_id = ? AND type = 'absence' AND justifiee = 0 AND ecole_id = ?",
        (eleve_id, ecole()))["n"]
    return render_template("eleves/bulletin.html", e=e, trimestre=trimestre, lignes=lignes,
                           generale=generale, appreciation=appreciation(generale), calc=calc,
                           rang=(calc["rang"].get(eleve_id) if calc else None), abs_n=abs_n)


# ---------- Import CSV (Pro) ----------
def norm(texte):
    t = unicodedata.normalize("NFKD", (texte or "").strip().lower())
    return "".join(c for c in t if not unicodedata.combining(c)).replace(" ", "_")


@bp.route("/import", methods=["GET", "POST"])
@admin_required
def importer():
    if request.method == "POST":
        if not est_pro():
            flash("L'import CSV est réservé au plan Pro.", "error")
            return redirect(url_for("abonnement.index"))
        fichier = request.files.get("fichier")
        if not fichier or not fichier.filename:
            flash("Choisissez un fichier CSV.", "error")
            return redirect(url_for("eleves.importer"))
        brut = fichier.read().decode("utf-8-sig", errors="replace")
        premiere = brut.splitlines()[0] if brut.strip() else ""
        delim = ";" if premiere.count(";") >= premiere.count(",") else ","
        lecteur = csv.DictReader(io.StringIO(brut), delimiter=delim)
        lecteur.fieldnames = [norm(n) for n in (lecteur.fieldnames or [])]
        if "nom" not in lecteur.fieldnames or "prenom" not in lecteur.fieldnames:
            flash("Colonnes « nom » et « prenom » introuvables. Téléchargez le modèle CSV.", "error")
            return redirect(url_for("eleves.importer"))

        db = get_db()
        classes = {c["nom"].lower(): c["id"] for c in
                   db.query("SELECT id, nom FROM classes WHERE ecole_id = ?", (ecole(),))}
        numero = db.one("SELECT COALESCE(MAX(numero), 0) AS n FROM eleves WHERE ecole_id = ?", (ecole(),))["n"]
        debut = (g.user["annee_scolaire"] or "")[:4] or "0000"
        importes, erreurs = 0, []
        for i, ligne in enumerate(lecteur, start=2):
            if i - 1 > 500:
                erreurs.append("Limite de 500 lignes atteinte, le reste est ignoré.")
                break
            nom, prenom = (ligne.get("nom") or "").strip(), (ligne.get("prenom") or "").strip()
            if not nom and not prenom:
                continue
            naissance = (ligne.get("date_naissance") or "").strip()
            if not nom or not prenom or (naissance and not date_ok(naissance)):
                erreurs.append(f"Ligne {i} ({prenom} {nom}): nom/prénom manquant ou date invalide (AAAA-MM-JJ)")
                continue
            cl = (ligne.get("classe") or "").strip()
            cid = None
            if cl:
                if cl.lower() not in classes:
                    classes[cl.lower()] = db.insert(
                        "INSERT INTO classes (nom, ecole_id) VALUES (?, ?)", (cl, ecole()))
                cid = classes[cl.lower()]
            numero += 1
            sexe = (ligne.get("sexe") or "").strip().upper()[:1]
            db.insert(
                """INSERT INTO eleves (numero, matricule, nom, prenom, date_naissance, sexe, classe_id, parent_nom,
                   parent_tel, email, adresse, ecole_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (numero, f"{debut}-{numero:04d}", nom, prenom, naissance, sexe if sexe in ("M", "F") else "",
                 cid, (ligne.get("parent_nom") or "").strip(), (ligne.get("parent_tel") or "").strip(),
                 (ligne.get("email") or "").strip(), (ligne.get("adresse") or "").strip(), ecole()))
            importes += 1
        if importes:
            journaliser(db, "Import CSV", f"{importes} élève(s) importé(s)")
        db.commit()
        flash(f"{importes} élève(s) importé(s)." + (f" {len(erreurs)} ligne(s) ignorée(s)." if erreurs else ""),
              "success" if importes else "error")
        for e in erreurs[:5]:
            flash(e, "error")
        return redirect(url_for("eleves.liste"))
    return render_template("eleves/import.html")


@bp.route("/import/modele")
@login_required
def modele():
    from flask import Response
    contenu = ("\ufeffnom;prenom;date_naissance;sexe;classe;parent_nom;parent_tel;email;adresse\n"
               "Ben Salah;Amine;2014-05-12;M;6A;Salah Ben Salah;22111222;;Tunis\n"
               "Trabelsi;Sara;2013-11-03;F;6A;Mounir Trabelsi;98123456;;Sfax\n")
    return Response(contenu, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=modele_eleves.csv"})
