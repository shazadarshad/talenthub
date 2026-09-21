"""
Regression test for CSRF tokens on plain <form> actions (shortlist,
unshortlist, delete profile). These don't use Flask-WTF's form objects,
so it's easy to forget the hidden csrf_token input - this test catches
that by running with CSRF protection actually turned ON (unlike the
rest of the suite, which disables it for convenience).
"""
import io
import pytest
from app import create_app
from app.extensions import db
from app.models import User, CandidateProfile


@pytest.fixture()
def csrf_app():
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = True  # the whole point of this test
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def csrf_client(csrf_app):
    return csrf_app.test_client()


def _extract_csrf(html):
    import re
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    return match.group(1) if match else None


def test_signup_and_login_forms_carry_csrf_token(csrf_client):
    resp = csrf_client.get("/auth/signup")
    assert _extract_csrf(resp.text) is not None

    resp = csrf_client.get("/auth/login")
    assert _extract_csrf(resp.text) is not None


def test_shortlist_form_has_csrf_and_works(csrf_app, csrf_client):
    with csrf_app.app_context():
        candidate = User(email="c@example.com", role="candidate")
        candidate.set_password("password123")
        employer = User(email="e@example.com", role="employer")
        employer.set_password("password123")
        db.session.add_all([candidate, employer])
        db.session.commit()

        profile = CandidateProfile(
            user_id=candidate.id, full_name="Test Person", role_wanted="Dev",
            skills="Python", location="Remote", experience_level="Junior",
            contact_email="c@example.com", cover_letter="Hi there.",
        )
        db.session.add(profile)
        db.session.commit()
        profile_id = profile.id

    # Log the employer in (grab CSRF from the login page first).
    login_page = csrf_client.get("/auth/login")
    token = _extract_csrf(login_page.text)
    csrf_client.post(
        "/auth/login",
        data={"csrf_token": token, "email": "e@example.com", "password": "password123"},
    )

    # The browse page's shortlist form must include a real CSRF token.
    browse_page = csrf_client.get("/employer/browse")
    browse_token = _extract_csrf(browse_page.text)
    assert browse_token is not None, "Shortlist form is missing a CSRF token"

    resp = csrf_client.post(
        f"/employer/shortlist/{profile_id}",
        data={"csrf_token": browse_token},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Bad Request" not in resp.data
    assert b"CSRF" not in resp.data


def test_delete_profile_form_has_csrf_and_works(csrf_app, csrf_client):
    with csrf_app.app_context():
        candidate = User(email="c2@example.com", role="candidate")
        candidate.set_password("password123")
        db.session.add(candidate)
        db.session.commit()

        profile = CandidateProfile(
            user_id=candidate.id, full_name="Delete Me", role_wanted="Dev",
            skills="Python", location="Remote", experience_level="Junior",
            contact_email="c2@example.com", cover_letter="Hi there.",
        )
        db.session.add(profile)
        db.session.commit()

    login_page = csrf_client.get("/auth/login")
    token = _extract_csrf(login_page.text)
    csrf_client.post(
        "/auth/login",
        data={"csrf_token": token, "email": "c2@example.com", "password": "password123"},
    )

    dash = csrf_client.get("/candidates/dashboard")
    dash_token = _extract_csrf(dash.text)
    assert dash_token is not None, "Delete profile form is missing a CSRF token"

    resp = csrf_client.post(
        "/candidates/profile/delete",
        data={"csrf_token": dash_token},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Bad Request" not in resp.data
