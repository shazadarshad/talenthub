"""
Database models for TalentHub.

- User: a login account, either role="candidate" or role="employer"
- CandidateProfile: the profile a candidate fills in (one per candidate user)
- Shortlist: links an employer to a candidate profile they've saved
- ProfileView: one row per employer who has opened a candidate's profile
"""
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


def utcnow():
    """Small helper so every timestamp default uses the same clock."""
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # "candidate" or "employer"
    created_at = db.Column(db.DateTime, default=utcnow)

    # A candidate user has at most one profile.
    candidate_profile = db.relationship(
        "CandidateProfile", backref="user", uselist=False, cascade="all, delete-orphan"
    )

    def set_password(self, raw_password):
        """Hash and store a password - we never keep the plain text."""
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        """Check a plain password against the stored hash."""
        return check_password_hash(self.password_hash, raw_password)

    def is_candidate(self):
        return self.role == "candidate"

    def is_employer(self):
        return self.role == "employer"

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class CandidateProfile(db.Model):
    __tablename__ = "candidate_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)

    full_name = db.Column(db.String(120), nullable=False)
    role_wanted = db.Column(db.String(120), nullable=False)
    skills = db.Column(db.String(400), nullable=False)  # comma separated
    location = db.Column(db.String(120), nullable=False)
    experience_level = db.Column(db.String(20), nullable=False)  # Entry/Junior/Mid/Senior
    contact_email = db.Column(db.String(255), nullable=False)
    cover_letter = db.Column(db.Text, nullable=False)
    cv_filename = db.Column(db.String(255), nullable=True)
    submitted_on = db.Column(db.DateTime, default=utcnow)

    # AI-generated fields, produced once from the uploaded CV's text.
    # These are supplementary - the app works fine if they're empty
    # (e.g. AI is not configured, or the CV couldn't be read).
    ai_summary = db.Column(db.Text, nullable=True)
    ai_skills = db.Column(db.String(500), nullable=True)  # comma separated, AI-extracted
    ai_experience_years = db.Column(db.Integer, nullable=True)
    ai_generated_at = db.Column(db.DateTime, nullable=True)

    shortlisted_by = db.relationship(
        "Shortlist", backref="candidate_profile", cascade="all, delete-orphan"
    )
    views = db.relationship(
        "ProfileView", backref="candidate_profile", cascade="all, delete-orphan"
    )

    def skill_list(self):
        """Split the comma-separated skills string into a clean list."""
        return [s.strip() for s in self.skills.split(",") if s.strip()]

    def ai_skill_list(self):
        """Split the AI-extracted skills string into a clean list."""
        if not self.ai_skills:
            return []
        return [s.strip() for s in self.ai_skills.split(",") if s.strip()]

    def __repr__(self):
        return f"<CandidateProfile {self.full_name}>"


class Shortlist(db.Model):
    __tablename__ = "shortlists"

    id = db.Column(db.Integer, primary_key=True)
    employer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    candidate_profile_id = db.Column(
        db.Integer, db.ForeignKey("candidate_profiles.id"), nullable=False
    )
    created_at = db.Column(db.DateTime, default=utcnow)

    employer = db.relationship("User", foreign_keys=[employer_id])

    __table_args__ = (
        db.UniqueConstraint("employer_id", "candidate_profile_id", name="uq_employer_candidate"),
    )


class ProfileView(db.Model):
    __tablename__ = "profile_views"

    id = db.Column(db.Integer, primary_key=True)
    employer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    candidate_profile_id = db.Column(
        db.Integer, db.ForeignKey("candidate_profiles.id"), nullable=False
    )
    viewed_at = db.Column(db.DateTime, default=utcnow)

    employer = db.relationship("User", foreign_keys=[employer_id])
