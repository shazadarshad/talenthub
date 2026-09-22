"""Tests for in-app messaging, private shortlist notes, and browse sorting."""
from app.extensions import db
from app.models import User, CandidateProfile, Conversation, Message, Shortlist
from tests.conftest import login


def _make_candidate(email, full_name, role_wanted, skills, location, level):
    user = User(email=email, role="candidate")
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    profile = CandidateProfile(
        user_id=user.id, full_name=full_name, role_wanted=role_wanted,
        skills=skills, location=location, experience_level=level,
        contact_email=email, cover_letter="Cover letter text.",
    )
    db.session.add(profile)
    db.session.commit()
    return user, profile


def _extract_csrf(html):
    import re
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    return match.group(1) if match else None


class TestMessaging:
    def test_employer_can_start_conversation(self, client, employer_user, app):
        _, profile = _make_candidate("cand1@example.com", "Alice Silva", "Dev", "Python", "Colombo", "Junior")
        login(client, "employer@example.com", "password123")

        resp = client.post(
            f"/messages/start/{profile.id}",
            data={"body": "Hi Alice, interested in your profile."},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        conv = Conversation.query.filter_by(candidate_profile_id=profile.id).first()
        assert conv is not None
        assert len(conv.messages) == 1
        assert conv.messages[0].body == "Hi Alice, interested in your profile."

    def test_starting_conversation_twice_reuses_thread(self, client, employer_user, app):
        _, profile = _make_candidate("cand2@example.com", "Bob Perera", "Dev", "Python", "Kandy", "Mid")
        login(client, "employer@example.com", "password123")

        client.post(f"/messages/start/{profile.id}", data={"body": "First message"})
        client.get(f"/messages/start/{profile.id}")  # would create a 2nd if buggy

        conversations = Conversation.query.filter_by(candidate_profile_id=profile.id).all()
        assert len(conversations) == 1

    def test_candidate_can_reply_in_thread(self, client, employer_user, app):
        candidate_user, profile = _make_candidate(
            "cand3@example.com", "Cara Fonseka", "Dev", "Python", "Galle", "Senior"
        )
        login(client, "employer@example.com", "password123")
        client.post(f"/messages/start/{profile.id}", data={"body": "Hello!"})
        conv = Conversation.query.filter_by(candidate_profile_id=profile.id).first()
        client.get("/auth/logout")

        login(client, "cand3@example.com", "password123")
        resp = client.post(
            f"/messages/thread/{conv.id}", data={"body": "Thanks for reaching out!"},
            follow_redirects=True,
        )
        assert resp.status_code == 200

        db.session.refresh(conv)
        assert len(conv.messages) == 2
        assert conv.messages[-1].sender_id == candidate_user.id

    def test_third_party_cannot_view_thread(self, client, employer_user, app):
        _, profile = _make_candidate("cand4@example.com", "Dan Silva", "Dev", "Python", "Colombo", "Entry")
        login(client, "employer@example.com", "password123")
        client.post(f"/messages/start/{profile.id}", data={"body": "Hi"})
        conv = Conversation.query.filter_by(candidate_profile_id=profile.id).first()
        client.get("/auth/logout")

        outsider = User(email="outsider@example.com", role="employer")
        outsider.set_password("password123")
        db.session.add(outsider)
        db.session.commit()

        login(client, "outsider@example.com", "password123")
        resp = client.get(f"/messages/thread/{conv.id}")
        assert resp.status_code == 403

    def test_unread_count_and_marking_as_read(self, client, employer_user, app):
        candidate_user, profile = _make_candidate(
            "cand5@example.com", "Eva Perera", "Dev", "Python", "Matara", "Junior"
        )
        login(client, "employer@example.com", "password123")
        client.post(f"/messages/start/{profile.id}", data={"body": "Hi Eva"})
        conv = Conversation.query.filter_by(candidate_profile_id=profile.id).first()
        client.get("/auth/logout")

        login(client, "cand5@example.com", "password123")
        assert conv.unread_count_for(candidate_user.id) == 1

        # Opening the thread should mark it as read.
        client.get(f"/messages/thread/{conv.id}")
        db.session.refresh(conv)
        assert conv.unread_count_for(candidate_user.id) == 0

    def test_candidate_cannot_start_conversation(self, client, candidate_user, app):
        _, profile = _make_candidate("cand6@example.com", "Fay Silva", "Dev", "Python", "Colombo", "Mid")
        login(client, "candidate@example.com", "password123")
        resp = client.post(f"/messages/start/{profile.id}", data={"body": "Hi"})
        assert resp.status_code == 403

    def test_inbox_shows_conversation(self, client, employer_user, app):
        _, profile = _make_candidate("cand7@example.com", "Gia Fernando", "Dev", "Python", "Colombo", "Senior")
        login(client, "employer@example.com", "password123")
        client.post(f"/messages/start/{profile.id}", data={"body": "Hi Gia"})

        resp = client.get("/messages/inbox")
        assert b"Gia Fernando" in resp.data


class TestShortlistNotes:
    def test_employer_can_save_note(self, client, employer_user, app):
        _, profile = _make_candidate("cand8@example.com", "Hana Rathnayake", "Dev", "Python", "Colombo", "Mid")
        login(client, "employer@example.com", "password123")
        client.post(f"/employer/shortlist/{profile.id}")

        resp = client.post(
            f"/employer/shortlist/{profile.id}/note",
            data={"note": "Call Tuesday, strong candidate."},
            follow_redirects=True,
        )
        assert resp.status_code == 200

        entry = Shortlist.query.filter_by(candidate_profile_id=profile.id).first()
        assert entry.note == "Call Tuesday, strong candidate."

    def test_note_appears_on_dashboard(self, client, employer_user, app):
        _, profile = _make_candidate("cand9@example.com", "Ian Bandara", "Dev", "Python", "Colombo", "Junior")
        login(client, "employer@example.com", "password123")
        client.post(f"/employer/shortlist/{profile.id}")
        client.post(f"/employer/shortlist/{profile.id}/note", data={"note": "Great communicator"})

        resp = client.get("/employer/dashboard")
        assert b"Great communicator" in resp.data

    def test_cannot_note_a_candidate_not_on_own_shortlist(self, client, employer_user, app):
        _, profile = _make_candidate("cand10@example.com", "Jaz Herath", "Dev", "Python", "Colombo", "Entry")
        login(client, "employer@example.com", "password123")
        # Never shortlisted this candidate.
        resp = client.post(f"/employer/shortlist/{profile.id}/note", data={"note": "Sneaky note"})
        assert resp.status_code == 404

    def test_note_is_private_to_the_employer_who_wrote_it(self, client, app):
        _, profile = _make_candidate("cand11@example.com", "Kai Silva", "Dev", "Python", "Colombo", "Mid")

        employer1 = User(email="emp1@example.com", role="employer")
        employer1.set_password("password123")
        employer2 = User(email="emp2@example.com", role="employer")
        employer2.set_password("password123")
        db.session.add_all([employer1, employer2])
        db.session.commit()

        login(client, "emp1@example.com", "password123")
        client.post(f"/employer/shortlist/{profile.id}")
        client.post(f"/employer/shortlist/{profile.id}/note", data={"note": "Employer 1's private thoughts"})
        client.get("/auth/logout")

        login(client, "emp2@example.com", "password123")
        client.post(f"/employer/shortlist/{profile.id}")
        resp = client.get("/employer/dashboard")
        assert b"Employer 1's private thoughts" not in resp.data


class TestBrowseSorting:
    def test_sort_by_experience_orders_senior_first(self, client, employer_user, app):
        _make_candidate("s1@example.com", "Junior Person", "Dev", "Python", "Colombo", "Junior")
        _make_candidate("s2@example.com", "Senior Person", "Dev", "Python", "Colombo", "Senior")

        login(client, "employer@example.com", "password123")
        resp = client.get("/employer/browse?sort=experience")
        content = resp.data.decode()
        assert content.index("Senior Person") < content.index("Junior Person")

    def test_sort_by_recent_orders_newest_first(self, client, employer_user, app):
        _make_candidate("r1@example.com", "First Created", "Dev", "Python", "Colombo", "Entry")
        _make_candidate("r2@example.com", "Second Created", "Dev", "Python", "Colombo", "Entry")

        login(client, "employer@example.com", "password123")
        resp = client.get("/employer/browse?sort=recent")
        content = resp.data.decode()
        assert content.index("Second Created") < content.index("First Created")

    def test_sort_by_views_orders_most_viewed_first(self, client, employer_user, app):
        _, p1 = _make_candidate("v1@example.com", "Rarely Viewed", "Dev", "Python", "Colombo", "Entry")
        _, p2 = _make_candidate("v2@example.com", "Often Viewed", "Dev", "Python", "Colombo", "Entry")

        login(client, "employer@example.com", "password123")
        # View "Often Viewed" a few times via different employer accounts to
        # rack up view count (own-view dedup only applies per employer).
        client.get(f"/employer/candidate/{p2.id}")

        other = User(email="viewer2@example.com", role="employer")
        other.set_password("password123")
        db.session.add(other)
        db.session.commit()
        client.get("/auth/logout")
        login(client, "viewer2@example.com", "password123")
        client.get(f"/employer/candidate/{p2.id}")

        resp = client.get("/employer/browse?sort=views")
        content = resp.data.decode()
        assert content.index("Often Viewed") < content.index("Rarely Viewed")

    def test_invalid_sort_falls_back_to_recent(self, client, employer_user, app):
        _make_candidate("i1@example.com", "Some Person", "Dev", "Python", "Colombo", "Entry")
        resp = login(client, "employer@example.com", "password123")
        resp = client.get("/employer/browse?sort=nonsense")
        assert resp.status_code == 200
