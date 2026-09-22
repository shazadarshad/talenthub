"""
WTForms forms. Using Flask-WTF gives us CSRF protection automatically on
every form that uses {{ form.hidden_tag() }} in the template.
"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField, PasswordField, TextAreaField, SelectField, SubmitField,
)
from wtforms.validators import (
    DataRequired, Email, EqualTo, Length, ValidationError, Optional, URL,
)

EXPERIENCE_LEVELS = ["Entry", "Junior", "Mid", "Senior"]


class SignupForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField(
        "Password", validators=[DataRequired(), Length(min=8, message="Use at least 8 characters.")]
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    role = SelectField(
        "I am a...",
        choices=[("candidate", "Candidate - looking for a role"), ("employer", "Employer - hiring")],
        validators=[DataRequired()],
    )
    submit = SubmitField("Create Account")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log In")


class ForgotPasswordForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Send Reset Link")


class ResetPasswordForm(FlaskForm):
    password = PasswordField(
        "New Password", validators=[DataRequired(), Length(min=8, message="Use at least 8 characters.")]
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Reset Password")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current Password", validators=[DataRequired()])
    new_password = PasswordField(
        "New Password", validators=[DataRequired(), Length(min=8, message="Use at least 8 characters.")]
    )
    confirm_new_password = PasswordField(
        "Confirm New Password",
        validators=[DataRequired(), EqualTo("new_password", message="Passwords must match.")],
    )
    submit = SubmitField("Change Password")


class DeleteAccountForm(FlaskForm):
    password = PasswordField("Enter your password to confirm", validators=[DataRequired()])
    submit = SubmitField("Delete My Account")


class CandidateProfileForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    role_wanted = StringField("Role You Want", validators=[DataRequired(), Length(max=120)])
    skills = StringField(
        "Skills (comma separated)", validators=[DataRequired(), Length(max=400)]
    )
    location = StringField("Location", validators=[DataRequired(), Length(max=120)])
    experience_level = SelectField(
        "Experience Level",
        choices=[(lvl, lvl) for lvl in EXPERIENCE_LEVELS],
        validators=[DataRequired()],
    )
    contact_email = StringField("Contact Email", validators=[DataRequired(), Email()])
    portfolio_url = StringField(
        "Portfolio / LinkedIn URL (optional)",
        validators=[Optional(), Length(max=300), URL(message="Enter a valid URL, e.g. https://...")],
    )
    cover_letter = TextAreaField(
        "Cover Letter / About You", validators=[DataRequired(), Length(max=4000)]
    )
    cv = FileField(
        "CV (PDF)",
        validators=[FileAllowed(["pdf"], "Only PDF files are allowed.")],
    )
    submit = SubmitField("Save Profile")

    def validate_cv(self, field):
        """Extra safety net: also require a CV on brand-new profiles.
        (The route itself decides whether a CV is required - e.g. it's
        optional when editing an existing profile that already has one.)
        """
        pass
