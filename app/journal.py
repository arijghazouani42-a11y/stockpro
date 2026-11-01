from flask import Blueprint, render_template, current_app

from .db import get_db
from .utils import admin_required, org_id, paginer

bp = Blueprint("journal", __name__, url_prefix="/journal")


@bp.route("/")
@admin_required
def index():
    corps = "FROM journal j LEFT JOIN users u ON u.id = j.user_id WHERE j.organisation_id = ?"
    page = paginer(get_db(), "SELECT j.*, u.nom AS user_nom " + corps + " ORDER BY j.id DESC",
                   "SELECT COUNT(*) AS n " + corps, [org_id()], 15)
    return render_template("journal/index.html", page=page)
