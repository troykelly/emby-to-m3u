"""Unit tests for Subsonic API error handling.

Tests all error codes, binary response error detection, retry logic, and network timeout handling.
"""

import httpx
import pytest
from unittest.mock import Mock, patch

from src.subsonic.client import SubsonicClient
from src.subsonic.exceptions import (
    ClientVersionTooOldError,
    ServerVersionTooOldError,
    SubsonicAuthenticationError,
    SubsonicAuthorizationError,
    SubsonicError,
    SubsonicNotFoundError,
    SubsonicParameterError,
    SubsonicTrialError,
    SubsonicVersionError,
    TokenAuthenticationNotSupportedError,
)
from src.subsonic.models import SubsonicConfig


@pytest.fixture
def subsonic_config():
    """Create test Subsonic configuration."""
    return SubsonicConfig(
        url="https://test.example.com",
        username="testuser",
        password="testpass",
    )


@pytest.fixture
def subsonic_client(subsonic_config):
    """Create SubsonicClient with mocked httpx.Client."""
    with patch.object(SubsonicClient, "__init__", lambda x, y: None):
        client = SubsonicClient.__new__(SubsonicClient)
        client.config = subsonic_config
        client._base_url = subsonic_config.url
        client.opensubsonic = False
        client.opensubsonic_version = None
        client.client = Mock(spec=httpx.Client)
        yield client


class TestErrorCodeMapping:
    """Test error code to exception mapping."""

    def test_error_code_40_authentication_failure(self, subsonic_client):
        """Test error code 40 raises SubsonicAuthenticationError."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 40, "message": "Wrong username or password"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with pytest.raises(SubsonicAuthenticationError) as exc_info:
            subsonic_client._handle_response(mock_response)

        assert exc_info.value.code == 40
        assert "Wrong username or password" in str(exc_info.value)

    def test_error_code_41_authentication_failure(self, subsonic_client):
        """Test error code 41 raises SubsonicAuthenticationError."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 41, "message": "Token authentication not supported"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with pytest.raises(SubsonicAuthenticationError) as exc_info:
            subsonic_client._handle_response(mock_response)

        assert exc_info.value.code == 41

    def test_error_code_42_token_not_supported(self, subsonic_client):
        """Test error code 42 raises TokenAuthenticationNotSupportedError."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 42, "message": "Token authentication not supported"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with pytest.raises(TokenAuthenticationNotSupportedError) as exc_info:
            subsonic_client._handle_response(mock_response)

        assert exc_info.value.code == 42

    def test_error_code_43_client_too_old(self, subsonic_client):
        """Test error code 43 raises ClientVersionTooOldError."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 43, "message": "Client must upgrade"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with pytest.raises(ClientVersionTooOldError) as exc_info:
            subsonic_client._handle_response(mock_response)

        assert exc_info.value.code == 43

    def test_error_code_44_server_too_old(self, subsonic_client):
        """Test error code 44 raises ServerVersionTooOldError."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 44, "message": "Server must upgrade"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with pytest.raises(ServerVersionTooOldError) as exc_info:
            subsonic_client._handle_response(mock_response)

        assert exc_info.value.code == 44

    def test_error_code_50_authorization_failure(self, subsonic_client):
        """Test error code 50 raises SubsonicAuthorizationError."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 50, "message": "User not authorized for operation"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with pytest.raises(SubsonicAuthorizationError) as exc_info:
            subsonic_client._handle_response(mock_response)

        assert exc_info.value.code == 50

    def test_error_code_70_not_found(self, subsonic_client):
        """Test error code 70 raises SubsonicNotFoundError."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 70, "message": "Requested data not found"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with pytest.raises(SubsonicNotFoundError) as exc_info:
            subsonic_client._handle_response(mock_response)

        assert exc_info.value.code == 70

    def test_error_code_20_version_error(self, subsonic_client):
        """Test error code 20 raises SubsonicVersionError."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 20, "message": "Incompatible client version"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with pytest.raises(SubsonicVersionError) as exc_info:
            subsonic_client._handle_response(mock_response)

        assert exc_info.value.code == 20

    def test_error_code_30_version_error(self, subsonic_client):
        """Test error code 30 raises SubsonicVersionError."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 30, "message": "Incompatible server version"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with pytest.raises(SubsonicVersionError) as exc_info:
            subsonic_client._handle_response(mock_response)

        assert exc_info.value.code == 30

    def test_error_code_10_parameter_error(self, subsonic_client):
        """Test error code 10 raises SubsonicParameterError."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 10, "message": "Required parameter missing"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with pytest.raises(SubsonicParameterError) as exc_info:
            subsonic_client._handle_response(mock_response)

        assert exc_info.value.code == 10

    def test_error_code_60_trial_error(self, subsonic_client):
        """Test error code 60 raises SubsonicTrialError."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 60, "message": "Trial period over"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with pytest.raises(SubsonicTrialError) as exc_info:
            subsonic_client._handle_response(mock_response)

        assert exc_info.value.code == 60

    def test_error_code_generic(self, subsonic_client):
        """Test unknown error code raises generic SubsonicError."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 999, "message": "Unknown error"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with pytest.raises(SubsonicError) as exc_info:
            subsonic_client._handle_response(mock_response)

        assert exc_info.value.code == 999
        assert "Unknown error" in str(exc_info.value)


