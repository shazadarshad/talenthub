"""
App configuration.
Reads sensitive values (SECRET_KEY, DATABASE_URL) from environment variables
so nothing secret is ever hardcoded or committed to git.
"""
import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    """Shared settings for every environment."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # File uploads
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB max upload size
    ALLOWED_EXTENSIONS = {"pdf"}

    # Pagination
    CANDIDATES_PER_PAGE = 9

    # Session cookie security (safe defaults, tightened further in production)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Rate limiting storage (in-memory is fine for a small app / one instance)
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'talenthub.db')}"
    )
    SESSION_COOKIE_SECURE = False  # allow plain http on localhost


class ProductionConfig(Config):
    DEBUG = False
    # Render/Heroku-style Postgres URLs start with postgres://, SQLAlchemy needs postgresql://
    _db_url = os.environ.get("DATABASE_URL", "")
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url or f"sqlite:///{os.path.join(BASE_DIR, 'talenthub.db')}"
    SESSION_COOKIE_SECURE = True  # only send cookies over https in production


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False  # simplifies posting test forms
    SESSION_COOKIE_SECURE = False
    RATELIMIT_ENABLED = False  # don't let rate limits break fast test loops


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
