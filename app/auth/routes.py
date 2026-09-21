"""
Authentication routes: signup, login, logout.
Login and signup are rate-limited so someone can't hammer the login form
trying to guess a password, or spam-create accounts.
"""
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from app.auth import auth_bp
from app.extensions import db, limiter
from app.forms import SignupForm, LoginForm
from app.models import User


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
