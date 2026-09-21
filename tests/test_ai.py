"""
Tests for AI features (CV summarization, smart search ranking).

Every OpenAI call is mocked - these tests never make a real network
request or cost real money, and they don't require a real API key.
"""
import json
from unittest.mock import patch, MagicMock

import pytest

from app import create_app
from app.extensions import db
from app.models import User, CandidateProfile
from app import ai
from tests.conftest import login


@pytest.fixture()
def ai_app():
    """An app instance with a fake OpenAI API key configured, so the AI
    functions think AI is "enabled" and proceed to (mocked) calls.
    """
    app = create_app("testing")
    app.config["OPENAI_API_KEY"] = "sk-fake-test-key"
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def ai_client(ai_app):
    return ai_app.test_client()


def _mock_openai_response(payload_dict):
    """Build a fake OpenAI ChatCompletion response object with the given
    JSON payload as the message content, matching the real response shape
    closely enough for our code to read `.choices[0].message.content`.
    """
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps(payload_dict)
    return mock_response


class TestSummarizeCv:
    def test_returns_none_without_api_key(self, app):
        """With no OPENAI_API_KEY configured, summarize_cv should quietly
        do nothing rather than error."""
        with app.app_context():
            app.config["OPENAI_API_KEY"] = ""
            result = ai.summarize_cv("Some CV text here.")
            assert result is None

    def test_returns_none_for_empty_text(self, ai_app):
        with ai_app.app_context():
            result = ai.summarize_cv("   ")
            assert result is None

    def test_parses_successful_response(self, ai_app):
        fake_payload = {
            "summary": "Experienced Python developer with strong backend skills.",
            "skills": ["Python", "Flask", "SQL"],
            "experience_years": 3,
        }
        with ai_app.app_context():
            with patch("app.ai._get_client") as mock_get_client:
                mock_client = MagicMock()
                mock_client.chat.completions.create.return_value = _mock_openai_response(fake_payload)
                mock_get_client.return_value = mock_client

                result = ai.summarize_cv("I am a Python developer with 3 years experience.")

        assert result is not None
        assert result["summary"] == fake_payload["summary"]
        assert result["skills"] == ["Python", "Flask", "SQL"]
        assert result["experience_years"] == 3

    def test_handles_api_failure_gracefully(self, ai_app):
        """If the OpenAI call raises (network error, rate limit, etc.),
        summarize_cv should return None instead of crashing."""
        with ai_app.app_context():
            with patch("app.ai._get_client") as mock_get_client:
                mock_client = MagicMock()
                mock_client.chat.completions.create.side_effect = Exception("API is down")
                mock_get_client.return_value = mock_client

                result = ai.summarize_cv("Some CV text.")

        assert result is None


