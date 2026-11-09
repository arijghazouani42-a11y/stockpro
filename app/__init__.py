import secrets
from datetime import datetime, timezone

from flask import Flask, g, session, request, abort, render_template
from markupsafe import Markup

from config import Config
from .db import close_db, get_db
from .utils import TUNIS, ROLES_LABEL, JOURS


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["DB_LABEL"] = ("Supabase (PostgreSQL)" if app.config["DATABASE_URL"]
                              else f"SQLite ({app.config['SQLITE_PATH']})")
    app.teardown_appcontext(close_db)

    # ----- Blueprints (kol partie fi module mostaqel) -----
    from . import (auth, main, referentiels, eleves, emploi, notes, absences,
                   paiements, abonnement, journal)
    for bp in (auth.bp, main.bp, referentiels.bp_classe, referentiels.bp_matiere,
               referentiels.bp_ens, eleves.bp, emploi.bp, notes.bp, absences.bp,
               paiements.bp, abonnement.bp, journal.bp):
        app.register_blueprint(bp)

    # ----- Protection CSRF simple -----
    @app.before_request
    def verifier_csrf():
        if request.method == "POST":
            envoye = request.form.get("csrf_token", "")
            attendu = session.get("csrf_token", "")
            if not attendu or not secrets.compare_digest(envoye, attendu):
                abort(400)

    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(16)
        return session["csrf_token"]

    @app.context_processor
    def globals_templates():
        nb_alertes = 0
        if getattr(g, "user", None):
            from .calculs import nb_alertes_absences
            nb_alertes = nb_alertes_absences(get_db(), g.user["ecole_id"],
                                             app.config["SEUIL_ABSENCES"])
        return dict(
            csrf_field=lambda: Markup(
                f'<input type="hidden" name="csrf_token" value="{csrf_token()}">'),
            nb_alertes=nb_alertes,
            LIMITE_FREE=app.config["LIMITE_FREE"],
            MAX_EQUIPE_FREE=app.config["MAX_EQUIPE_FREE"],
            SEUIL_ABSENCES=app.config["SEUIL_ABSENCES"],
            ROLES_LABEL=ROLES_LABEL,
            JOURS=JOURS,
            annee=datetime.now(TUNIS).year,
        )

    # ----- Filtres d'affichage -----
    def _en_datetime(v):
        if isinstance(v, str):
            v = datetime.fromisoformat(v)
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.astimezone(TUNIS)

    @app.template_filter("dt")
    def filtre_dt(v):
        return _en_datetime(v).strftime("%d/%m/%Y %H:%M") if v else ""

    @app.template_filter("jour")
    def filtre_jour(v):
        return _en_datetime(v).strftime("%d/%m/%Y") if v else ""

    @app.template_filter("datefr")
    def filtre_datefr(v):          # 'YYYY-MM-DD' -> 'DD/MM/YYYY'
        try:
            return datetime.strptime(str(v)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            return v or ""

    @app.template_filter("money")
    def filtre_money(v):
        return "{:,.2f}".format(float(v or 0)).replace(",", " ") + " DT"

    @app.template_filter("note")
    def filtre_note(v):
        return "-" if v is None else "{:.2f}".format(float(v))

    # ----- Pages d'erreur -----
    @app.errorhandler(404)
    def err_404(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def err_403(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(400)
    def err_400(e):
        return render_template("errors/400.html"), 400

    @app.errorhandler(500)
    def err_500(e):
        return render_template("errors/500.html"), 500

    return app
