"""
Authentication routes: signup, login, logout, and password reset.
Login, signup, and forgot-password are rate-limited so someone can't
hammer these forms trying to guess a password or spam requests.
"""
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from app.auth import auth_bp
from app.extensions import db, limiter
from app.forms import SignupForm, LoginForm, ForgotPasswordForm, ResetPasswordForm, ChangePasswordForm, DeleteAccountForm
from app.models import User
from app.utils import generate_reset_token, verify_reset_token, send_password_reset_email


@auth_bp.route("/signup", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("main.landing"))

    form = SignupForm()
    if form.validate_on_submit():
        existing = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if existing:
            flash("An account with that email already exists. Try logging in instead.", "error")
            return render_template("auth/signup.html", form=form)

        user = User(email=form.email.data.lower().strip(), role=form.role.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash("Welcome to TalentHub! Your account has been created.", "success")

        if user.is_candidate():
            return redirect(url_for("candidates.new_profile"))
        return redirect(url_for("employer.browse"))

    return render_template("auth/signup.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.landing"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()

        if user is None or not user.check_password(form.password.data):
            flash("Incorrect email or password.", "error")
            return render_template("auth/login.html", form=form)

        login_user(user, remember=True)
        flash(f"Welcome back, {user.email}!", "success")

        next_page = request.args.get("next")
        if next_page:
            return redirect(next_page)
        if user.is_candidate():
            return redirect(url_for("candidates.dashboard"))
        return redirect(url_for("employer.browse"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You've been logged out.", "success")
    return redirect(url_for("main.landing"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("main.landing"))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        user = User.query.filter_by(email=email).first()

        # Always show the same message whether or not the account exists -
        # this avoids letting someone use this form to check which emails
        # are registered on the site.
        if user:
            token = generate_reset_token(user.email)
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            send_password_reset_email(user.email, reset_url)

        flash(
            "If an account with that email exists, we've sent a password reset link.",
            "success",
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for("main.landing"))

    email = verify_reset_token(token)
    if email is None:
        flash("That reset link is invalid or has expired. Please request a new one.", "error")
        return redirect(url_for("auth.forgot_password"))

    user = User.query.filter_by(email=email).first()
    if user is None:
        flash("That reset link is invalid or has expired. Please request a new one.", "error")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Your password has been reset. You can log in now.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form)


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Your current password is incorrect.", "error")
            return render_template("auth/change_password.html", form=form)

        current_user.set_password(form.new_password.data)
        db.session.commit()
        flash("Your password has been changed.", "success")
        if current_user.is_candidate():
            return redirect(url_for("candidates.dashboard"))
        return redirect(url_for("employer.dashboard"))

    return render_template("auth/change_password.html", form=form)


@auth_bp.route("/delete-account", methods=["GET", "POST"])
@login_required
def delete_account():
    form = DeleteAccountForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.password.data):
            flash("Incorrect password.", "error")
            return render_template("auth/delete_account.html", form=form)

        user = db.session.get(User, current_user.id)
        if user.is_candidate() and user.candidate_profile and user.candidate_profile.cv_filename:
            from app.utils import delete_cv_file
            delete_cv_file(user.candidate_profile.cv_filename)

        from app.models import Shortlist, ProfileView, Conversation, Message

        # Clean up everything that references this user, since there's no
        # database-level cascade on these foreign keys - deleting the user
        # directly would otherwise fail with a foreign key error.
        if user.is_employer():
            Shortlist.query.filter_by(employer_id=user.id).delete()
            ProfileView.query.filter_by(employer_id=user.id).delete()
        conversation_ids = [
            c.id for c in Conversation.query.filter(
                (Conversation.employer_id == user.id) | (Conversation.candidate_id == user.id)
            ).all()
        ]
        if conversation_ids:
            Message.query.filter(Message.conversation_id.in_(conversation_ids)).delete(synchronize_session=False)
            Conversation.query.filter(Conversation.id.in_(conversation_ids)).delete(synchronize_session=False)

        logout_user()
        db.session.delete(user)
        db.session.commit()
        flash("Your account has been permanently deleted.", "success")
        return redirect(url_for("main.landing"))

    return render_template("auth/delete_account.html", form=form)
