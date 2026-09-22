"""
Candidate-only routes: create/edit your profile, and a dashboard showing
your stats (how many employers viewed or shortlisted you).
Every route here is locked to role="candidate" via @role_required.
"""
from datetime import datetime, timezone

from flask import render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.candidates import candidates_bp
from app.extensions import db
from app.forms import CandidateProfileForm
from app.models import CandidateProfile, ProfileView, Shortlist
from app.utils import role_required, is_valid_pdf, save_uploaded_cv, delete_cv_file, extract_pdf_text
from app.ai import summarize_cv


def _generate_ai_summary(profile):
    """Read the candidate's CV and store an AI-generated summary on the
    profile. Safe to call even if AI isn't configured or the CV has no
    readable text - in that case it simply leaves the AI fields empty.
    """
    cv_text = extract_pdf_text(profile.cv_filename)
    if not cv_text:
        return

    result = summarize_cv(cv_text, {
        "role_wanted": profile.role_wanted,
        "experience_level": profile.experience_level,
    })
    if result is None:
        return

    profile.ai_summary = result["summary"]
    profile.ai_skills = ", ".join(result["skills"])
    profile.ai_experience_years = result["experience_years"]
    profile.ai_generated_at = datetime.now(timezone.utc)


@candidates_bp.route("/profile/new", methods=["GET", "POST"])
@login_required
@role_required("candidate")
def new_profile():
    # A candidate only ever has one profile - if they already made one,
    # send them to edit it instead of creating a second.
    if current_user.candidate_profile:
        return redirect(url_for("candidates.edit_profile"))

    form = CandidateProfileForm()
    if form.validate_on_submit():
        cv_file = form.cv.data
        if not cv_file or not cv_file.filename:
            flash("Please upload your CV (PDF).", "error")
            return render_template("candidates/profile_form.html", form=form, is_new=True)

        if not is_valid_pdf(cv_file):
            flash("Your CV must be a real PDF file.", "error")
            return render_template("candidates/profile_form.html", form=form, is_new=True)

        cv_filename = save_uploaded_cv(cv_file)

        profile = CandidateProfile(
            user_id=current_user.id,
            full_name=form.full_name.data.strip(),
            role_wanted=form.role_wanted.data.strip(),
            skills=form.skills.data.strip(),
            location=form.location.data.strip(),
            experience_level=form.experience_level.data,
            contact_email=form.contact_email.data.strip(),
            portfolio_url=form.portfolio_url.data.strip() if form.portfolio_url.data else None,
            cover_letter=form.cover_letter.data.strip(),
            cv_filename=cv_filename,
        )
        db.session.add(profile)
        db.session.commit()

        # Generate the AI summary once, right after upload. If this fails
        # or AI isn't configured, the profile is still saved and usable.
        _generate_ai_summary(profile)
        db.session.commit()

        flash("Your profile is live! Employers can now find you.", "success")
        return redirect(url_for("candidates.dashboard"))

    return render_template("candidates/profile_form.html", form=form, is_new=True)


@candidates_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
@role_required("candidate")
def edit_profile():
    profile = current_user.candidate_profile
    if profile is None:
        return redirect(url_for("candidates.new_profile"))

    form = CandidateProfileForm(obj=profile)
    if form.validate_on_submit():
        # A new CV is optional when editing - only replace it if one was uploaded.
        cv_file = form.cv.data
        new_cv_uploaded = False
        if cv_file and cv_file.filename:
            if not is_valid_pdf(cv_file):
                flash("Your CV must be a real PDF file.", "error")
                return render_template("candidates/profile_form.html", form=form, is_new=False)
            delete_cv_file(profile.cv_filename)
            profile.cv_filename = save_uploaded_cv(cv_file)
            new_cv_uploaded = True

        profile.full_name = form.full_name.data.strip()
        profile.role_wanted = form.role_wanted.data.strip()
        profile.skills = form.skills.data.strip()
        profile.location = form.location.data.strip()
        profile.experience_level = form.experience_level.data
        profile.contact_email = form.contact_email.data.strip()
        profile.portfolio_url = form.portfolio_url.data.strip() if form.portfolio_url.data else None
        profile.cover_letter = form.cover_letter.data.strip()

        if new_cv_uploaded:
            # The CV changed, so the old AI summary no longer applies -
            # regenerate it from the new file.
            _generate_ai_summary(profile)

        db.session.commit()

        flash("Your profile has been updated.", "success")
        return redirect(url_for("candidates.dashboard"))

    if not form.is_submitted():
        # Pre-fill the form with the candidate's existing details.
        form.full_name.data = profile.full_name
        form.role_wanted.data = profile.role_wanted
        form.skills.data = profile.skills
        form.location.data = profile.location
        form.experience_level.data = profile.experience_level
        form.contact_email.data = profile.contact_email
        form.portfolio_url.data = profile.portfolio_url
        form.cover_letter.data = profile.cover_letter

    return render_template("candidates/profile_form.html", form=form, is_new=False, profile=profile)


def _profile_completeness_tips(profile):
    """Return a list of (done, label) tuples for simple profile checks,
    so candidates always have something actionable to see on their
    dashboard, even before any employer activity happens.
    """
    return [
        (bool(profile.cv_filename), "Upload your CV"),
        (len(profile.skill_list()) >= 3, "List at least 3 skills"),
        (len(profile.cover_letter) >= 100, "Write a cover letter (100+ characters)"),
        (bool(profile.ai_summary), "AI summary generated from your CV"),
    ]


@candidates_bp.route("/dashboard")
@login_required
@role_required("candidate")
def dashboard():
    profile = current_user.candidate_profile
    view_count = 0
    shortlist_count = 0
    completeness_tips = []
    completeness_percent = 0

    if profile:
        view_count = ProfileView.query.filter_by(candidate_profile_id=profile.id).count()
        shortlist_count = Shortlist.query.filter_by(candidate_profile_id=profile.id).count()
        completeness_tips = _profile_completeness_tips(profile)
        done_count = sum(1 for done, _ in completeness_tips if done)
        completeness_percent = round((done_count / len(completeness_tips)) * 100)

    return render_template(
        "candidates/dashboard.html",
        profile=profile,
        view_count=view_count,
        shortlist_count=shortlist_count,
        completeness_tips=completeness_tips,
        completeness_percent=completeness_percent,
    )


@candidates_bp.route("/profile/delete", methods=["POST"])
@login_required
@role_required("candidate")
def delete_profile():
    profile = current_user.candidate_profile
    if profile is None:
        abort(404)

    delete_cv_file(profile.cv_filename)
    db.session.delete(profile)
    db.session.commit()

    flash("Your profile has been removed.", "success")
    return redirect(url_for("candidates.dashboard"))
