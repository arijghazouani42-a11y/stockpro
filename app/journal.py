from flask import Blueprint, render_template

from .db import get_db
from .utils import admin_required, ecole, paginer

bp = Blueprint("journal", __name__, url_prefix="/journal")


@bp.route("/")
@admin_required
def index():
    corps = "FROM journal_ecole j LEFT JOIN utilisateurs u ON u.id = j.user_id WHERE j.ecole_id = ?"
    page = paginer(get_db(), "SELECT j.*, u.nom AS user_nom " + corps + " ORDER BY j.id DESC",
                   "SELECT COUNT(*) AS n " + corps, [ecole()], 15)
    return render_template("journal/index.html", page=page)
