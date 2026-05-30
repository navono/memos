"""Unit tests for auth module."""

import time

import jwt
import pytest

from agent.auth import verify_token


class TestVerifyToken:
    """Tests for verify_token function."""

    @pytest.fixture
    def valid_token(self):
        """Create a valid JWT token."""
        now = int(time.time())
        payload = {
            "iss": "memos",
            "sub": "101",
            "aud": "user.access-token",
            "name": "testuser",
            "iat": now,
            "exp": now + 3600,
        }
        return jwt.encode(payload, "usememos", algorithm="HS256")

    @pytest.fixture
    def token_with_custom_secret(self):
        """Create a token with custom secret for testing different secret config."""
        now = int(time.time())
        payload = {
            "iss": "memos",
            "sub": "101",
            "aud": "user.access-token",
            "iat": now,
            "exp": now + 3600,
        }
        return jwt.encode(payload, "custom-secret", algorithm="HS256")

    def test_valid_token_returns_claims(self, valid_token):
        """Valid token should return claims dict."""
        result = verify_token(valid_token)
        assert isinstance(result, dict)
        assert result["user_id"] == 101
        assert result["username"] == "testuser"

    def test_expired_token_returns_unauthorized(self):
        """Expired token should return 401 response."""
        now = int(time.time())
        payload = {
            "iss": "memos",
            "sub": "101",
            "aud": "user.access-token",
            "iat": now - 7200,
            "exp": now - 3600,  # Expired 1 hour ago
        }
        token = jwt.encode(payload, "usememos", algorithm="HS256")
        result = verify_token(token)
        assert hasattr(result, "status_code")
        assert result.status_code == 401
        assert "expired" in result.body.decode().lower()

    def test_invalid_signature_returns_unauthorized(self, token_with_custom_secret):
        """Token signed with wrong secret should return 401."""
        result = verify_token(token_with_custom_secret)
        assert hasattr(result, "status_code")
        assert result.status_code == 401

    def test_missing_issuer_returns_unauthorized(self):
        """Token without 'iss' claim should return 401."""
        now = int(time.time())
        payload = {
            "sub": "101",
            "aud": "user.access-token",
            "iat": now,
            "exp": now + 3600,
        }
        token = jwt.encode(payload, "usememos", algorithm="HS256")
        result = verify_token(token)
        assert hasattr(result, "status_code")
        assert result.status_code == 401

    def test_wrong_issuer_returns_unauthorized(self):
        """Token with wrong issuer should return 401."""
        now = int(time.time())
        payload = {
            "iss": "wrong-issuer",
            "sub": "101",
            "aud": "user.access-token",
            "iat": now,
            "exp": now + 3600,
        }
        token = jwt.encode(payload, "usememos", algorithm="HS256")
        result = verify_token(token)
        assert hasattr(result, "status_code")
        assert result.status_code == 401

    def test_missing_audience_returns_unauthorized(self):
        """Token without 'aud' claim should return 401."""
        now = int(time.time())
        payload = {
            "iss": "memos",
            "sub": "101",
            "iat": now,
            "exp": now + 3600,
        }
        token = jwt.encode(payload, "usememos", algorithm="HS256")
        result = verify_token(token)
        assert hasattr(result, "status_code")
        assert result.status_code == 401

    def test_wrong_audience_returns_unauthorized(self):
        """Token with wrong audience should return 401."""
        now = int(time.time())
        payload = {
            "iss": "memos",
            "sub": "101",
            "aud": "wrong.audience",
            "iat": now,
            "exp": now + 3600,
        }
        token = jwt.encode(payload, "usememos", algorithm="HS256")
        result = verify_token(token)
        assert hasattr(result, "status_code")
        assert result.status_code == 401

    def test_missing_subject_returns_unauthorized(self):
        """Token without 'sub' claim should return 401."""
        now = int(time.time())
        payload = {
            "iss": "memos",
            "aud": "user.access-token",
            "iat": now,
            "exp": now + 3600,
        }
        token = jwt.encode(payload, "usememos", algorithm="HS256")
        result = verify_token(token)
        assert hasattr(result, "status_code")
        assert result.status_code == 401

    def test_invalid_subject_returns_unauthorized(self):
        """Token with non-integer subject should return 401."""
        now = int(time.time())
        payload = {
            "iss": "memos",
            "sub": "not-a-number",
            "aud": "user.access-token",
            "iat": now,
            "exp": now + 3600,
        }
        token = jwt.encode(payload, "usememos", algorithm="HS256")
        result = verify_token(token)
        assert hasattr(result, "status_code")
        assert result.status_code == 401
        assert "subject" in result.body.decode().lower()

    def test_malformed_token_returns_unauthorized(self):
        """Completely invalid token string should return 401."""
        result = verify_token("not.a.valid.token")
        assert hasattr(result, "status_code")
        assert result.status_code == 401

    def test_empty_token_returns_unauthorized(self):
        """Empty string token should return 401."""
        result = verify_token("")
        assert hasattr(result, "status_code")
        assert result.status_code == 401

    def test_token_without_name_claim_still_valid(self, valid_token):
        """Token without 'name' claim should still be valid, username defaults to empty."""
        now = int(time.time())
        payload = {
            "iss": "memos",
            "sub": "101",
            "aud": "user.access-token",
            "iat": now,
            "exp": now + 3600,
        }
        token = jwt.encode(payload, "usememos", algorithm="HS256")
        result = verify_token(token)
        assert isinstance(result, dict)
        assert result["user_id"] == 101
        assert result["username"] == ""
