import csv
import io
from functools import wraps

from flask import g, redirect, url_for, flash, Response, request


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if g.user["role"] != "admin":
            flash("Action réservée à l'administrateur.", "error")
            return redirect(url_for("main.dashboard"))
        return f(*args, **kwargs)
    return login_required(wrapper)


def org_id():
    return g.user["organisation_id"]


def est_pro():
    return g.user["plan"] == "pro"


def paginer(db, select_sql, count_sql, params, par_page):
    """Yرجّa3 dict: rows, page, pages, total."""
    page = max(1, request.args.get("page", 1, type=int))
    total = db.one(count_sql, params)["n"]
    pages = max(1, -(-total // par_page))
    page = min(page, pages)
    items = db.query(select_sql + " LIMIT ? OFFSET ?",
                     list(params) + [par_page, (page - 1) * par_page])
    return dict(rows=items, page=page, pages=pages, total=total)


def id_de_org(table, valeur):
    """Yرجّa3 l'id ken yخص el société, sinon None (sécurité multi-tenant)."""
    from .db import get_db
    if table not in ("categories", "fournisseurs", "produits", "clients"):
        return None
    if not valeur or not str(valeur).isdigit():
        return None
    ligne = get_db().one(f"SELECT id FROM {table} WHERE id = ? AND organisation_id = ?",
                         (int(valeur), org_id()))
    return ligne["id"] if ligne else None


def csv_response(nom_fichier, entetes, lignes):
    sortie = io.StringIO()
    w = csv.writer(sortie, delimiter=";")
    w.writerow(entetes)
    w.writerows(lignes)
    contenu = "\ufeff" + sortie.getvalue()  # BOM: Excel yقra les accents
    return Response(contenu, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename={nom_fichier}"})


def next_sur(cible, defaut):
    """Redirection sûre (relative bark)."""
    if cible and cible.startswith("/") and not cible.startswith("//"):
        return cible
    return defaut


def journaliser(db, action, detail=""):
    """Ysajjel 7aja fel journal d'activité (el caller yعمل commit)."""
    db.execute("INSERT INTO journal (action, detail, user_id, organisation_id) VALUES (?,?,?,?)",
               (action, detail, g.user["id"], g.user["organisation_id"]))


def lire_lignes():
    """Yقra les lignes (produit_id[], quantite[], prix[]) mel formulaire.
    Yرجّa3: liste de dicts, [] ken fadya, None ken fama ligne ghalta."""
    ids = request.form.getlist("produit_id")
    qtes = request.form.getlist("quantite")
    prix = request.form.getlist("prix")
    lignes = {}
    for pid, q, pr in zip(ids, qtes, prix):
        if not pid:
            continue
        try:
            q, pr = int(q), float(pr)
        except ValueError:
            return None
        pid_ok = id_de_org("produits", pid)
        if pid_ok is None or q <= 0 or pr < 0:
            return None
        if pid_ok in lignes:
            lignes[pid_ok]["quantite"] += q
        else:
            lignes[pid_ok] = dict(produit_id=pid_ok, quantite=q, prix=pr)
    return list(lignes.values())
