"""
Small helper functions shared across the app:
- role_required: a decorator that locks a route to one account type
- is_valid_pdf: checks the file is *actually* a PDF, not just named .pdf
- save_uploaded_cv: safely saves an uploaded CV with a unique filename
"""
import os
import uuid
from functools import wraps

from flask import abort, current_app
from flask_login import current_user
from werkzeug.utils import secure_filename

PDF_MAGIC_BYTES = b"%PDF"


def role_required(role):
    """Only let users with the given role (e.g. 'candidate' or 'employer') in.
    Anyone else gets a 403 Forbidden - this stops candidates from reaching
    employer-only pages and vice versa.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role != role:
                abort(403)
            return view_func(*args, **kwargs)
        return wrapped
    return decorator


def is_valid_pdf(file_storage):
    """Check the file's actual content starts with the PDF magic bytes.
    A file can be renamed to "resume.pdf" without being a real PDF, so we
    peek at the first few bytes instead of trusting the file extension.
    """
    if file_storage is None or not file_storage.filename:
        return False

    file_storage.stream.seek(0)
    header = file_storage.stream.read(4)
    file_storage.stream.seek(0)  # reset so it can still be saved afterwards
    return header == PDF_MAGIC_BYTES


def save_uploaded_cv(file_storage):
    """Save an uploaded CV to the uploads folder with a unique, safe filename.
    Returns the filename that was stored on disk.
    """
    safe_name = secure_filename(file_storage.filename)
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)
    file_storage.save(os.path.join(upload_folder, stored_name))
    return stored_name


def delete_cv_file(filename):
    """Remove a stored CV file from disk, if it exists."""
    if not filename:
        return
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    if os.path.exists(path):
        os.remove(path)


def extract_pdf_text(filename, max_chars=12000):
    """Read the text content out of a stored CV PDF.

    Returns an empty string if the file is missing or can't be read (e.g. a
    scanned image PDF with no real text layer) - callers should treat that
    as "no text available" rather than an error.
    """
    if not filename:
        return ""

    path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    if not os.path.exists(path):
        return ""

    try:
        from pypdf import PdfReader

        reader = PdfReader(path)
        pages_text = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages_text).strip()
        return text[:max_chars]
    except Exception:
        # A corrupted or unusual PDF shouldn't crash the app - just treat
        # it as if there was no readable text.
        return ""


def generate_reset_token(user_email):
    """Create a signed, time-limited token for a password reset link.

    Uses the app's SECRET_KEY to sign it, so it can't be forged, and it's
    self-contained (no database table needed to track pending resets) -
    verifying it later also checks that it hasn't expired.
    """
    from itsdangerous import URLSafeTimedSerializer

    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return serializer.dumps(user_email, salt="password-reset")


def verify_reset_token(token):
    """Check a password reset token and return the email it was issued
    for, or None if the token is invalid, tampered with, or expired.
    """
    from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    max_age = current_app.config.get("RESET_TOKEN_MAX_AGE", 3600)

    try:
        return serializer.loads(token, salt="password-reset", max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None


def send_password_reset_email(to_email, reset_url):
    """Email a password reset link to the user.

    If no mail server is configured (MAIL_USERNAME is blank), this just
    logs the link instead of sending an email - handy for local dev, and
    it means the app never breaks just because email isn't set up yet.
    """
    if not current_app.config.get("MAIL_USERNAME"):
        current_app.logger.info(f"[No mail configured] Password reset link for {to_email}: {reset_url}")
        return

    from flask_mail import Message
    from app.extensions import mail

    message = Message(
        subject="Reset your TalentHub password",
        recipients=[to_email],
        body=(
            f"Hi,\n\n"
            f"We received a request to reset your TalentHub password. "
            f"Click the link below to choose a new one:\n\n"
            f"{reset_url}\n\n"
            f"This link expires in 1 hour. If you didn't request this, "
            f"you can safely ignore this email.\n\n"
            f"- TalentHub"
        ),
    )

    try:
        mail.send(message)
    except Exception:
        # Don't let an email provider outage break the reset flow for the
        # user - log it so we can investigate, but still let them proceed.
        current_app.logger.exception(f"Failed to send password reset email to {to_email}")
