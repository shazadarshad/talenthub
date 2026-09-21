"""Tests for employer browsing, filtering, shortlisting, and permission boundaries."""
from app.extensions import db
from app.models import User, CandidateProfile, ProfileView, Shortlist
from tests.conftest import login


def _make_candidate(email, full_name, role_wanted, skills, location, level):
    user = User(email=email, role="candidate")
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    profile = CandidateProfile(
        user_id=user.id,
        full_name=full_name,
        role_wanted=role_wanted,
        skills=skills,
        location=location,
        experience_level=level,
        contact_email=email,
        cover_letter="Cover letter text.",
    )
    db.session.add(profile)
    db.session.commit()
    return profile


def test_browse_requires_employer_role(client, candidate_user):
    login(client, "candidate@example.com", "password123")
    resp = client.get("/employer/browse")
    assert resp.status_code == 403


def test_browse_lists_candidates(client, employer_user, app):
    _make_candidate("a@example.com", "Alice Silva", "Frontend Dev", "React, CSS", "Colombo", "Junior")
    _make_candidate("b@example.com", "Bob Perera", "Backend Dev", "Python, SQL", "Kandy", "Senior")

    login(client, "employer@example.com", "password123")
    resp = client.get("/employer/browse")
    assert b"Alice Silva" in resp.data
    assert b"Bob Perera" in resp.data


def test_filter_by_skill(client, employer_user, app):
    _make_candidate("a@example.com", "Alice Silva", "Frontend Dev", "React, CSS", "Colombo", "Junior")
    _make_candidate("b@example.com", "Bob Perera", "Backend Dev", "Python, SQL", "Kandy", "Senior")

    login(client, "employer@example.com", "password123")
    resp = client.get("/employer/browse?skill=Python")
    assert b"Bob Perera" in resp.data
    assert b"Alice Silva" not in resp.data


def test_filter_by_experience_level(client, employer_user, app):
    _make_candidate("a@example.com", "Alice Silva", "Frontend Dev", "React", "Colombo", "Junior")
    _make_candidate("b@example.com", "Bob Perera", "Backend Dev", "Python", "Kandy", "Senior")

    login(client, "employer@example.com", "password123")
    resp = client.get("/employer/browse?experience=Senior")
    assert b"Bob Perera" in resp.data
    assert b"Alice Silva" not in resp.data


def test_pagination_limits_results_per_page(client, employer_user, app):
    # CANDIDATES_PER_PAGE is 9 in config; create 11 to force a second page.
    for i in range(11):
        _make_candidate(f"c{i}@example.com", f"Candidate {i}", "Developer", "Python", "Remote", "Entry")

    login(client, "employer@example.com", "password123")
    resp = client.get("/employer/browse")
    assert b"Page 1 of 2" in resp.data

    resp_page2 = client.get("/employer/browse?page=2")
    assert b"Page 2 of 2" in resp_page2.data


def test_viewing_profile_logs_a_view(client, employer_user, app):
    profile = _make_candidate("a@example.com", "Alice Silva", "Dev", "Python", "Colombo", "Junior")

    login(client, "employer@example.com", "password123")
    client.get(f"/employer/candidate/{profile.id}")

    views = ProfileView.query.filter_by(candidate_profile_id=profile.id).count()
    assert views == 1

    # Viewing again as the SAME employer should not double-count.
    client.get(f"/employer/candidate/{profile.id}")
    views_again = ProfileView.query.filter_by(candidate_profile_id=profile.id).count()
    assert views_again == 1


def test_shortlist_and_unshortlist(client, employer_user, app):
    profile = _make_candidate("a@example.com", "Alice Silva", "Dev", "Python", "Colombo", "Junior")

    login(client, "employer@example.com", "password123")
    client.post(f"/employer/shortlist/{profile.id}")
    assert Shortlist.query.filter_by(candidate_profile_id=profile.id).count() == 1

    resp = client.get("/employer/dashboard")
    assert b"Alice Silva" in resp.data

    client.post(f"/employer/unshortlist/{profile.id}")
    assert Shortlist.query.filter_by(candidate_profile_id=profile.id).count() == 0


def test_candidate_cannot_shortlist(client, candidate_user, app):
    profile = _make_candidate("a@example.com", "Alice Silva", "Dev", "Python", "Colombo", "Junior")

    login(client, "candidate@example.com", "password123")
    resp = client.post(f"/employer/shortlist/{profile.id}")
    assert resp.status_code == 403


def test_employer_dashboard_requires_login(client):
    resp = client.get("/employer/dashboard", follow_redirects=True)
    assert b"Log In" in resp.data or b"Please log in" in resp.data
