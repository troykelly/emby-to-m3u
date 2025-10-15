"""Tests for Subsonic authentication implementation.

This test suite validates the authentication module against:
1. Unit tests for token generation and verification
2. Contract tests against subsonic-auth.yaml specification
3. Integration tests against real Subsonic server (https://music.mctk.co)
"""

import hashlib
import re
from datetime import datetime, timezone

import pytest

from src.subsonic.auth import (
    create_auth_params,
    generate_token,
    verify_token,
)
from src.subsonic.models import SubsonicAuthToken, SubsonicConfig


class TestTokenGeneration:
    """Unit tests for token generation."""

    def test_generate_token_creates_valid_token(self):
        """Test that generate_token creates a valid authentication token."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )

        token = generate_token(config)

        # Verify token structure
        assert isinstance(token, SubsonicAuthToken)
        assert token.username == "testuser"
        assert len(token.token) == 32  # MD5 hash is 32 hex chars
        assert len(token.salt) == 16  # secrets.token_hex(8) = 16 hex chars
        assert re.match(r"^[a-f0-9]{32}$", token.token)  # Lowercase hex
        assert re.match(r"^[a-f0-9]{16}$", token.salt)  # Lowercase hex
        assert isinstance(token.created_at, datetime)
        assert token.expires_at is None

    def test_generate_token_with_custom_salt(self):
        """Test token generation with provided salt."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="admin",
            password="sesame",
        )

        # Use example from Subsonic API docs
        salt = "c19b2d"
        token = generate_token(config, salt=salt)

        # Verify salt is used
        assert token.salt == salt
        # Verify token is calculated correctly: MD5("sesamec19b2d")
        expected_token = hashlib.md5(b"sesamec19b2d").hexdigest()
        assert token.token == expected_token

    def test_generate_token_produces_unique_salts(self):
        """Test that each token generation produces unique salt."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )

        token1 = generate_token(config)
        token2 = generate_token(config)

        # Different salts should produce different tokens
        assert token1.salt != token2.salt
        assert token1.token != token2.token

    def test_generate_token_with_known_example(self):
        """Test against known example from Subsonic API documentation.

        Example from http://www.subsonic.org/pages/api.jsp:
        - username: admin
        - password: sesame
        - salt: c19b2d
        - token: 26719a1196d2a940705a59634eb18eab
        """
        config = SubsonicConfig(
            url="https://music.example.com",
            username="admin",
            password="sesame",
        )

        token = generate_token(config, salt="c19b2d")

        assert token.username == "admin"
        assert token.salt == "c19b2d"
        assert token.token == "26719a1196d2a940705a59634eb18eab"

    def test_token_to_auth_params(self):
        """Test conversion of token to authentication parameters."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )

        token = generate_token(config, salt="abcdef1234567890")

        params = token.to_auth_params()

        assert params == {
            "u": "testuser",
            "t": token.token,
            "s": "abcdef1234567890",
        }

    def test_token_is_not_expired_by_default(self):
        """Test that tokens don't expire by default."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )

        token = generate_token(config)

        assert not token.is_expired()


class TestTokenVerification:
    """Unit tests for token verification."""

    def test_verify_token_success(self):
        """Test successful token verification."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )

        salt = "test1234567890ab"
        token = generate_token(config, salt=salt)

        assert verify_token(config, token.token, salt)

    def test_verify_token_wrong_token(self):
        """Test verification fails with wrong token."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )

        salt = "test1234567890ab"
        wrong_token = "00000000000000000000000000000000"

        assert not verify_token(config, wrong_token, salt)

    def test_verify_token_wrong_salt(self):
        """Test verification fails with wrong salt."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )

        token_obj = generate_token(config, salt="test1234567890ab")
        wrong_salt = "wrong123456890ab"

        assert not verify_token(config, token_obj.token, wrong_salt)


class TestAuthParams:
    """Tests for authentication parameter creation."""

    def test_create_auth_params_default(self):
        """Test creating auth params with default values."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )

        token = generate_token(config, salt="abc123def456")
        params = create_auth_params(token)

        assert params["u"] == "testuser"
        assert params["t"] == token.token
        assert params["s"] == "abc123def456"
        assert params["v"] == "1.16.1"
        assert params["c"] == "playlistgen"
        assert params["f"] == "json"

    def test_create_auth_params_custom(self):
        """Test creating auth params with custom values."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
            client_name="custom-client",
            api_version="1.15.0",
        )

        token = generate_token(config, salt="abc123def456")
        params = create_auth_params(
            token,
            api_version="1.15.0",
            client_name="custom-client",
            response_format="xml",
        )

        assert params["v"] == "1.15.0"
        assert params["c"] == "custom-client"
        assert params["f"] == "xml"


