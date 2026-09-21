"""Public landing page - no login required."""
from flask import render_template
from flask_login import current_user

from app.main import main_bp


@main_bp.route("/")
def landing():
    """Home page. Logged-in users get sent straight to their dashboard."""
    if current_user.is_authenticated:
        if current_user.is_candidate():
            from flask import redirect, url_for
            return redirect(url_for("candidates.dashboard"))
        else:
            from flask import redirect, url_for
            return redirect(url_for("employer.dashboard"))
    return render_template("index.html")
