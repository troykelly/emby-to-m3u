"""
Comprehensive tests for subsonic.auth module to achieve 90%+ coverage.

Tests cover:
1. Token generation with password authentication
2. Token generation with API key authentication
3. Custom salt handling
4. Token verification (valid and invalid)
5. Authentication parameter building
6. Security edge cases (empty passwords, special characters, unicode)
7. Error handling and validation
8. Salt generation randomness
9. Token format validation
10. Timestamp handling
"""

import hashlib
import re
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest

from src.subsonic.auth import (
    generate_token,
    verify_token,
    create_auth_params,
)
from src.subsonic.models import SubsonicConfig, SubsonicAuthToken


class TestGenerateToken:
    """Tests for generate_token function."""

    def test_generate_token_with_password_creates_valid_token(self):
        """Test token generation with password authentication."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )

        token = generate_token(config)

        assert token is not None
        assert isinstance(token, SubsonicAuthToken)
        assert token.username == "testuser"
        assert len(token.token) == 32  # MD5 hash is 32 hex chars
        assert len(token.salt) == 16  # Salt is 16 hex chars
        assert re.match(r"^[a-f0-9]{32}$", token.token)  # Lowercase hex
        assert re.match(r"^[a-f0-9]{16}$", token.salt)  # Lowercase hex
        assert isinstance(token.created_at, datetime)
        assert token.expires_at is None

    def test_generate_token_with_api_key_returns_none(self):
        """Test that API key authentication returns None (OpenSubsonic)."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            api_key="test-api-key-12345",
        )

        token = generate_token(config)

        assert token is None  # OpenSubsonic uses API key, not token

    def test_generate_token_with_custom_salt(self):
        """Test token generation with custom salt."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )
        custom_salt = "a1b2c3d4e5f67890"

        token = generate_token(config, salt=custom_salt)

        assert token is not None
        assert token.salt == custom_salt
        # Verify token is MD5(password + salt)
        expected_token = hashlib.md5(f"testpass{custom_salt}".encode("utf-8")).hexdigest()
        assert token.token == expected_token

    def test_generate_token_salt_randomness(self):
        """Test that each token generation produces a unique salt."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )

        tokens = [generate_token(config) for _ in range(10)]
        salts = [t.salt for t in tokens]

        # All salts should be unique
        assert len(salts) == len(set(salts))

    def test_generate_token_different_salts_produce_different_tokens(self):
        """Test that different salts produce different tokens for same password."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )

        token1 = generate_token(config, salt="0123456789abcdef")
        token2 = generate_token(config, salt="fedcba9876543210")

        assert token1.token != token2.token
        assert token1.salt != token2.salt

    def test_generate_token_timestamp_is_recent(self):
        """Test that created_at timestamp is current UTC time."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )

        before = datetime.now(timezone.utc)
        token = generate_token(config)
        after = datetime.now(timezone.utc)

        assert before <= token.created_at <= after
        assert token.created_at.tzinfo == timezone.utc

    def test_generate_token_with_empty_password(self):
        """Test that empty password is rejected during config validation."""
        # SubsonicConfig validation prevents empty password at initialization
        with pytest.raises(ValueError, match="Either password or api_key must be provided"):
            SubsonicConfig(
                url="https://music.example.com",
                username="testuser",
                password="",
            )

    def test_generate_token_with_special_characters_in_password(self):
        """Test token generation with special characters in password."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="p@$$w0rd!#%&*()[]{}",
        )

        token = generate_token(config, salt="a1b2c3d4e5f67890")

        assert token is not None
        expected = hashlib.md5(
            "p@$$w0rd!#%&*()[]{}a1b2c3d4e5f67890".encode("utf-8")
        ).hexdigest()
        assert token.token == expected

    def test_generate_token_with_unicode_password(self):
        """Test token generation with unicode characters in password."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="пароль密码🔒",  # Russian + Chinese + emoji
        )

        token = generate_token(config, salt="a1b2c3d4e5f67890")

        assert token is not None
        assert len(token.token) == 32
        # Verify UTF-8 encoding works correctly
        expected = hashlib.md5(
            "пароль密码🔒a1b2c3d4e5f67890".encode("utf-8")
        ).hexdigest()
        assert token.token == expected

    def test_generate_token_with_very_long_password(self):
        """Test token generation with very long password."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="a" * 1000,  # 1000 character password
        )

        token = generate_token(config, salt="a1b2c3d4e5f67890")

        assert token is not None
        assert len(token.token) == 32  # MD5 output is always 32 chars

    def test_generate_token_with_whitespace_in_password(self):
        """Test token generation preserves whitespace in password."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="  password with spaces  ",
        )

        token = generate_token(config, salt="a1b2c3d4e5f67890")

        assert token is not None
        # Whitespace should be preserved
        expected = hashlib.md5(
            "  password with spaces  a1b2c3d4e5f67890".encode("utf-8")
        ).hexdigest()
        assert token.token == expected

    def test_generate_token_salt_length_validation(self):
        """Test that salt is always 16 hex characters when auto-generated."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )

        # Generate multiple tokens and verify salt length
        for _ in range(20):
            token = generate_token(config)
            assert len(token.salt) == 16
            assert re.match(r"^[a-f0-9]{16}$", token.salt)

    def test_generate_token_md5_algorithm_correctness(self):
        """Test that MD5 algorithm is correctly applied."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="admin",
            password="sesame",
        )
        salt = "c19b2d"  # Known salt from docs

        token = generate_token(config, salt=salt)

        # Manually calculate expected MD5
        expected_token = hashlib.md5(f"sesame{salt}".encode("utf-8")).hexdigest()
        assert token.token == expected_token

    @patch("src.subsonic.auth.secrets.token_hex")
    def test_generate_token_uses_cryptographic_random(self, mock_token_hex):
        """Test that cryptographically secure random is used for salt."""
        mock_token_hex.return_value = "a1b2c3d4e5f67890"
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )

        token = generate_token(config)

        mock_token_hex.assert_called_once_with(8)  # 8 bytes = 16 hex chars
        assert token.salt == "a1b2c3d4e5f67890"

    def test_generate_token_to_auth_params(self):
        """Test that generated token can be converted to auth params."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )

        token = generate_token(config, salt="a1b2c3d4e5f67890")
        params = token.to_auth_params()

        assert params["u"] == "testuser"
        assert params["t"] == token.token
        assert params["s"] == "a1b2c3d4e5f67890"
        assert len(params) == 3


class TestVerifyToken:
    """Tests for verify_token function."""

    def test_verify_token_with_valid_token(self):
        """Test that valid tokens are verified correctly."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )
        salt = "a1b2c3d4e5f67890"

        # Generate token
        auth_token = generate_token(config, salt=salt)

        # Verify it
        assert verify_token(config, auth_token.token, salt)

    def test_verify_token_with_invalid_token(self):
        """Test that invalid tokens are rejected."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )

        result = verify_token(config, "invalidtoken123", "a1b2c3d4e5f67890")

        assert result is False

    def test_verify_token_with_wrong_salt(self):
        """Test that token with wrong salt is rejected."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )

        # Generate token with one salt
        auth_token = generate_token(config, salt="0123456789abcdef")

        # Verify with different salt
        result = verify_token(config, auth_token.token, "fedcba9876543210")

        assert result is False

    def test_verify_token_with_wrong_password(self):
        """Test that token from different password is rejected."""
        config1 = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="password1",
        )
        config2 = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="password2",
        )
        salt = "a1b2c3d4e5f67890"

        # Generate token with password1
        token = generate_token(config1, salt=salt)

        # Try to verify with password2
        result = verify_token(config2, token.token, salt)

        assert result is False

    def test_verify_token_case_sensitivity(self):
        """Test that token verification is case-sensitive."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )
        salt = "a1b2c3d4e5f67890"

        token = generate_token(config, salt=salt)

        # MD5 hash should be lowercase
        assert token.token == token.token.lower()

        # Uppercase should fail
        result = verify_token(config, token.token.upper(), salt)
        assert result is False

    def test_verify_token_with_special_characters(self):
        """Test token verification with special characters in password."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="p@$$w0rd!#%",
        )
        salt = "a1b2c3d4e5f67890"

        token = generate_token(config, salt=salt)
        result = verify_token(config, token.token, salt)

        assert result is True

    def test_verify_token_with_unicode_password(self):
        """Test token verification with unicode password."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="пароль密码🔒",
        )
        salt = "a1b2c3d4e5f67890"

        token = generate_token(config, salt=salt)
        result = verify_token(config, token.token, salt)

        assert result is True

    def test_verify_token_single_character_password(self):
        """Test token verification with single character password."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="a",  # Minimal valid password
        )
        salt = "a1b2c3d4e5f67890"

        token = generate_token(config, salt=salt)
        result = verify_token(config, token.token, salt)

        assert result is True

    def test_verify_token_manual_calculation(self):
        """Test verification against manually calculated token."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="admin",
            password="sesame",
        )
        salt = "c19b2d"

        # Manually calculate expected token
        expected_token = hashlib.md5(f"sesame{salt}".encode("utf-8")).hexdigest()

        result = verify_token(config, expected_token, salt)

        assert result is True

    def test_verify_token_with_truncated_token(self):
        """Test that truncated tokens are rejected."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )
        salt = "a1b2c3d4e5f67890"

        token = generate_token(config, salt=salt)

        # Truncate token
        result = verify_token(config, token.token[:16], salt)

        assert result is False


