import csv
import io
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import g, redirect, url_for, flash, Response, request

TUNIS = timezone(timedelta(hours=1))   # Tunisie: UTC+1
ROLES = ("admin", "secretaire", "enseignant")
ROLES_LABEL = {"admin": "Directeur / Admin", "secretaire": "Secrétaire", "enseignant": "Enseignant"}
JOURS = {1: "Lundi", 2: "Mardi", 3: "Mercredi", 4: "Jeudi", 5: "Vendredi", 6: "Samedi"}


def aujourdhui():
    return datetime.now(TUNIS).date().isoformat()


def date_ok(s):
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


def heure_ok(s):
    try:
        datetime.strptime(s, "%H:%M")
        return True
    except (ValueError, TypeError):
        return False


def nombre(s):
    """float men texte (yقbel el virgule)."""
    return float(str(s).strip().replace(",", "."))


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


def roles_required(*roles):
    """Restreint une route à certains rôles."""
    def decorateur(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if g.user["role"] not in roles:
                flash("Action non autorisée pour votre rôle.", "error")
                return redirect(url_for("main.dashboard"))
            return f(*args, **kwargs)
        return login_required(wrapper)
    return decorateur


admin_required = roles_required("admin")
gestion_required = roles_required("admin", "secretaire")      # élèves, classes, paiements...
pedagogie_required = roles_required("admin", "enseignant")     # notes
vie_scolaire_required = roles_required("admin", "secretaire", "enseignant")  # absences


def ecole():
    return g.user["ecole_id"]


def est_pro():
    return g.user["plan"] == "pro"


def paginer(db, select_sql, count_sql, params, par_page):
    """Yرجّa3 dict: rows, page, pages, total."""
    page = max(1, request.args.get("page", 1, type=int))
    total = db.one(count_sql, params)["n"]
    pages = max(1, -(-total // par_page))
    page = min(page, pages)
    rows = db.query(select_sql + " LIMIT ? OFFSET ?",
                    list(params) + [par_page, (page - 1) * par_page])
    return dict(rows=rows, page=page, pages=pages, total=total)


def id_de_ecole(table, valeur):
    """Yرجّa3 l'id ken yخص el école, sinon None (sécurité multi-tenant)."""
    from .db import get_db
    if table not in ("classes", "matieres", "enseignants", "eleves", "evaluations"):
        return None
    if not valeur or not str(valeur).isdigit():
        return None
    ligne = get_db().one(f"SELECT id FROM {table} WHERE id = ? AND ecole_id = ?",
                         (int(valeur), ecole()))
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
    db.execute("INSERT INTO journal_ecole (action, detail, user_id, ecole_id) VALUES (?,?,?,?)",
               (action, detail, g.user["id"], g.user["ecole_id"]))