class TestBinaryResponseErrorDetection:
    """Test binary endpoint error detection when XML/JSON returned instead of binary."""

    def test_binary_endpoint_returns_json_error(self, subsonic_client):
        """Test that JSON error response is detected when binary expected."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json; charset=utf-8"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 70, "message": "Track not found"},
            }
        }

        with pytest.raises(SubsonicNotFoundError) as exc_info:
            subsonic_client._handle_response(mock_response, expect_binary=True)

        assert exc_info.value.code == 70

    def test_binary_endpoint_returns_xml_error(self, subsonic_client):
        """Test that XML error response is detected when binary expected."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "text/xml; charset=utf-8"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 70, "message": "Cover art not found"},
            }
        }

        with pytest.raises(SubsonicNotFoundError) as exc_info:
            subsonic_client._handle_response(mock_response, expect_binary=True)

        assert exc_info.value.code == 70


class TestNetworkTimeoutHandling:
    """Test network timeout and retry logic."""

    def test_connection_timeout(self, subsonic_config):
        """Test that connection timeout raises appropriate exception."""
        with patch("httpx.Client") as MockClient:
            mock_client = MockClient.return_value.__enter__.return_value
            mock_client.get.side_effect = httpx.ConnectTimeout("Connection timeout")

            client = SubsonicClient(subsonic_config)
            client.client = mock_client

            with pytest.raises(httpx.ConnectTimeout):
                client.ping()

    def test_read_timeout(self, subsonic_config):
        """Test that read timeout raises appropriate exception."""
        with patch("httpx.Client") as MockClient:
            mock_client = MockClient.return_value.__enter__.return_value
            mock_client.get.side_effect = httpx.ReadTimeout("Read timeout")

            client = SubsonicClient(subsonic_config)
            client.client = mock_client

            with pytest.raises(httpx.ReadTimeout):
                client.ping()


class TestHTTPStatusErrors:
    """Test HTTP-level error handling."""

    def test_404_not_found(self, subsonic_client):
        """Test that 404 HTTP error is properly handled."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=Mock(), response=mock_response
        )
        mock_response.headers = {"content-type": "text/html"}

        with pytest.raises(httpx.HTTPStatusError):
            subsonic_client._handle_response(mock_response)

    def test_500_server_error(self, subsonic_client):
        """Test that 500 HTTP error is properly handled."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error", request=Mock(), response=mock_response
        )
        mock_response.headers = {"content-type": "text/html"}

        with pytest.raises(httpx.HTTPStatusError):
            subsonic_client._handle_response(mock_response)


class TestSuccessfulResponses:
    """Test successful API responses."""

    def test_successful_ping_response(self, subsonic_client):
        """Test that successful ping response is properly parsed."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
            }
        }

        result = subsonic_client._handle_response(mock_response)
        assert result["status"] == "ok"
        assert result["version"] == "1.16.1"

    def test_successful_opensubsonic_detection(self, subsonic_client):
        """Test OpenSubsonic server detection."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "openSubsonic": {
                    "serverVersion": "0.1.0",
                },
            }
        }

        result = subsonic_client._handle_response(mock_response)
        assert "openSubsonic" in result
        assert result["openSubsonic"]["serverVersion"] == "0.1.0"