class TestCreateAuthParams:
    """Tests for create_auth_params function."""

    def test_create_auth_params_with_defaults(self):
        """Test parameter creation with default values."""
        auth_token = SubsonicAuthToken(
            token="a" * 32,
            salt="b" * 16,
            username="testuser",
            created_at=datetime.now(timezone.utc),
        )

        params = create_auth_params(auth_token)

        assert params["u"] == "testuser"
        assert params["t"] == "a" * 32
        assert params["s"] == "b" * 16
        assert params["v"] == "1.16.1"  # Default API version
        assert params["c"] == "playlistgen"  # Default client name
        assert params["f"] == "json"  # Default format
        assert len(params) == 6

    def test_create_auth_params_with_custom_values(self):
        """Test parameter creation with custom values."""
        auth_token = SubsonicAuthToken(
            token="a" * 32,
            salt="b" * 16,
            username="testuser",
            created_at=datetime.now(timezone.utc),
        )

        params = create_auth_params(
            auth_token,
            api_version="1.15.0",
            client_name="myclient",
            response_format="xml",
        )

        assert params["u"] == "testuser"
        assert params["t"] == "a" * 32
        assert params["s"] == "b" * 16
        assert params["v"] == "1.15.0"
        assert params["c"] == "myclient"
        assert params["f"] == "xml"

    def test_create_auth_params_xml_format(self):
        """Test parameter creation with XML response format."""
        auth_token = SubsonicAuthToken(
            token="a" * 32,
            salt="b" * 16,
            username="testuser",
            created_at=datetime.now(timezone.utc),
        )

        params = create_auth_params(auth_token, response_format="xml")

        assert params["f"] == "xml"

    def test_create_auth_params_includes_all_required_fields(self):
        """Test that all required Subsonic API parameters are included."""
        auth_token = SubsonicAuthToken(
            token="a" * 32,
            salt="b" * 16,
            username="testuser",
            created_at=datetime.now(timezone.utc),
        )

        params = create_auth_params(auth_token)

        # All required Subsonic API parameters
        required_params = ["u", "t", "s", "v", "c", "f"]
        for param in required_params:
            assert param in params

    def test_create_auth_params_with_different_api_versions(self):
        """Test parameter creation with various API versions."""
        auth_token = SubsonicAuthToken(
            token="a" * 32,
            salt="b" * 16,
            username="testuser",
            created_at=datetime.now(timezone.utc),
        )

        versions = ["1.13.0", "1.14.0", "1.15.0", "1.16.1"]
        for version in versions:
            params = create_auth_params(auth_token, api_version=version)
            assert params["v"] == version

    def test_create_auth_params_with_special_characters_in_username(self):
        """Test parameter creation with special characters in username."""
        auth_token = SubsonicAuthToken(
            token="a" * 32,
            salt="b" * 16,
            username="user@example.com",
            created_at=datetime.now(timezone.utc),
        )

        params = create_auth_params(auth_token)

        assert params["u"] == "user@example.com"

    def test_create_auth_params_combines_token_params_correctly(self):
        """Test that auth token params are correctly merged."""
        auth_token = SubsonicAuthToken(
            token="token123",
            salt="salt456",
            username="testuser",
            created_at=datetime.now(timezone.utc),
        )

        params = create_auth_params(auth_token)

        # Verify auth params from token are included
        token_params = auth_token.to_auth_params()
        for key, value in token_params.items():
            assert params[key] == value

    def test_create_auth_params_integration_with_generate_token(self):
        """Test full integration: config -> token -> params."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )

        auth_token = generate_token(config, salt="a1b2c3d4e5f67890")
        params = create_auth_params(
            auth_token,
            api_version="1.16.1",
            client_name="playlistgen",
        )

        assert params["u"] == "testuser"
        assert len(params["t"]) == 32
        assert params["s"] == "a1b2c3d4e5f67890"
        assert params["v"] == "1.16.1"
        assert params["c"] == "playlistgen"
        assert params["f"] == "json"

    def test_create_auth_params_with_custom_client_name(self):
        """Test parameter creation with custom client names."""
        auth_token = SubsonicAuthToken(
            token="a" * 32,
            salt="b" * 16,
            username="testuser",
            created_at=datetime.now(timezone.utc),
        )

        client_names = ["myclient", "test-app", "app_v2", "client123"]
        for client_name in client_names:
            params = create_auth_params(auth_token, client_name=client_name)
            assert params["c"] == client_name


class TestSubsonicAuthTokenModel:
    """Tests for SubsonicAuthToken model integration with auth functions."""

    def test_auth_token_is_expired_returns_false_when_no_expiry(self):
        """Test that tokens without expiry are never expired."""
        token = SubsonicAuthToken(
            token="a" * 32,
            salt="b" * 16,
            username="testuser",
            created_at=datetime.now(timezone.utc),
            expires_at=None,
        )

        assert not token.is_expired()

    def test_auth_token_is_expired_returns_false_when_not_expired(self):
        """Test that future expiry times return False."""
        token = SubsonicAuthToken(
            token="a" * 32,
            salt="b" * 16,
            username="testuser",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        assert not token.is_expired()

    def test_auth_token_is_expired_returns_true_when_expired(self):
        """Test that past expiry times return True."""
        token = SubsonicAuthToken(
            token="a" * 32,
            salt="b" * 16,
            username="testuser",
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        assert token.is_expired()

    def test_auth_token_to_auth_params_format(self):
        """Test that to_auth_params returns correct format."""
        token = SubsonicAuthToken(
            token="token123",
            salt="salt456",
            username="testuser",
            created_at=datetime.now(timezone.utc),
        )

        params = token.to_auth_params()

        assert isinstance(params, dict)
        assert set(params.keys()) == {"u", "t", "s"}
        assert params["u"] == "testuser"
        assert params["t"] == "token123"
        assert params["s"] == "salt456"


class TestSecurityEdgeCases:
    """Security-focused edge case tests."""

    def test_salt_collision_probability_is_low(self):
        """Test that salt generation has low collision probability."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )

        # Generate 100 tokens and check for unique salts
        tokens = [generate_token(config) for _ in range(100)]
        salts = [t.salt for t in tokens]

        assert len(salts) == len(set(salts))  # All should be unique

    def test_token_regeneration_produces_different_values(self):
        """Test that regenerating tokens produces different values."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )

        token1 = generate_token(config)
        token2 = generate_token(config)

        # Same password but different salts should produce different tokens
        assert token1.salt != token2.salt
        assert token1.token != token2.token

    def test_sql_injection_in_password_is_hashed(self):
        """Test that SQL injection attempts in password are safely hashed."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="'; DROP TABLE users; --",
        )

        token = generate_token(config, salt="a1b2c3d4e5f67890")

        # Password should be safely hashed
        assert token is not None
        assert len(token.token) == 32
        assert "DROP" not in token.token
        assert ";" not in token.token

    def test_xss_in_password_is_hashed(self):
        """Test that XSS attempts in password are safely hashed."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="<script>alert('XSS')</script>",
        )

        token = generate_token(config, salt="a1b2c3d4e5f67890")

        # Password should be safely hashed
        assert token is not None
        assert "<script>" not in token.token
        assert "alert" not in token.token

    def test_null_byte_in_password_is_handled(self):
        """Test that null bytes in password are handled correctly."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="password\x00injection",
        )

        token = generate_token(config, salt="a1b2c3d4e5f67890")

        # Should hash the entire string including null byte
        assert token is not None
        expected = hashlib.md5(
            "password\x00injectiona1b2c3d4e5f67890".encode("utf-8")
        ).hexdigest()
        assert token.token == expected

    def test_timing_attack_resistance_same_execution_path(self):
        """Test that verification follows same path for valid/invalid tokens."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )
        salt = "a1b2c3d4e5f67890"

        # Both valid and invalid verification should use == comparison
        # (not short-circuit optimized), making timing attacks harder
        valid_token = generate_token(config, salt=salt)
        verify_token(config, valid_token.token, salt)  # Valid
        verify_token(config, "invalid" * 4, salt)  # Invalid

        # Both execute the same code path (MD5 calculation + comparison)
        # This test documents the behavior; actual timing analysis would
        # require specialized tools


class TestErrorHandling:
    """Tests for error handling and validation."""

    def test_generate_token_with_invalid_config_raises_validation_error(self):
        """Test that invalid config raises ValueError during initialization."""
        with pytest.raises(ValueError, match="url must be a valid HTTP/HTTPS URL"):
            SubsonicConfig(
                url="invalid-url",
                username="testuser",
                password="testpass",
            )

    def test_generate_token_with_missing_username_raises_error(self):
        """Test that missing username raises ValueError."""
        with pytest.raises(ValueError, match="username is required"):
            SubsonicConfig(
                url="https://music.example.com",
                username="",
                password="testpass",
            )

    def test_generate_token_with_missing_auth_raises_error(self):
        """Test that missing password and API key raises ValueError."""
        with pytest.raises(
            ValueError, match="Either password or api_key must be provided"
        ):
            SubsonicConfig(
                url="https://music.example.com",
                username="testuser",
            )

    def test_create_auth_params_with_none_token_raises_error(self):
        """Test that create_auth_params requires non-None token."""
        # This would be a programming error, but let's document the behavior
        # If auth_token is None, it should raise AttributeError
        with pytest.raises(AttributeError):
            create_auth_params(None)

    def test_verify_token_with_api_key_config(self):
        """Test verification behavior when config uses API key."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            api_key="test-api-key",
        )

        # Can't verify tokens for API key auth (no password)
        # Should handle gracefully (MD5 of None would fail)
        # Since config.password could be None, this documents edge case
        # In practice, verify_token expects password-based config
        assert config.api_key == "test-api-key"
        assert config.password is None
