"""
The app factory. create_app() builds and configures the Flask app:
extensions, blueprints (routes), and error handlers all get wired up here.
Using a factory (instead of a global `app = Flask(__name__)`) makes it easy
to create separate app instances for running the server vs. running tests.
"""
import logging
import os

from flask import Flask, render_template

from config import config_by_name
from app.extensions import db, migrate, login_manager, csrf, limiter


def create_app(config_name=None):
    app = Flask(__name__)

    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app.config.from_object(config_by_name[config_name])

    # --- Extensions ---
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "error"

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # --- Blueprints ---
    from app.main import main_bp
    from app.auth import auth_bp
    from app.candidates import candidates_bp
    from app.employer import employer_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(candidates_bp, url_prefix="/candidates")
    app.register_blueprint(employer_bp, url_prefix="/employer")

    # --- Error handlers ---
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("Unhandled server error")
        return render_template("errors/500.html"), 500

    @app.errorhandler(413)
    def file_too_large(e):
        from flask import flash, redirect, url_for
        flash("That file is too large. Maximum upload size is 5 MB.", "error")
        return redirect(url_for("candidates.new_profile")), 302

    # --- Logging (writes to console; good enough for a small app) ---
    if not app.debug and not app.testing:
        logging.basicConfig(level=logging.INFO)

    # Make sure the folder for CV uploads exists.
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    return app
