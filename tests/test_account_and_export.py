"""Tests for: change password, account deletion, portfolio URL field,
and shortlist CSV export.
"""
import io
from app.extensions import db
from app.models import User, CandidateProfile, Shortlist, Conversation
from tests.conftest import login, make_pdf_file


class TestChangePassword:
    def test_change_password_success(self, client, candidate_user):
        login(client, "candidate@example.com", "password123")
        resp = client.post(
            "/auth/change-password",
            data={"current_password": "password123", "new_password": "NewPass123", "confirm_new_password": "NewPass123"},
            follow_redirects=True,
        )
        assert b"password has been changed" in resp.data

        client.get("/auth/logout")
        old = login(client, "candidate@example.com", "password123")
        assert b"Incorrect email or password" in old.data
        new = login(client, "candidate@example.com", "NewPass123")
        assert b"Welcome back" in new.data

    def test_change_password_wrong_current(self, client, candidate_user):
        login(client, "candidate@example.com", "password123")
        resp = client.post(
            "/auth/change-password",
            data={"current_password": "wrongpass", "new_password": "NewPass123", "confirm_new_password": "NewPass123"},
            follow_redirects=True,
        )
        assert b"current password is incorrect" in resp.data
        user = User.query.filter_by(email="candidate@example.com").first()
        assert user.check_password("password123")

    def test_change_password_requires_login(self, client):
        resp = client.get("/auth/change-password", follow_redirects=True)
        assert b"Log In" in resp.data or b"Please log in" in resp.data


class TestDeleteAccount:
    def test_candidate_can_delete_own_account(self, client, candidate_with_profile):
        login(client, "candidate@example.com", "password123")
        resp = client.post(
            "/auth/delete-account", data={"password": "password123"}, follow_redirects=True,
        )
        assert b"account has been permanently deleted" in resp.data
        assert User.query.filter_by(email="candidate@example.com").first() is None
        assert CandidateProfile.query.filter_by(contact_email="candidate@example.com").first() is None

    def test_delete_account_wrong_password_rejected(self, client, candidate_user):
        login(client, "candidate@example.com", "password123")
        resp = client.post("/auth/delete-account", data={"password": "wrongpass"}, follow_redirects=True)
        assert b"Incorrect password" in resp.data
        assert User.query.filter_by(email="candidate@example.com").first() is not None

    def test_employer_delete_cleans_up_shortlist_and_conversations(self, client, employer_user, app):
        candidate = User(email="del1@example.com", role="candidate")
        candidate.set_password("password123")
        db.session.add(candidate)
        db.session.commit()
        profile = CandidateProfile(
            user_id=candidate.id, full_name="Del Test", role_wanted="Dev", skills="Python",
            location="Colombo", experience_level="Junior", contact_email="del1@example.com",
            cover_letter="Hi.",
        )
        db.session.add(profile)
        db.session.commit()

        login(client, "employer@example.com", "password123")
        client.post(f"/employer/shortlist/{profile.id}")
        client.post(f"/messages/start/{profile.id}", data={"body": "Hello"})

        resp = client.post("/auth/delete-account", data={"password": "password123"}, follow_redirects=True)
        assert b"permanently deleted" in resp.data
        assert Shortlist.query.filter_by(candidate_profile_id=profile.id).count() == 0
        assert Conversation.query.filter_by(candidate_profile_id=profile.id).count() == 0


