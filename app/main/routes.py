"""Public landing page - no login required."""
from flask import render_template, redirect, url_for
from flask_login import current_user

from app.main import main_bp


@main_bp.route("/")
def landing():
    """Home page. Logged-in users get sent straight to their dashboard."""
    if current_user.is_authenticated:
        if current_user.is_candidate():
            return redirect(url_for("candidates.dashboard"))
        return redirect(url_for("employer.dashboard"))

    from app.models import User, CandidateProfile

    stats = {
        "candidate_count": User.query.filter_by(role="candidate").count(),
        "employer_count": User.query.filter_by(role="employer").count(),
        "role_count": (
            CandidateProfile.query.with_entities(CandidateProfile.role_wanted)
            .distinct()
            .count()
        ),
    }

    # A small, real preview of candidates so a logged-out visitor can see
    # the product actually has people in it, not just marketing copy.
    # Full profiles/contact details are only shown after signing up.
    preview_candidates = (
        CandidateProfile.query.order_by(CandidateProfile.submitted_on.desc())
        .limit(3)
        .all()
    )

    return render_template("index.html", stats=stats, preview_candidates=preview_candidates)
