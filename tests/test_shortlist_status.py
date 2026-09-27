"""Tests for the shortlist hiring-pipeline status feature."""
from app.extensions import db
from app.models import User, CandidateProfile, Shortlist
from tests.conftest import login


def _make_candidate(email, full_name):
    user = User(email=email, role="candidate")
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    profile = CandidateProfile(
        user_id=user.id,
        full_name=full_name,
        role_wanted="Developer",
        skills="Python, SQL",
        location="Colombo",
        experience_level="Junior",
        contact_email=email,
        cover_letter="Cover letter text.",
    )
    db.session.add(profile)
    db.session.commit()
    return profile


def test_new_shortlist_defaults_to_new_status(client, employer_user, app):
    profile = _make_candidate("a@example.com", "Alice Silva")

    login(client, "employer@example.com", "password123")
    client.post(f"/employer/shortlist/{profile.id}")

    entry = Shortlist.query.filter_by(candidate_profile_id=profile.id).first()
    assert entry.status == "New"


def test_employer_can_update_status(client, employer_user, app):
    profile = _make_candidate("a@example.com", "Alice Silva")

    login(client, "employer@example.com", "password123")
    client.post(f"/employer/shortlist/{profile.id}")
    client.post(f"/employer/shortlist/{profile.id}/status", data={"status": "Interviewing"})

    entry = Shortlist.query.filter_by(candidate_profile_id=profile.id).first()
    assert entry.status == "Interviewing"


def test_invalid_status_is_rejected(client, employer_user, app):
    profile = _make_candidate("a@example.com", "Alice Silva")

    login(client, "employer@example.com", "password123")
    client.post(f"/employer/shortlist/{profile.id}")
    client.post(f"/employer/shortlist/{profile.id}/status", data={"status": "Bogus"})

    entry = Shortlist.query.filter_by(candidate_profile_id=profile.id).first()
    assert entry.status == "New"  # unchanged


def test_status_update_requires_existing_shortlist(client, employer_user, app):
    profile = _make_candidate("a@example.com", "Alice Silva")

    login(client, "employer@example.com", "password123")
    # Not shortlisted yet -> 404
    resp = client.post(f"/employer/shortlist/{profile.id}/status", data={"status": "Hired"})
    assert resp.status_code == 404


def test_candidate_cannot_update_status(client, candidate_user, app):
    profile = _make_candidate("other@example.com", "Alice Silva")

    login(client, "candidate@example.com", "password123")
    resp = client.post(f"/employer/shortlist/{profile.id}/status", data={"status": "Hired"})
    assert resp.status_code == 403


def test_dashboard_filters_by_status(client, employer_user, app):
    alice = _make_candidate("a@example.com", "Alice Silva")
    bob = _make_candidate("b@example.com", "Bob Perera")

    login(client, "employer@example.com", "password123")
    client.post(f"/employer/shortlist/{alice.id}")
    client.post(f"/employer/shortlist/{bob.id}")
    client.post(f"/employer/shortlist/{alice.id}/status", data={"status": "Hired"})

    resp = client.get("/employer/dashboard?status=Hired")
    # Check for the candidate's profile link, not their name — names also
    # appear in flash messages ("X added to your shortlist"), which would
    # make a plain name check unreliable.
    assert f"/employer/candidate/{alice.id}".encode() in resp.data
    assert f"/employer/candidate/{bob.id}".encode() not in resp.data


def test_status_included_in_csv_export(client, employer_user, app):
    profile = _make_candidate("a@example.com", "Alice Silva")

    login(client, "employer@example.com", "password123")
    client.post(f"/employer/shortlist/{profile.id}")
    client.post(f"/employer/shortlist/{profile.id}/status", data={"status": "Contacted"})

    resp = client.get("/employer/shortlist/export.csv")
    assert b"Status" in resp.data
    assert b"Contacted" in resp.data
