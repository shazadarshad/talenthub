"""
Employer-only routes: browse and filter candidates, view a full profile
(which logs a "profile view" so the candidate can see interest), shortlist
candidates, and download CVs.
"""
from flask import render_template, redirect, url_for, flash, request, abort, send_from_directory, current_app
from flask_login import login_required, current_user

from app.employer import employer_bp
from app.extensions import db
from app.models import CandidateProfile, Shortlist, ProfileView
from app.forms import EXPERIENCE_LEVELS
from app.utils import role_required
from app.ai import rank_candidates

# Smart search only makes sense on a reasonably small pool of candidates -
# it sends their profiles to the AI in one request, so we cap how many
# get considered to keep it fast and affordable.
SMART_SEARCH_MAX_CANDIDATES = 40


@employer_bp.route("/browse")
@login_required
@role_required("employer")
def browse():
    skill = request.args.get("skill", "").strip()
    role_wanted = request.args.get("role", "").strip()
    location = request.args.get("location", "").strip()
    experience = request.args.get("experience", "").strip()
    smart_query = request.args.get("smart", "").strip()
    page = request.args.get("page", 1, type=int)

    filters = {
        "skill": skill, "role": role_wanted,
        "location": location, "experience": experience, "smart": smart_query,
    }
    shortlisted_ids = {
        s.candidate_profile_id
        for s in Shortlist.query.filter_by(employer_id=current_user.id).all()
    }

    # Smart search: rank a pool of candidates against a plain-English
    # requirement using AI, instead of exact-match SQL filters.
    if smart_query:
        pool = (
            CandidateProfile.query.order_by(CandidateProfile.submitted_on.desc())
            .limit(SMART_SEARCH_MAX_CANDIDATES)
            .all()
        )
        ranked = rank_candidates(smart_query, pool)
        candidates = [c for c, _reason in ranked]
        reasons = {c.id: reason for c, reason in ranked if reason}

        return render_template(
            "employer/browse.html",
            pagination=None,
            candidates=candidates,
            filters=filters,
            experience_levels=EXPERIENCE_LEVELS,
            shortlisted_ids=shortlisted_ids,
            ai_reasons=reasons,
            smart_search_active=True,
        )

    query = CandidateProfile.query

    if skill:
        query = query.filter(CandidateProfile.skills.ilike(f"%{skill}%"))
    if role_wanted:
        query = query.filter(CandidateProfile.role_wanted.ilike(f"%{role_wanted}%"))
    if location:
        query = query.filter(CandidateProfile.location.ilike(f"%{location}%"))
    if experience:
        query = query.filter(CandidateProfile.experience_level == experience)

    query = query.order_by(CandidateProfile.submitted_on.desc())

    per_page = current_app.config["CANDIDATES_PER_PAGE"]
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        "employer/browse.html",
        pagination=pagination,
        candidates=pagination.items,
        filters=filters,
        experience_levels=EXPERIENCE_LEVELS,
        shortlisted_ids=shortlisted_ids,
    )


@employer_bp.route("/candidate/<int:profile_id>")
@login_required
@role_required("employer")
def candidate_detail(profile_id):
    profile = CandidateProfile.query.get_or_404(profile_id)

    # Log this view, but only once per employer per candidate (avoid
    # inflating the count every time the same employer refreshes the page).
    already_viewed = ProfileView.query.filter_by(
        employer_id=current_user.id, candidate_profile_id=profile.id
    ).first()
    if not already_viewed:
        db.session.add(ProfileView(employer_id=current_user.id, candidate_profile_id=profile.id))
        db.session.commit()

    is_shortlisted = Shortlist.query.filter_by(
        employer_id=current_user.id, candidate_profile_id=profile.id
    ).first() is not None

    return render_template(
        "employer/candidate_detail.html", candidate=profile, is_shortlisted=is_shortlisted
    )


@employer_bp.route("/shortlist/<int:profile_id>", methods=["POST"])
@login_required
@role_required("employer")
def shortlist(profile_id):
    profile = CandidateProfile.query.get_or_404(profile_id)

    existing = Shortlist.query.filter_by(
        employer_id=current_user.id, candidate_profile_id=profile.id
    ).first()
    if not existing:
        db.session.add(Shortlist(employer_id=current_user.id, candidate_profile_id=profile.id))
        db.session.commit()
        flash(f"{profile.full_name} added to your shortlist.", "success")

    return redirect(request.referrer or url_for("employer.browse"))


@employer_bp.route("/unshortlist/<int:profile_id>", methods=["POST"])
@login_required
@role_required("employer")
def unshortlist(profile_id):
    entry = Shortlist.query.filter_by(
        employer_id=current_user.id, candidate_profile_id=profile_id
    ).first()
    if entry:
        db.session.delete(entry)
        db.session.commit()
        flash("Removed from your shortlist.", "success")

    return redirect(request.referrer or url_for("employer.dashboard"))


@employer_bp.route("/dashboard")
@login_required
@role_required("employer")
def dashboard():
    shortlisted = (
        CandidateProfile.query.join(Shortlist)
        .filter(Shortlist.employer_id == current_user.id)
        .order_by(Shortlist.created_at.desc())
        .all()
    )
    return render_template("employer/dashboard.html", candidates=shortlisted)


@employer_bp.route("/cv/<int:profile_id>")
@login_required
def download_cv(profile_id):
    """Only an employer, or the candidate who owns the profile, can download the CV."""
    profile = CandidateProfile.query.get_or_404(profile_id)

    is_owner = current_user.is_candidate() and profile.user_id == current_user.id
    if not (current_user.is_employer() or is_owner):
        abort(403)

    if not profile.cv_filename:
        abort(404)

    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"], profile.cv_filename, as_attachment=True
    )
