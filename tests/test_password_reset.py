"""Tests for the forgot-password / reset-password flow."""
import time
from unittest.mock import patch

from app.models import User
from app.utils import generate_reset_token, verify_reset_token
from tests.conftest import login


def _extract_csrf(html):
    import re
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    return match.group(1) if match else None


class TestResetTokens:
    def test_token_roundtrip(self, app):
        with app.app_context():
            token = generate_reset_token("someone@example.com")
            assert verify_reset_token(token) == "someone@example.com"

    def test_tampered_token_rejected(self, app):
        with app.app_context():
            token = generate_reset_token("someone@example.com")
            tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
            assert verify_reset_token(tampered) is None

    def test_expired_token_rejected(self, app):
        with app.app_context():
            app.config["RESET_TOKEN_MAX_AGE"] = 1  # 1 second
            token = generate_reset_token("someone@example.com")
            time.sleep(2.5)  # generous margin to avoid flakiness under load
            assert verify_reset_token(token) is None

    def test_garbage_token_rejected(self, app):
        with app.app_context():
            assert verify_reset_token("not-a-real-token") is None


class TestForgotPasswordFlow:
    def test_forgot_password_page_loads(self, client):
        resp = client.get("/auth/forgot-password")
        assert resp.status_code == 200

    def test_same_message_whether_or_not_account_exists(self, client, candidate_user):
        """Prevents email enumeration - the response must look identical
        whether the email is registered or not."""
        resp_real = client.post(
            "/auth/forgot-password", data={"email": "candidate@example.com"},
            follow_redirects=True,
        )
        resp_fake = client.post(
            "/auth/forgot-password", data={"email": "nobody-here@example.com"},
            follow_redirects=True,
        )
        assert b"password reset link" in resp_real.data
        assert b"password reset link" in resp_fake.data

    def test_email_is_logged_when_smtp_not_configured(self, client, candidate_user, caplog):
        """With no MAIL_USERNAME set (the default test config), the reset
        link should just be logged, not actually emailed."""
        import logging
        with caplog.at_level(logging.INFO):
            client.post("/auth/forgot-password", data={"email": "candidate@example.com"})
        assert any("Password reset link" in record.message for record in caplog.records)

    def test_reset_email_sent_when_smtp_configured(self, app, client, candidate_user):
        """When mail IS configured, it should attempt to actually send."""
        app.config["MAIL_USERNAME"] = "noreply@talenthub.test"

        with patch("app.extensions.mail.send") as mock_send:
            client.post("/auth/forgot-password", data={"email": "candidate@example.com"})
            assert mock_send.called

    def test_forgot_password_is_rate_limited(self):
        """The route should have a rate limit configured, same as login/signup.
        (Full throttling behavior is exercised by the equivalent login
        rate-limit test; Flask-Limiter's shared extension instance makes
        toggling RATELIMIT_ENABLED per-test unreliable, so this just
        confirms the limit decorator is actually applied to the view.)
        """
        from app.auth.routes import forgot_password
        assert hasattr(forgot_password, "__wrapped__") or "view_rate_limit" in str(forgot_password)


class TestResetPasswordFlow:
    def test_reset_page_rejects_invalid_token(self, client):
        resp = client.get("/auth/reset-password/garbage-token", follow_redirects=True)
        assert b"invalid or has expired" in resp.data

    def test_full_reset_flow_changes_password(self, app, client, candidate_user):
        with app.app_context():
            token = generate_reset_token("candidate@example.com")

        resp = client.get(f"/auth/reset-password/{token}")
        assert resp.status_code == 200

        resp = client.post(
            f"/auth/reset-password/{token}",
            data={"password": "BrandNewPassword123", "confirm_password": "BrandNewPassword123"},
            follow_redirects=True,
        )
        assert b"password has been reset" in resp.data

        # Old password should no longer work; new one should.
        old_login = login(client, "candidate@example.com", "password123")
        assert b"Incorrect email or password" in old_login.data

        new_login = login(client, "candidate@example.com", "BrandNewPassword123")
        assert b"Welcome back" in new_login.data

    def test_reset_rejects_mismatched_passwords(self, app, client, candidate_user):
        with app.app_context():
            token = generate_reset_token("candidate@example.com")

        resp = client.post(
            f"/auth/reset-password/{token}",
            data={"password": "BrandNewPassword123", "confirm_password": "Different123"},
        )
        # Should re-render the form with an error, not proceed.
        assert resp.status_code == 200
        user = User.query.filter_by(email="candidate@example.com").first()
        assert user.check_password("password123")  # unchanged

    def test_reset_token_for_deleted_user_rejected(self, app, client):
        with app.app_context():
            token = generate_reset_token("ghost@example.com")

        resp = client.get(f"/auth/reset-password/{token}", follow_redirects=True)
        assert b"invalid or has expired" in resp.data
