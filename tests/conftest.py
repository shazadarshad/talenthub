"""
Shared pytest fixtures.
Every test gets a fresh in-memory database via the 'testing' config,
so tests never touch the real talenthub.db file.
"""
import io
import pytest

from app import create_app
from app.extensions import db
from app.models import User, CandidateProfile


@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def candidate_user(app):
    """A plain candidate account with no profile yet."""
    user = User(email="candidate@example.com", role="candidate")
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def employer_user(app):
    """A plain employer account."""
    user = User(email="employer@example.com", role="employer")
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def candidate_with_profile(app, candidate_user):
    """A candidate account that already has a completed profile."""
    profile = CandidateProfile(
        user_id=candidate_user.id,
        full_name="Test Candidate",
        role_wanted="Python Developer",
        skills="Python, Flask, SQL",
        location="Colombo",
        experience_level="Junior",
        contact_email="candidate@example.com",
        cover_letter="I love building things.",
        cv_filename=None,
    )
    db.session.add(profile)
    db.session.commit()
    return candidate_user


def login(client, email, password):
    return client.post(
        "/auth/login", data={"email": email, "password": password}, follow_redirects=True
    )


def make_pdf_file(name="cv.pdf"):
    """Build an in-memory file that looks like a real (tiny) PDF."""
    return (io.BytesIO(b"%PDF-1.4 fake pdf content for tests"), name)


def make_fake_pdf_file(name="cv.pdf"):
    """A file with a .pdf name but non-PDF content, to test real validation."""
    return (io.BytesIO(b"this is just plain text, not a pdf"), name)
