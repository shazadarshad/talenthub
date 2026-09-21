"""
Candidate-only routes: create/edit your profile, and a dashboard showing
your stats (how many employers viewed or shortlisted you).
Every route here is locked to role="candidate" via @role_required.
"""
from flask import render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.candidates import candidates_bp
from app.extensions import db
from app.forms import CandidateProfileForm
from app.models import CandidateProfile, ProfileView, Shortlist
from app.utils import role_required, is_valid_pdf, save_uploaded_cv, delete_cv_file


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
            cover_letter=form.cover_letter.data.strip(),
            cv_filename=cv_filename,
        )
        db.session.add(profile)
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
        if cv_file and cv_file.filename:
            if not is_valid_pdf(cv_file):
                flash("Your CV must be a real PDF file.", "error")
                return render_template("candidates/profile_form.html", form=form, is_new=False)
            delete_cv_file(profile.cv_filename)
            profile.cv_filename = save_uploaded_cv(cv_file)

        profile.full_name = form.full_name.data.strip()
        profile.role_wanted = form.role_wanted.data.strip()
        profile.skills = form.skills.data.strip()
        profile.location = form.location.data.strip()
        profile.experience_level = form.experience_level.data
        profile.contact_email = form.contact_email.data.strip()
        profile.cover_letter = form.cover_letter.data.strip()
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
        form.cover_letter.data = profile.cover_letter

    return render_template("candidates/profile_form.html", form=form, is_new=False, profile=profile)


@candidates_bp.route("/dashboard")
@login_required
@role_required("candidate")
def dashboard():
    profile = current_user.candidate_profile
    view_count = 0
    shortlist_count = 0
    if profile:
        view_count = ProfileView.query.filter_by(candidate_profile_id=profile.id).count()
        shortlist_count = Shortlist.query.filter_by(candidate_profile_id=profile.id).count()

    return render_template(
        "candidates/dashboard.html",
        profile=profile,
        view_count=view_count,
        shortlist_count=shortlist_count,
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