class TestPortfolioUrl:
    def test_profile_creation_with_portfolio_url(self, client, candidate_user):
        login(client, "candidate@example.com", "password123")
        data = {
            "full_name": "Jane Doe", "role_wanted": "Dev", "skills": "Python",
            "location": "Colombo", "experience_level": "Junior",
            "contact_email": "candidate@example.com", "cover_letter": "Hello there.",
            "portfolio_url": "https://linkedin.com/in/janedoe",
            "cv": make_pdf_file(),
        }
        client.post("/candidates/profile/new", data=data, content_type="multipart/form-data")
        profile = CandidateProfile.query.filter_by(user_id=candidate_user.id).first()
        assert profile.portfolio_url == "https://linkedin.com/in/janedoe"

    def test_profile_creation_without_portfolio_url_is_optional(self, client, candidate_user):
        login(client, "candidate@example.com", "password123")
        data = {
            "full_name": "Jane Doe", "role_wanted": "Dev", "skills": "Python",
            "location": "Colombo", "experience_level": "Junior",
            "contact_email": "candidate@example.com", "cover_letter": "Hello there.",
            "cv": make_pdf_file(),
        }
        resp = client.post("/candidates/profile/new", data=data, content_type="multipart/form-data", follow_redirects=True)
        assert resp.status_code == 200
        profile = CandidateProfile.query.filter_by(user_id=candidate_user.id).first()
        assert profile is not None
        assert profile.portfolio_url is None

    def test_invalid_portfolio_url_rejected(self, client, candidate_user):
        login(client, "candidate@example.com", "password123")
        data = {
            "full_name": "Jane Doe", "role_wanted": "Dev", "skills": "Python",
            "location": "Colombo", "experience_level": "Junior",
            "contact_email": "candidate@example.com", "cover_letter": "Hello there.",
            "portfolio_url": "not-a-valid-url",
            "cv": make_pdf_file(),
        }
        client.post("/candidates/profile/new", data=data, content_type="multipart/form-data")
        assert CandidateProfile.query.filter_by(user_id=candidate_user.id).first() is None

    def test_portfolio_url_shown_on_employer_view(self, client, employer_user, app):
        candidate = User(email="port1@example.com", role="candidate")
        candidate.set_password("password123")
        db.session.add(candidate)
        db.session.commit()
        profile = CandidateProfile(
            user_id=candidate.id, full_name="Port Test", role_wanted="Dev", skills="Python",
            location="Colombo", experience_level="Junior", contact_email="port1@example.com",
            cover_letter="Hi.", portfolio_url="https://myportfolio.dev",
        )
        db.session.add(profile)
        db.session.commit()

        login(client, "employer@example.com", "password123")
        resp = client.get(f"/employer/candidate/{profile.id}")
        assert b"https://myportfolio.dev" in resp.data


class TestShortlistCsvExport:
    def test_export_returns_csv_with_shortlisted_candidate(self, client, employer_user, app):
        candidate = User(email="csv1@example.com", role="candidate")
        candidate.set_password("password123")
        db.session.add(candidate)
        db.session.commit()
        profile = CandidateProfile(
            user_id=candidate.id, full_name="CSV Test Person", role_wanted="Dev", skills="Python",
            location="Colombo", experience_level="Junior", contact_email="csv1@example.com",
            cover_letter="Hi.",
        )
        db.session.add(profile)
        db.session.commit()

        login(client, "employer@example.com", "password123")
        client.post(f"/employer/shortlist/{profile.id}")

        resp = client.get("/employer/shortlist/export.csv")
        assert resp.status_code == 200
        assert resp.headers["Content-Type"].startswith("text/csv")
        assert "attachment" in resp.headers["Content-Disposition"]
        assert b"CSV Test Person" in resp.data

    def test_export_requires_employer_role(self, client, candidate_user):
        login(client, "candidate@example.com", "password123")
        resp = client.get("/employer/shortlist/export.csv")
        assert resp.status_code == 403

    def test_export_only_includes_own_shortlist(self, client, app):
        candidate = User(email="csv2@example.com", role="candidate")
        candidate.set_password("password123")
        emp1 = User(email="csvemp1@example.com", role="employer")
        emp1.set_password("password123")
        emp2 = User(email="csvemp2@example.com", role="employer")
        emp2.set_password("password123")
        db.session.add_all([candidate, emp1, emp2])
        db.session.commit()
        profile = CandidateProfile(
            user_id=candidate.id, full_name="Isolation Test", role_wanted="Dev", skills="Python",
            location="Colombo", experience_level="Junior", contact_email="csv2@example.com",
            cover_letter="Hi.",
        )
        db.session.add(profile)
        db.session.commit()

        login(client, "csvemp1@example.com", "password123")
        client.post(f"/employer/shortlist/{profile.id}")
        client.get("/auth/logout")

        login(client, "csvemp2@example.com", "password123")
        resp = client.get("/employer/shortlist/export.csv")
        assert b"Isolation Test" not in resp.data