class TestRankCandidates:
    def test_empty_query_returns_unranked(self, ai_app):
        with ai_app.app_context():
            candidates = [MagicMock(id=1), MagicMock(id=2)]
            result = ai.rank_candidates("", candidates)
        assert result == [(candidates[0], ""), (candidates[1], "")]

    def test_no_candidates_returns_empty(self, ai_app):
        with ai_app.app_context():
            result = ai.rank_candidates("python developer", [])
        assert result == []

    def test_ranks_and_includes_reasons(self, ai_app, app):
        with app.app_context():
            u1 = User(email="a@example.com", role="candidate")
            u1.set_password("password123")
            u2 = User(email="b@example.com", role="candidate")
            u2.set_password("password123")
            db.session.add_all([u1, u2])
            db.session.commit()

            p1 = CandidateProfile(
                user_id=u1.id, full_name="Alice", role_wanted="Backend Dev",
                skills="Python, SQL", location="Colombo", experience_level="Mid",
                contact_email="a@example.com", cover_letter="Backend focused.",
            )
            p2 = CandidateProfile(
                user_id=u2.id, full_name="Bob", role_wanted="Frontend Dev",
                skills="React, CSS", location="Kandy", experience_level="Junior",
                contact_email="b@example.com", cover_letter="Frontend focused.",
            )
            db.session.add_all([p1, p2])
            db.session.commit()

            fake_payload = {
                "ranking": [
                    {"id": p1.id, "reason": "Strong Python/SQL backend match"},
                    {"id": p2.id, "reason": "Frontend skills, less relevant"},
                ]
            }
            with patch("app.ai._get_client") as mock_get_client:
                mock_client = MagicMock()
                mock_client.chat.completions.create.return_value = _mock_openai_response(fake_payload)
                mock_get_client.return_value = mock_client

                result = ai.rank_candidates("backend python developer", [p1, p2])

            assert len(result) == 2
            assert result[0][0].full_name == "Alice"
            assert "Python" in result[0][1] or "backend" in result[0][1].lower()

    def test_falls_back_to_original_order_on_failure(self, ai_app, app):
        with app.app_context():
            u1 = User(email="c@example.com", role="candidate")
            u1.set_password("password123")
            db.session.add(u1)
            db.session.commit()
            p1 = CandidateProfile(
                user_id=u1.id, full_name="Charlie", role_wanted="Dev",
                skills="Python", location="Remote", experience_level="Entry",
                contact_email="c@example.com", cover_letter="Hi.",
            )
            db.session.add(p1)
            db.session.commit()

            with patch("app.ai._get_client") as mock_get_client:
                mock_client = MagicMock()
                mock_client.chat.completions.create.side_effect = Exception("boom")
                mock_get_client.return_value = mock_client

                result = ai.rank_candidates("anything", [p1])

            assert result == [(p1, "")]


class TestAiSummaryIntegration:
    """Confirms the profile creation flow calls the AI summarizer and
    stores its result, without ever hitting the real OpenAI API.
    """

    def test_profile_creation_stores_ai_summary_when_available(self, ai_app, ai_client):
        import io

        with ai_app.app_context():
            candidate = User(email="applicant@example.com", role="candidate")
            candidate.set_password("password123")
            db.session.add(candidate)
            db.session.commit()

        login(ai_client, "applicant@example.com", "password123")

        fake_payload = {
            "summary": "A capable developer with full-stack experience.",
            "skills": ["Python", "Flask"],
            "experience_years": 2,
        }
        with patch("app.ai._get_client") as mock_get_client, \
             patch("app.candidates.routes.extract_pdf_text", return_value="Fake extracted CV text"):
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = _mock_openai_response(fake_payload)
            mock_get_client.return_value = mock_client

            pdf = (io.BytesIO(b"%PDF-1.4 fake"), "cv.pdf")
            ai_client.post(
                "/candidates/profile/new",
                data={
                    "full_name": "Applicant Person", "role_wanted": "Developer",
                    "skills": "Python", "location": "Remote", "experience_level": "Junior",
                    "contact_email": "applicant@example.com", "cover_letter": "Hi there.",
                    "cv": pdf,
                },
                content_type="multipart/form-data",
            )

        with ai_app.app_context():
            profile = CandidateProfile.query.filter_by(full_name="Applicant Person").first()
            assert profile is not None
            assert profile.ai_summary == fake_payload["summary"]
            assert profile.ai_experience_years == 2
            assert "Python" in profile.ai_skills

    def test_profile_creation_works_without_ai_configured(self, client, candidate_user):
        """The app must still work perfectly with no OPENAI_API_KEY set -
        this is the default test config, so AI is off by default here."""
        import io

        login(client, "candidate@example.com", "password123")
        pdf = (io.BytesIO(b"%PDF-1.4 fake"), "cv.pdf")
        resp = client.post(
            "/candidates/profile/new",
            data={
                "full_name": "No AI Person", "role_wanted": "Developer",
                "skills": "Python", "location": "Remote", "experience_level": "Junior",
                "contact_email": "candidate@example.com", "cover_letter": "Hi there.",
                "cv": pdf,
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        profile = CandidateProfile.query.filter_by(full_name="No AI Person").first()
        assert profile is not None
        assert profile.ai_summary is None