class TestContractCompliance:
    """Tests for OpenAPI contract compliance (subsonic-auth.yaml)."""

    def test_token_format_matches_contract(self):
        """Test that token matches contract pattern: ^[a-f0-9]{32}$"""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="admin",
            password="sesame",
        )

        token = generate_token(config)

        # Contract requires lowercase hex, 32 chars
        assert re.match(r"^[a-f0-9]{32}$", token.token)

    def test_salt_length_within_contract_bounds(self):
        """Test that salt length is within contract bounds (6-36 chars)."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="admin",
            password="sesame",
        )

        token = generate_token(config)

        # Contract specifies minLength: 6, maxLength: 36
        assert 6 <= len(token.salt) <= 36

    def test_auth_params_contain_required_fields(self):
        """Test that auth params contain all required fields per contract."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="admin",
            password="sesame",
        )

        token = generate_token(config)
        params = create_auth_params(token)

        # All required query parameters per contract
        required_fields = ["u", "t", "s", "v", "c"]
        for field in required_fields:
            assert field in params

    def test_api_version_format(self):
        r"""Test that API version matches contract pattern: ^\d+\.\d+\.\d+$"""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="admin",
            password="sesame",
        )

        token = generate_token(config)
        params = create_auth_params(token)

        # Contract requires version pattern
        assert re.match(r"^\d+\.\d+\.\d+$", params["v"])

    def test_response_format_enum(self):
        """Test that response format is one of allowed values (json, xml)."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="admin",
            password="sesame",
        )

        token = generate_token(config)

        # Test both allowed values
        params_json = create_auth_params(token, response_format="json")
        assert params_json["f"] in ["json", "xml"]

        params_xml = create_auth_params(token, response_format="xml")
        assert params_xml["f"] in ["json", "xml"]


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_empty_password(self):
        """Test token generation with empty password."""
        # SubsonicConfig should raise ValueError for empty password
        with pytest.raises(ValueError, match="username and password are required"):
            SubsonicConfig(
                url="https://music.example.com",
                username="testuser",
                password="",
            )

    def test_empty_username(self):
        """Test token generation with empty username."""
        # SubsonicConfig should raise ValueError for empty username
        with pytest.raises(ValueError, match="username and password are required"):
            SubsonicConfig(
                url="https://music.example.com",
                username="",
                password="testpass",
            )

    def test_invalid_url(self):
        """Test config validation with invalid URL."""
        with pytest.raises(ValueError, match="url must be a valid HTTP/HTTPS URL"):
            SubsonicConfig(
                url="not-a-url",
                username="testuser",
                password="testpass",
            )

    def test_special_characters_in_password(self):
        """Test token generation with special characters in password."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="p@ssw0rd!#$%^&*()",
        )

        token = generate_token(config, salt="test1234567890ab")

        # Should generate valid token
        assert len(token.token) == 32
        assert verify_token(config, token.token, "test1234567890ab")

    def test_unicode_password(self):
        """Test token generation with unicode characters in password."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="pāsswörd™",
        )

        token = generate_token(config, salt="test1234567890ab")

        # Should generate valid token
        assert len(token.token) == 32
        assert verify_token(config, token.token, "test1234567890ab")


@pytest.mark.integration
class TestRealServerIntegration:
    """Integration tests against real Subsonic server.

    These tests require:
    - SUBSONIC_URL=https://music.mctk.co
    - SUBSONIC_USER (from .env)
    - SUBSONIC_PASSWORD (from .env)

    Run with: pytest -m integration tests/test_subsonic_auth.py
    """

    @pytest.fixture
    def real_config(self):
        """Create config from environment variables for real server testing."""
        import os

        # Try to load from .env file
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass

        url = os.getenv("SUBSONIC_URL", "https://music.mctk.co")
        username = os.getenv("SUBSONIC_USER") or os.getenv("SUBSONIC_USER")
        password = os.getenv("SUBSONIC_PASSWORD")

        if not username or not password:
            pytest.skip("SUBSONIC_USER and SUBSONIC_PASSWORD must be set")

        return SubsonicConfig(
            url=url,
            username=username,
            password=password,
        )

    def test_ping_endpoint_with_generated_token(self, real_config):
        """Test /ping endpoint with generated authentication token."""
        import requests

        token = generate_token(real_config)
        params = create_auth_params(token)

        # Make request to /rest/ping endpoint
        response = requests.get(
            f"{real_config.url}/rest/ping",
            params=params,
            timeout=10,
        )

        # Should return 200 OK with successful authentication
        assert response.status_code == 200

        # Response should have subsonic-response with status=ok
        data = response.json()
        assert "subsonic-response" in data
        assert data["subsonic-response"]["status"] == "ok"
        assert data["subsonic-response"]["version"] == "1.16.1"

    def test_authentication_with_wrong_password(self, real_config):
        """Test that wrong password returns authentication error."""
        import requests

        # Create config with wrong password
        wrong_config = SubsonicConfig(
            url=real_config.url,
            username=real_config.username,
            password="wrong_password",
        )

        token = generate_token(wrong_config)
        params = create_auth_params(token)

        response = requests.get(
            f"{wrong_config.url}/rest/ping",
            params=params,
            timeout=10,
        )

        # Should return error with code 40 (wrong username or password)
        data = response.json()
        assert data["subsonic-response"]["status"] == "failed"
        assert data["subsonic-response"]["error"]["code"] == 40

    def test_multiple_requests_with_different_tokens(self, real_config):
        """Test that multiple requests work with different tokens (unique salts)."""
        import requests

        # Make 3 requests with different tokens
        for _ in range(3):
            token = generate_token(real_config)
            params = create_auth_params(token)

            response = requests.get(
                f"{real_config.url}/rest/ping",
                params=params,
                timeout=10,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["subsonic-response"]["status"] == "ok"
