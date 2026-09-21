"""Tests for signup, login, and logout."""
from app.models import User
from tests.conftest import login


def test_signup_candidate(client, app):
    resp = client.post(
        "/auth/signup",
        data={
            "email": "newcandidate@example.com",
            "password": "password123",
            "confirm_password": "password123",
            "role": "candidate",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    user = User.query.filter_by(email="newcandidate@example.com").first()
    assert user is not None
    assert user.role == "candidate"
    assert user.password_hash != "password123"  # must be hashed, not plain


def test_signup_employer(client, app):
    resp = client.post(
        "/auth/signup",
        data={
            "email": "newemployer@example.com",
            "password": "password123",
            "confirm_password": "password123",
            "role": "employer",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    user = User.query.filter_by(email="newemployer@example.com").first()
    assert user is not None
    assert user.role == "employer"


def test_signup_duplicate_email_rejected(client, candidate_user):
    resp = client.post(
        "/auth/signup",
        data={
            "email": "candidate@example.com",  # already taken by the fixture
            "password": "password123",
            "confirm_password": "password123",
            "role": "candidate",
        },
        follow_redirects=True,
    )
    assert b"already exists" in resp.data
    # still only one user with that email
    assert User.query.filter_by(email="candidate@example.com").count() == 1


def test_signup_password_mismatch_rejected(client):
    resp = client.post(
        "/auth/signup",
        data={
            "email": "mismatch@example.com",
            "password": "password123",
            "confirm_password": "different123",
            "role": "candidate",
        },
    )
    assert User.query.filter_by(email="mismatch@example.com").first() is None
    assert resp.status_code == 200  # re-renders the form with an error


def test_login_success(client, candidate_user):
    resp = login(client, "candidate@example.com", "password123")
    assert resp.status_code == 200
    assert b"Welcome back" in resp.data


def test_login_wrong_password_rejected(client, candidate_user):
    resp = login(client, "candidate@example.com", "wrongpassword")
    assert b"Incorrect email or password" in resp.data


def test_login_unknown_email_rejected(client):
    resp = login(client, "nobody@example.com", "whatever123")
    assert b"Incorrect email or password" in resp.data


def test_logout(client, candidate_user):
    login(client, "candidate@example.com", "password123")
    resp = client.get("/auth/logout", follow_redirects=True)
    assert b"logged out" in resp.data

    # After logging out, a protected page should redirect to login.
    resp = client.get("/candidates/dashboard", follow_redirects=True)
    assert b"Please log in" in resp.data or b"Log In" in resp.data
