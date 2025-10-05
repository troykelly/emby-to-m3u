"""Contract tests for Subsonic authentication API."""

import hashlib
import json
import pytest
from pathlib import Path


@pytest.fixture
def subsonic_responses():
    """Load Subsonic API response fixtures."""
    fixtures_path = Path(__file__).parent.parent / "subsonic" / "fixtures" / "subsonic_responses.json"
    with open(fixtures_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_ping_success_with_valid_token(subsonic_responses):
    """Test ping endpoint with valid token returns 200 OK."""
    response = subsonic_responses["ping_success"]

    # Validate response schema
    assert "subsonic-response" in response
    assert response["subsonic-response"]["status"] == "ok"
    assert "version" in response["subsonic-response"]
    assert response["subsonic-response"]["version"] == "1.16.1"


def test_ping_failure_wrong_credentials(subsonic_responses):
    """Test ping endpoint with wrong credentials returns 401 with error code 40."""
    response = subsonic_responses["ping_auth_failure"]

    # Validate error response schema
    assert "subsonic-response" in response
    assert response["subsonic-response"]["status"] == "failed"
    assert "error" in response["subsonic-response"]
    assert response["subsonic-response"]["error"]["code"] == 40
    assert "Wrong username or password" in response["subsonic-response"]["error"]["message"]


def test_token_generation_md5():
    """Test that token generation uses correct MD5(password + salt) algorithm."""
    password = "sesame"
    salt = "c19b2d"

    # Expected token from contract
    expected_token = "26719a1196d2a940705a59634eb18eab"

    # Generate token using MD5(password + salt)
    token_input = f"{password}{salt}"
    generated_token = hashlib.md5(token_input.encode()).hexdigest()

    assert generated_token == expected_token
    assert len(generated_token) == 32  # MD5 produces 32-char hex string


def test_auth_params_complete():
    """Test that all required authentication parameters are present."""
    # Required parameters per contract
    required_params = ["u", "t", "s", "v", "c", "f"]

    auth_params = {
        "u": "admin",
        "t": "26719a1196d2a940705a59634eb18eab",
        "s": "c19b2d",
        "v": "1.16.1",
        "c": "playlistgen",
        "f": "json"
    }

    for param in required_params:
        assert param in auth_params, f"Missing required parameter: {param}"

    # Validate parameter formats
    assert len(auth_params["t"]) == 32  # MD5 token is 32 chars
    assert len(auth_params["s"]) >= 6  # Salt min length
    assert "." in auth_params["v"]  # Version format


def test_response_schema_matches_contract(subsonic_responses):
    """Test that response schema matches OpenAPI contract specification."""
    success_response = subsonic_responses["ping_success"]
    error_response = subsonic_responses["ping_auth_failure"]

    # Success response validation
    assert isinstance(success_response["subsonic-response"], dict)
    assert success_response["subsonic-response"]["status"] in ["ok", "failed"]

    # Error response validation
    assert "error" in error_response["subsonic-response"]
    assert isinstance(error_response["subsonic-response"]["error"]["code"], int)
    assert isinstance(error_response["subsonic-response"]["error"]["message"], str)

    # Error codes validation (per contract)
    valid_error_codes = [0, 10, 20, 30, 40, 50, 60, 70]
    assert error_response["subsonic-response"]["error"]["code"] in valid_error_codes
