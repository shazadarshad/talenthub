"""Tests for candidate profile creation, editing, ownership, and CV uploads."""
from app.models import CandidateProfile
from tests.conftest import login, make_pdf_file, make_fake_pdf_file


def _profile_form_data(**overrides):
    data = {
        "full_name": "Jane Doe",
        "role_wanted": "Backend Developer",
        "skills": "Python, Django",
        "location": "Kandy",
        "experience_level": "Mid",
        "contact_email": "jane@example.com",
        "cover_letter": "I build reliable backend systems.",
    }
    data.update(overrides)
    return data


def test_create_profile_with_valid_pdf(client, candidate_user):
    login(client, "candidate@example.com", "password123")

    data = _profile_form_data()
    data["cv"] = make_pdf_file()

    resp = client.post(
        "/candidates/profile/new", data=data, content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"profile is live" in resp.data

    profile = CandidateProfile.query.filter_by(user_id=candidate_user.id).first()
    assert profile is not None
    assert profile.full_name == "Jane Doe"
    assert profile.cv_filename is not None


def test_create_profile_rejects_non_pdf_content(client, candidate_user):
    """A file named cv.pdf but containing plain text must be rejected."""
    login(client, "candidate@example.com", "password123")

    data = _profile_form_data()
    data["cv"] = make_fake_pdf_file()

    resp = client.post(
        "/candidates/profile/new", data=data, content_type="multipart/form-data",
    )
    assert b"must be a real PDF" in resp.data
    assert CandidateProfile.query.filter_by(user_id=candidate_user.id).first() is None


def test_create_profile_requires_cv(client, candidate_user):
    login(client, "candidate@example.com", "password123")
    data = _profile_form_data()  # no "cv" key at all

    resp = client.post(
        "/candidates/profile/new", data=data, content_type="multipart/form-data",
    )
    assert b"upload your CV" in resp.data


def test_employer_cannot_create_candidate_profile(client, employer_user):
    """role_required should block employers from candidate-only routes (403)."""
    login(client, "employer@example.com", "password123")

    data = _profile_form_data()
    data["cv"] = make_pdf_file()
    resp = client.post("/candidates/profile/new", data=data, content_type="multipart/form-data")
    assert resp.status_code == 403


def test_candidate_can_edit_own_profile(client, candidate_with_profile):
    login(client, "candidate@example.com", "password123")

    resp = client.post(
        "/candidates/profile/edit",
        data=_profile_form_data(full_name="Jane Updated"),
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"has been updated" in resp.data

    profile = CandidateProfile.query.filter_by(user_id=candidate_with_profile.id).first()
    assert profile.full_name == "Jane Updated"


def test_candidate_without_profile_redirected_to_new(client, candidate_user):
    login(client, "candidate@example.com", "password123")
    resp = client.get("/candidates/profile/edit", follow_redirects=True)
    # Should end up on the "create profile" page instead of erroring.
    assert b"Create Your Profile" in resp.data


def test_cv_download_requires_login(client, candidate_with_profile):
    # Not logged in at all - should redirect to login, not serve the file.
    from app.models import CandidateProfile as CP
    profile = CP.query.first()
    resp = client.get(f"/employer/cv/{profile.id}", follow_redirects=True)
    assert b"Log In" in resp.data or b"Please log in" in resp.data


def test_employer_can_download_cv(client, candidate_with_profile, employer_user):
    # First give the candidate a real CV file via edit.
    login(client, "candidate@example.com", "password123")
    client.post(
        "/candidates/profile/edit",
        data={**_profile_form_data(), "cv": make_pdf_file()},
        content_type="multipart/form-data",
    )
    client.get("/auth/logout")

    login(client, "employer@example.com", "password123")
    profile = CandidateProfile.query.filter_by(user_id=candidate_with_profile.id).first()
    resp = client.get(f"/employer/cv/{profile.id}")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "application/pdf"
