"""Tests for authentication module."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, AsyncMock

import jwt
import pytest

from app.core.auth import decode_jwt, TokenPayload


class TestDecodeJWT:
    """Tests for JWT decoding."""

    @pytest.fixture
    def jwt_secret(self):
        """Test JWT secret."""
        return "test-secret-key-for-testing"

    def test_decode_valid_token(self, jwt_secret):
        """Test decoding a valid JWT token."""
        payload = {
            "sub": str(uuid.uuid4()),
            "email": "test@example.com",
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }

        token = jwt.encode(payload, jwt_secret, algorithm="HS256")

        with patch("app.core.auth.get_settings") as mock_settings:
            mock_settings.return_value.supabase_jwt_secret = jwt_secret

            result = decode_jwt(token)

        assert result is not None
        assert result.sub == payload["sub"]
        assert result.email == payload["email"]

    def test_decode_expired_token(self, jwt_secret):
        """Test that expired tokens return None."""
        payload = {
            "sub": str(uuid.uuid4()),
            "email": "test@example.com",
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }

        token = jwt.encode(payload, jwt_secret, algorithm="HS256")

        with patch("app.core.auth.get_settings") as mock_settings:
            mock_settings.return_value.supabase_jwt_secret = jwt_secret

            result = decode_jwt(token)

        assert result is None

    def test_decode_invalid_signature(self, jwt_secret):
        """Test that tokens with invalid signature return None."""
        payload = {
            "sub": str(uuid.uuid4()),
            "email": "test@example.com",
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }

        token = jwt.encode(payload, "wrong-secret", algorithm="HS256")

        with patch("app.core.auth.get_settings") as mock_settings:
            mock_settings.return_value.supabase_jwt_secret = jwt_secret

            result = decode_jwt(token)

        assert result is None

    def test_decode_malformed_token(self, jwt_secret):
        """Test that malformed tokens return None."""
        with patch("app.core.auth.get_settings") as mock_settings:
            mock_settings.return_value.supabase_jwt_secret = jwt_secret

            result = decode_jwt("not.a.valid.token")

        assert result is None

    def test_decode_wrong_audience(self, jwt_secret):
        """Test that tokens with wrong audience return None."""
        payload = {
            "sub": str(uuid.uuid4()),
            "email": "test@example.com",
            "aud": "wrong-audience",
            "role": "authenticated",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }

        token = jwt.encode(payload, jwt_secret, algorithm="HS256")

        with patch("app.core.auth.get_settings") as mock_settings:
            mock_settings.return_value.supabase_jwt_secret = jwt_secret

            result = decode_jwt(token)

        assert result is None


class TestTokenPayload:
    """Tests for TokenPayload model."""

    def test_token_payload_required_fields(self):
        """Test TokenPayload requires sub and exp fields."""
        payload = TokenPayload(
            sub=str(uuid.uuid4()),
            exp=int(datetime.utcnow().timestamp()),
        )

        assert payload.sub is not None
        assert payload.exp is not None
        assert payload.aud == "authenticated"  # Default value
        assert payload.role == "authenticated"  # Default value

    def test_token_payload_with_email(self):
        """Test TokenPayload with optional email."""
        user_id = str(uuid.uuid4())
        payload = TokenPayload(
            sub=user_id,
            email="test@example.com",
            exp=int(datetime.utcnow().timestamp()),
        )

        assert payload.email == "test@example.com"
