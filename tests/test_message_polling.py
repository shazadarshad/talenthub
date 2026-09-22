"""Tests for live message polling: the /poll and /unread-count endpoints,
plus sending a reply via AJAX (fetch), which is how the thread page
avoids needing a manual page refresh to see new messages.
"""
from app.extensions import db
from app.models import User, CandidateProfile, Conversation
from tests.conftest import login


def _make_candidate(email, full_name):
    user = User(email=email, role="candidate")
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    profile = CandidateProfile(
        user_id=user.id, full_name=full_name, role_wanted="Dev",
        skills="Python", location="Colombo", experience_level="Junior",
        contact_email=email, cover_letter="Hi.",
    )
    db.session.add(profile)
    db.session.commit()
    return user, profile


class TestMessagePolling:
    def test_poll_returns_no_messages_when_nothing_new(self, client, employer_user, app):
        _, profile = _make_candidate("poll1@example.com", "Poll Test One")
        login(client, "employer@example.com", "password123")
        client.post(f"/messages/start/{profile.id}", data={"body": "Hi there"})
        conv = Conversation.query.filter_by(candidate_profile_id=profile.id).first()

        resp = client.get(f"/messages/thread/{conv.id}/poll?after={conv.messages[0].id}")
        assert resp.status_code == 200
        assert resp.get_json()["messages"] == []

    def test_poll_returns_new_message_sent_by_other_party(self, client, employer_user, app):
        candidate_user, profile = _make_candidate("poll2@example.com", "Poll Test Two")
        login(client, "employer@example.com", "password123")
        client.post(f"/messages/start/{profile.id}", data={"body": "Hi there"})
        conv = Conversation.query.filter_by(candidate_profile_id=profile.id).first()
        first_id = conv.messages[0].id
        client.get("/auth/logout")

        # Candidate replies - this simulates the "other browser tab" sending
        # a message while the employer's poll loop is running.
        login(client, "poll2@example.com", "password123")
        client.post(f"/messages/thread/{conv.id}", data={"body": "Hello back!"})
        client.get("/auth/logout")

        login(client, "employer@example.com", "password123")
        resp = client.get(f"/messages/thread/{conv.id}/poll?after={first_id}")
        data = resp.get_json()
        assert len(data["messages"]) == 1
        assert data["messages"][0]["body"] == "Hello back!"
        assert data["messages"][0]["is_own"] is False

    def test_poll_marks_new_messages_as_read(self, client, employer_user, app):
        candidate_user, profile = _make_candidate("poll3@example.com", "Poll Test Three")
        login(client, "employer@example.com", "password123")
        client.post(f"/messages/start/{profile.id}", data={"body": "Hi"})
        conv = Conversation.query.filter_by(candidate_profile_id=profile.id).first()
        first_id = conv.messages[0].id
        client.get("/auth/logout")

        login(client, "poll3@example.com", "password123")
        client.post(f"/messages/thread/{conv.id}", data={"body": "Reply"})
        client.get("/auth/logout")

        login(client, "employer@example.com", "password123")
        assert conv.unread_count_for(employer_user.id if False else conv.employer_id) >= 0
        client.get(f"/messages/thread/{conv.id}/poll?after={first_id}")

        db.session.refresh(conv)
        unread = [m for m in conv.messages if m.sender_id == candidate_user.id and not m.read]
        assert unread == []

    def test_poll_rejects_non_participant(self, client, employer_user, app):
        _, profile = _make_candidate("poll4@example.com", "Poll Test Four")
        login(client, "employer@example.com", "password123")
        client.post(f"/messages/start/{profile.id}", data={"body": "Hi"})
        conv = Conversation.query.filter_by(candidate_profile_id=profile.id).first()
        client.get("/auth/logout")

        outsider = User(email="pollout@example.com", role="employer")
        outsider.set_password("password123")
        db.session.add(outsider)
        db.session.commit()
        login(client, "pollout@example.com", "password123")

        resp = client.get(f"/messages/thread/{conv.id}/poll?after=0")
        assert resp.status_code == 403

    def test_ajax_send_returns_json_message(self, client, employer_user, app):
        _, profile = _make_candidate("poll5@example.com", "Poll Test Five")
        login(client, "employer@example.com", "password123")
        client.post(f"/messages/start/{profile.id}", data={"body": "First"})
        conv = Conversation.query.filter_by(candidate_profile_id=profile.id).first()

        resp = client.post(
            f"/messages/thread/{conv.id}",
            data={"body": "Sent via AJAX"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["message"]["body"] == "Sent via AJAX"
        assert data["message"]["is_own"] is True

    def test_ajax_send_with_empty_body_returns_error(self, client, employer_user, app):
        _, profile = _make_candidate("poll6@example.com", "Poll Test Six")
        login(client, "employer@example.com", "password123")
        client.post(f"/messages/start/{profile.id}", data={"body": "First"})
        conv = Conversation.query.filter_by(candidate_profile_id=profile.id).first()

        resp = client.post(
            f"/messages/thread/{conv.id}",
            data={"body": "   "},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert resp.status_code == 400


class TestUnreadCountEndpoint:
    def test_unread_count_reflects_new_messages(self, client, employer_user, app):
        candidate_user, profile = _make_candidate("poll7@example.com", "Poll Test Seven")
        login(client, "employer@example.com", "password123")
        client.post(f"/messages/start/{profile.id}", data={"body": "Hi"})
        conv = Conversation.query.filter_by(candidate_profile_id=profile.id).first()
        client.get("/auth/logout")

        login(client, "poll7@example.com", "password123")
        resp = client.get("/messages/unread-count")
        assert resp.get_json()["count"] == 1

        client.get(f"/messages/thread/{conv.id}")  # opening marks as read
        resp = client.get("/messages/unread-count")
        assert resp.get_json()["count"] == 0

    def test_unread_count_requires_login(self, client):
        resp = client.get("/messages/unread-count", follow_redirects=True)
        assert b"Log In" in resp.data or b"Please log in" in resp.data
