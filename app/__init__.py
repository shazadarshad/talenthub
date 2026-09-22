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
from app.extensions import db, migrate, login_manager, csrf, limiter, mail


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
    mail.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "error"

    # Import every model here (not just User) so SQLAlchemy's metadata
    # knows about every table/column before create_all() runs below.
    # Without this, tables for models that aren't imported yet (e.g. if
    # blueprints hadn't been registered) could be missing from metadata.
    from app.models import User, CandidateProfile, Shortlist, ProfileView, Conversation, Message  # noqa: F401

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # --- Blueprints ---
    from app.main import main_bp
    from app.auth import auth_bp
    from app.candidates import candidates_bp
    from app.employer import employer_bp
    from app.messages import messages_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(candidates_bp, url_prefix="/candidates")
    app.register_blueprint(employer_bp, url_prefix="/employer")
    app.register_blueprint(messages_bp, url_prefix="/messages")

    @app.context_processor
    def inject_unread_message_count():
        """Makes the inbox unread count available in every template
        (e.g. for a badge in the nav bar), without every route needing
        to compute and pass it manually.
        """
        from flask_login import current_user
        if not current_user.is_authenticated:
            return {"unread_message_count": 0}

        from app.models import Conversation
        if current_user.is_employer():
            conversations = Conversation.query.filter_by(employer_id=current_user.id).all()
        else:
            conversations = Conversation.query.filter_by(candidate_id=current_user.id).all()

        count = sum(c.unread_count_for(current_user.id) for c in conversations)
        return {"unread_message_count": count}

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

    # Create any missing database tables automatically on startup.
    # This is safe to run every time - create_all() only creates tables
    # that don't exist yet, it never touches or drops existing data.
    with app.app_context():
        db.create_all()
        _sync_missing_columns(app)

        # One-time seed hook: only runs if SEED_CANDIDATES_ON_STARTUP=true
        # is set. This is how demo candidates get loaded into production
        # without needing a direct database connection or SSH access -
        # the app seeds itself once, then the env var gets removed.
        if os.environ.get("SEED_CANDIDATES_ON_STARTUP") == "true":
            try:
                from seed_candidates import seed
                seed(app=app)
            except Exception:
                app.logger.exception("Candidate seeding failed")

        # One-time AI backfill hook: only runs if BACKFILL_AI_ON_STARTUP=true
        # is set. Generates AI summaries for any candidate that has a CV
        # but no summary yet (e.g. seeded demo profiles).
        if os.environ.get("BACKFILL_AI_ON_STARTUP") == "true":
            try:
                from backfill_ai_summaries import backfill
                backfill(app=app)
            except Exception:
                app.logger.exception("AI summary backfill failed")

    return app


def _sync_missing_columns(app):
    """Add any model columns that are missing from the live database.

    db.create_all() only creates whole tables that don't exist yet - it
    won't add a new column to a table that's already there. Since this
    app doesn't run a full migration tool in production, this checks for
    a few known columns that were added after the tables were first
    created, and adds them if missing. Safe to run every startup: each
    column is only added if it isn't already there.
    """
    from sqlalchemy import text, inspect

    # This uses Postgres-specific information_schema queries, so skip it
    # entirely on SQLite (local dev/tests) - create_all() there is enough
    # since the whole file is usually fresh.
    if "sqlite" in app.config["SQLALCHEMY_DATABASE_URI"]:
        return

    columns_to_ensure = {
        "candidate_profiles": [
            ("ai_summary", "TEXT"),
            ("ai_skills", "VARCHAR(500)"),
            ("ai_experience_years", "INTEGER"),
            ("ai_generated_at", "TIMESTAMP"),
            ("portfolio_url", "VARCHAR(300)"),
        ],
        "shortlists": [
            ("note", "TEXT"),
        ],
    }

    inspector = inspect(db.engine)
    with db.engine.connect() as conn:
        for table_name, columns in columns_to_ensure.items():
            if table_name not in inspector.get_table_names():
                continue  # table doesn't exist yet, create_all() will handle it

            existing_columns = {c["name"] for c in inspector.get_columns(table_name)}
            for column_name, column_type in columns:
                if column_name in existing_columns:
                    continue
                conn.execute(text(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                ))
                conn.commit()
                app.logger.info(f"Added missing column {table_name}.{column_name}")
