"""Contract tests for rate limiting (T033)."""
import pytest
from unittest.mock import Mock, patch
from src.azuracast.main import AzuraCastSync, BASE_BACKOFF, MAX_BACKOFF


class TestRateLimiting:
    """Test rate limiting behavior in AzuraCastSync._perform_request()."""

    @patch.dict('os.environ', {
        'AZURACAST_HOST': 'https://test.example.com',
        'AZURACAST_API_KEY': 'test-key',
        'AZURACAST_STATIONID': '1'
    })
    def test_handles_429_with_retry_after_header(self):
        """Test that 429 responses with Retry-After header are handled correctly."""
        client = AzuraCastSync()

        # Mock session to return 429 then 200
        with patch.object(client, '_get_session') as mock_get_session:
            mock_session = Mock()
            mock_response_429 = Mock()
            mock_response_429.status_code = 429
            mock_response_429.headers = {'Retry-After': '5'}

            mock_response_200 = Mock()
            mock_response_200.status_code = 200
            mock_response_200.json.return_value = {'success': True}

            mock_session.request.side_effect = [mock_response_429, mock_response_200]
            mock_get_session.return_value = mock_session

            with patch('time.sleep') as mock_sleep:
                response = client._perform_request('GET', '/test')

                # Should have slept for 5 seconds (Retry-After value)
                mock_sleep.assert_called_once_with(5)
                assert response.status_code == 200

    @patch.dict('os.environ', {
        'AZURACAST_HOST': 'https://test.example.com',
        'AZURACAST_API_KEY': 'test-key',
        'AZURACAST_STATIONID': '1'
    })
    def test_handles_429_without_retry_after_uses_exponential_backoff(self):
        """Test that 429 responses without Retry-After use exponential backoff."""
        client = AzuraCastSync()

        with patch.object(client, '_get_session') as mock_get_session:
            mock_session = Mock()
            mock_response_429 = Mock()
            mock_response_429.status_code = 429
            mock_response_429.headers = {}  # No Retry-After header

            mock_response_200 = Mock()
            mock_response_200.status_code = 200
            mock_response_200.json.return_value = {'success': True}

            # Return 429 twice, then 200
            mock_session.request.side_effect = [mock_response_429, mock_response_429, mock_response_200]
            mock_get_session.return_value = mock_session

            with patch('time.sleep') as mock_sleep:
                response = client._perform_request('GET', '/test')

                # Should have used exponential backoff (BASE_BACKOFF * 2^attempt)
                # Attempt 1: 2 * 2^1 = 4
                # Attempt 2: 2 * 2^2 = 8
                assert mock_sleep.call_count == 2
                # First backoff should be 4s (attempt 1)
                assert mock_sleep.call_args_list[0][0][0] == min(BASE_BACKOFF * (2 ** 1), MAX_BACKOFF)

    @patch.dict('os.environ', {
        'AZURACAST_HOST': 'https://test.example.com',
        'AZURACAST_API_KEY': 'test-key',
        'AZURACAST_STATIONID': '1'
    })
    def test_exponential_backoff_caps_at_max(self):
        """Test that exponential backoff caps at MAX_BACKOFF."""
        client = AzuraCastSync()

        with patch.object(client, '_get_session') as mock_get_session:
            mock_session = Mock()
            mock_response_429 = Mock()
            mock_response_429.status_code = 429
            mock_response_429.headers = {}

            # Create enough 429s to hit MAX_BACKOFF
            # BASE_BACKOFF=2, MAX_BACKOFF=64
            # 2 * 2^5 = 64, 2 * 2^6 = 128 > 64
            # Use 5 attempts (429 responses) then success
            responses = [mock_response_429] * 5
            mock_response_200 = Mock()
            mock_response_200.status_code = 200
            responses.append(mock_response_200)

            mock_session.request.side_effect = responses
            mock_get_session.return_value = mock_session

            with patch('time.sleep') as mock_sleep:
                response = client._perform_request('GET', '/test')

                # Last backoff should be capped at MAX_BACKOFF (64s)
                # Attempt 5: 2 * 2^5 = 64
                # Attempt 6: 2 * 2^6 = 128, capped at 64
                last_sleep_value = mock_sleep.call_args_list[-1][0][0]
                assert last_sleep_value == MAX_BACKOFF

    @patch.dict('os.environ', {
        'AZURACAST_HOST': 'https://test.example.com',
        'AZURACAST_API_KEY': 'test-key',
        'AZURACAST_STATIONID': '1'
    })
    def test_invalid_retry_after_falls_back_to_exponential(self):
        """Test that invalid Retry-After values fall back to exponential backoff."""
        client = AzuraCastSync()

        with patch.object(client, '_get_session') as mock_get_session:
            mock_session = Mock()
            mock_response_429 = Mock()
            mock_response_429.status_code = 429
            mock_response_429.headers = {'Retry-After': 'invalid'}  # Non-integer value

            mock_response_200 = Mock()
            mock_response_200.status_code = 200

            mock_session.request.side_effect = [mock_response_429, mock_response_200]
            mock_get_session.return_value = mock_session

            with patch('time.sleep') as mock_sleep:
                response = client._perform_request('GET', '/test')

                # Should fall back to exponential backoff
                expected_backoff = min(BASE_BACKOFF * (2 ** 1), MAX_BACKOFF)
                mock_sleep.assert_called_once_with(expected_backoff)
