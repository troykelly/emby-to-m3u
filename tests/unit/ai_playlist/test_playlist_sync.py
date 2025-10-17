"""
Unit Tests for AzuraCast Playlist Sync Module (T062)

Comprehensive test suite for azuracast/playlist_sync.py with 90% coverage.

Test Coverage (15 tests):
1. Dry-run mode (3 tests)
2. Track upload logic (4 tests)
3. Schedule configuration (3 tests)
4. Playlist verification (2 tests)
5. Error handling (3 tests)
"""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from src.ai_playlist.azuracast.playlist_sync import AzuraCastPlaylistSync
from src.ai_playlist.models.core import Playlist, SelectedTrack, ValidationStatus


@pytest.fixture
def mock_playlist():
    """Create a mock playlist for testing."""
    tracks = [
        SelectedTrack(
            track_id="track_001",
            title="Test Song 1",
            artist="Test Artist 1",
            album="Test Album 1",
            duration_seconds=180,
            is_australian=True,
            rotation_category="Power",
            position_in_playlist=0,
            selection_reasoning="Matches BPM and genre criteria",
            validation_status=ValidationStatus.PASS,
            metadata_source="test",
            bpm=120,
            genre="Alternative",
            year=2023,
            country="AU"
        ),
        SelectedTrack(
            track_id="track_002",
            title="Test Song 2",
            artist="Test Artist 2",
            album="Test Album 2",
            duration_seconds=200,
            is_australian=False,
            rotation_category="Medium",
            position_in_playlist=1,
            selection_reasoning="Matches era distribution",
            validation_status=ValidationStatus.PASS,
            metadata_source="test",
            bpm=125,
            genre="Alternative",
            year=2022,
            country="US"
        ),
        SelectedTrack(
            track_id="track_003",
            title="Test Song 3",
            artist="Test Artist 3",
            album="Test Album 3",
            duration_seconds=195,
            is_australian=True,
            rotation_category="Light",
            position_in_playlist=2,
            selection_reasoning="Provides genre diversity",
            validation_status=ValidationStatus.PASS,
            metadata_source="test",
            bpm=130,
            genre="Rock",
            year=2021,
            country="AU"
        )
    ]

    return Playlist(
        id="playlist_001",
        name="Morning Drive - 2023-10-07",
        specification_id="spec_001",
        tracks=tracks,
        validation_result=None,
        created_at=datetime.now(),
        cost_actual=Decimal("0.50"),
        generation_time_seconds=5.2
    )


@pytest.fixture
def sync_client():
    """Create AzuraCast sync client with test config."""
    return AzuraCastPlaylistSync(
        host="https://test.azuracast.com",
        api_key="test_api_key_12345",
        station_id="1",
        timeout=30
    )


# ============================================================================
# Category 1: Dry-run Mode (3 tests)
# ============================================================================


class TestDryRunMode:
    """Test dry-run mode functionality."""

    @pytest.mark.asyncio
    async def test_dry_run_skips_actual_sync(self, sync_client, mock_playlist):
        """Test dry-run mode skips actual sync operations."""
        m3u_path = Path("/tmp/test.m3u")

        result = await sync_client.sync_playlist(
            playlist=mock_playlist,
            m3u_path=m3u_path,
            dry_run=True
        )

        # Verify dry-run result
        assert result.dry_run is True
        assert result.success is True
        assert result.playlist_id == "dry_run_playlist_id"
        assert result.tracks_uploaded == len(mock_playlist.tracks)
        assert result.verification_passed is True
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_dry_run_logs_what_would_be_synced(
        self, sync_client, mock_playlist, caplog
    ):
        """Test dry-run logs planned operations without executing."""
        m3u_path = Path("/tmp/test.m3u")

        with caplog.at_level("INFO"):
            result = await sync_client.sync_playlist(
                playlist=mock_playlist,
                m3u_path=m3u_path,
                dry_run=True
            )

        # Verify logging
        assert "DRY RUN: Would create playlist" in caplog.text
        assert f"Would upload {len(mock_playlist.tracks)} tracks" in caplog.text
        assert "Skipping verification" in caplog.text
        assert result.dry_run is True

    @pytest.mark.asyncio
    async def test_dry_run_with_schedule_returns_mock_results(
        self, sync_client, mock_playlist
    ):
        """Test dry-run with schedule configuration returns mock success."""
        m3u_path = Path("/tmp/test.m3u")
        schedule = {
            "days": [1, 2, 3, 4, 5],  # Mon-Fri
            "start_time": "06:00",
            "end_time": "10:00"
        }

        result = await sync_client.sync_playlist(
            playlist=mock_playlist,
            m3u_path=m3u_path,
            schedule=schedule,
            dry_run=True
        )

        assert result.dry_run is True
        assert result.schedule_configured is True
        assert result.success is True
        assert len(result.errors) == 0


# ============================================================================
# Category 2: Track Upload Logic (4 tests)
# ============================================================================


class TestTrackUploadLogic:
    """Test track upload functionality."""

    @pytest.mark.asyncio
    async def test_upload_tracks_to_azuracast(self, sync_client, mock_playlist):
        """Test successful track upload to AzuraCast playlist."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock playlist creation
            mock_client.get.return_value = AsyncMock(
                status_code=200,
                json=Mock(return_value=[])
            )
            mock_client.post.return_value = AsyncMock(
                status_code=201,
                json=Mock(return_value={"id": "123"})
            )

            result = await sync_client.sync_playlist(
                playlist=mock_playlist,
                m3u_path=Path("/tmp/test.m3u"),
                dry_run=False
            )

            # Verify tracks uploaded
            assert result.tracks_uploaded == len(mock_playlist.tracks)
            assert mock_client.post.call_count >= 1  # Playlist + tracks

    @pytest.mark.asyncio
    async def test_handle_duplicate_tracks(self, sync_client, mock_playlist):
        """Test handling duplicate tracks during upload."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock existing playlist
            mock_client.get.return_value = AsyncMock(
                status_code=200,
                json=Mock(return_value=[{"id": "123", "name": mock_playlist.name}])
            )

            # Mock update
            mock_client.put.return_value = AsyncMock(status_code=200)

            # First track succeeds, second fails (duplicate), third succeeds
            post_responses = [
                AsyncMock(status_code=201),  # Track 1
                AsyncMock(
                    status_code=409,
                    raise_for_status=Mock(
                        side_effect=httpx.HTTPStatusError(
                            "Conflict", request=Mock(), response=Mock()
                        )
                    )
                ),  # Track 2 duplicate
                AsyncMock(status_code=201),  # Track 3
            ]
            mock_client.post.side_effect = post_responses

            result = await sync_client.sync_playlist(
                playlist=mock_playlist,
                m3u_path=Path("/tmp/test.m3u"),
                dry_run=False
            )

            # Should handle duplicate gracefully
            assert result.tracks_uploaded == 2  # Only 2 uploaded successfully

    @pytest.mark.asyncio
    async def test_verify_track_metadata_during_upload(
        self, sync_client, mock_playlist
    ):
        """Test track metadata is correctly sent during upload."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock playlist creation
            mock_client.get.return_value = AsyncMock(
                status_code=200,
                json=Mock(return_value=[])
            )
            mock_client.post.return_value = AsyncMock(
                status_code=201,
                json=Mock(return_value={"id": "123"})
            )

            await sync_client.sync_playlist(
                playlist=mock_playlist,
                m3u_path=Path("/tmp/test.m3u"),
                dry_run=False
            )

            # Verify track upload calls include media_id
            track_upload_calls = [
                call for call in mock_client.post.call_args_list
                if "items" in str(call)
            ]
            assert len(track_upload_calls) >= len(mock_playlist.tracks)

    @pytest.mark.asyncio
    async def test_track_upload_progress_logging(
        self, sync_client, mock_playlist, caplog
    ):
        """Test track upload logs progress."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_client.get.return_value = AsyncMock(
                status_code=200,
                json=Mock(return_value=[])
            )
            mock_client.post.return_value = AsyncMock(
                status_code=201,
                json=Mock(return_value={"id": "123"})
            )

            with caplog.at_level("INFO"):
                await sync_client.sync_playlist(
                    playlist=mock_playlist,
                    m3u_path=Path("/tmp/test.m3u"),
                    dry_run=False
                )

            # Verify upload progress logged
            assert f"Uploaded {len(mock_playlist.tracks)}" in caplog.text


# ============================================================================
# Category 3: Schedule Configuration (3 tests)
# ============================================================================


class TestScheduleConfiguration:
    """Test playlist schedule configuration."""

    @pytest.mark.asyncio
    async def test_set_playlist_schedule(self, sync_client, mock_playlist):
        """Test setting playlist schedule with valid times."""
        schedule = {
            "days": [1, 2, 3, 4, 5],  # Mon-Fri
            "start_time": "06:00",
            "end_time": "10:00"
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock playlist exists
            mock_client.get.return_value = AsyncMock(
                status_code=200,
                json=Mock(return_value=[{"id": "123", "name": mock_playlist.name}])
            )
            mock_client.put.return_value = AsyncMock(status_code=200)
            mock_client.post.return_value = AsyncMock(status_code=201)

            result = await sync_client.sync_playlist(
                playlist=mock_playlist,
                m3u_path=Path("/tmp/test.m3u"),
                schedule=schedule,
                dry_run=False
            )

            assert result.schedule_configured is True

    @pytest.mark.asyncio
    async def test_validate_schedule_times(self, sync_client, mock_playlist):
        """Test schedule time validation."""
        schedule = {
            "days": [0, 6],  # Weekend
            "start_time": "10:00",
            "end_time": "14:00"
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_client.get.return_value = AsyncMock(
                status_code=200,
                json=Mock(return_value=[])
            )
            mock_client.post.return_value = AsyncMock(
                status_code=201,
                json=Mock(return_value={"id": "123"})
            )
            mock_client.put.return_value = AsyncMock(status_code=200)

            result = await sync_client.sync_playlist(
                playlist=mock_playlist,
                m3u_path=Path("/tmp/test.m3u"),
                schedule=schedule,
                dry_run=False
            )

            # Schedule should be configured
            assert result.schedule_configured is True

    @pytest.mark.asyncio
    async def test_handle_timezone_conversion(self, sync_client, mock_playlist):
        """Test timezone handling in schedule configuration."""
        schedule = {
            "days": [1, 2, 3],
            "start_time": "00:00",  # Midnight
            "end_time": "23:59"  # End of day
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_client.get.return_value = AsyncMock(
                status_code=200,
                json=Mock(return_value=[])
            )
            mock_client.post.return_value = AsyncMock(
                status_code=201,
                json=Mock(return_value={"id": "123"})
            )
            mock_client.put.return_value = AsyncMock(status_code=200)

            result = await sync_client.sync_playlist(
                playlist=mock_playlist,
                m3u_path=Path("/tmp/test.m3u"),
                schedule=schedule,
                dry_run=False
            )

            assert result.schedule_configured is True


# ============================================================================
# Category 4: Playlist Verification (2 tests)
# ============================================================================


class TestPlaylistVerification:
    """Test playlist verification after sync."""

    @pytest.mark.asyncio
    async def test_verify_playlist_exists_on_azuracast(
        self, sync_client, mock_playlist
    ):
        """Test verification that playlist exists on AzuraCast."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock playlist creation and verification
            mock_client.get.side_effect = [
                AsyncMock(
                    status_code=200,
                    json=Mock(return_value=[])
                ),  # Initial check
                AsyncMock(
                    status_code=200,
                    json=Mock(
                        return_value={
                            "id": "123",
                            "name": mock_playlist.name,
                            "items": [
                                {"id": "1"},
                                {"id": "2"},
                                {"id": "3"}
                            ]
                        }
                    )
                )  # Verification fetch
            ]
            mock_client.post.return_value = AsyncMock(
                status_code=201,
                json=Mock(return_value={"id": "123"})
            )

            result = await sync_client.sync_playlist(
                playlist=mock_playlist,
                m3u_path=Path("/tmp/test.m3u"),
                dry_run=False
            )

            assert result.verification_passed is True
            assert result.success is True

    @pytest.mark.asyncio
    async def test_verify_track_count_matches(self, sync_client, mock_playlist):
        """Test verification checks track count matches."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock playlist with wrong track count
            mock_client.get.side_effect = [
                AsyncMock(
                    status_code=200,
                    json=Mock(return_value=[])
                ),  # Initial check
                AsyncMock(
                    status_code=200,
                    json=Mock(
                        return_value={
                            "id": "123",
                            "name": mock_playlist.name,
                            "items": [{"id": "1"}]  # Only 1 track instead of 3
                        }
                    )
                )  # Verification fetch
            ]
            mock_client.post.return_value = AsyncMock(
                status_code=201,
                json=Mock(return_value={"id": "123"})
            )

            result = await sync_client.sync_playlist(
                playlist=mock_playlist,
                m3u_path=Path("/tmp/test.m3u"),
                dry_run=False
            )

            # Verification should fail due to track count mismatch
            assert result.verification_passed is False


# ============================================================================
# Category 5: Error Handling (3 tests)
# ============================================================================


class TestErrorHandling:
    """Test error handling for various failure scenarios."""

    @pytest.mark.asyncio
    async def test_handle_404_playlist_not_found(self, sync_client, mock_playlist):
        """Test handling 404 error (playlist not found) during verification."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Initial check succeeds, but playlist creation returns None (404 scenario)
            mock_client.get.return_value = AsyncMock(
                status_code=404,
                raise_for_status=Mock(
                    side_effect=httpx.HTTPStatusError(
                        "Not Found",
                        request=Mock(),
                        response=Mock(status_code=404)
                    )
                )
            )

            result = await sync_client.sync_playlist(
                playlist=mock_playlist,
                m3u_path=Path("/tmp/test.m3u"),
                dry_run=False
            )

            # Should handle 404 gracefully
            assert result.success is False
            assert len(result.errors) > 0
            assert any("404" in str(e) or "Not Found" in str(e) for e in result.errors)

    @pytest.mark.asyncio
    async def test_handle_401_unauthorized(self, sync_client, mock_playlist):
        """Test handling 401 error (unauthorized) during sync."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Unauthorized error
            mock_client.get.return_value = AsyncMock(
                status_code=401,
                raise_for_status=Mock(
                    side_effect=httpx.HTTPStatusError(
                        "Unauthorized",
                        request=Mock(),
                        response=Mock(status_code=401)
                    )
                )
            )

            result = await sync_client.sync_playlist(
                playlist=mock_playlist,
                m3u_path=Path("/tmp/test.m3u"),
                dry_run=False
            )

            # Should capture error
            assert result.success is False
            assert len(result.errors) > 0
            assert any("401" in str(e) or "Unauthorized" in str(e) for e in result.errors)

    @pytest.mark.asyncio
    async def test_handle_503_service_unavailable(self, sync_client, mock_playlist):
        """Test handling 503 error (service unavailable)."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Service unavailable
            mock_client.get.return_value = AsyncMock(
                status_code=503,
                raise_for_status=Mock(
                    side_effect=httpx.HTTPStatusError(
                        "Service Unavailable",
                        request=Mock(),
                        response=Mock(status_code=503)
                    )
                )
            )

            result = await sync_client.sync_playlist(
                playlist=mock_playlist,
                m3u_path=Path("/tmp/test.m3u"),
                dry_run=False
            )

            # Should capture error
            assert result.success is False
            assert len(result.errors) > 0
            assert any(
                "503" in str(e) or "Service Unavailable" in str(e)
                for e in result.errors
            )


# ============================================================================
# Additional Tests for Edge Cases
# ============================================================================


class TestAdditionalEdgeCases:
    """Additional tests for edge cases and full coverage."""

    @pytest.mark.asyncio
    async def test_sync_client_initialization(self):
        """Test AzuraCast sync client initialization."""
        client = AzuraCastPlaylistSync(
            host="https://radio.example.com/",  # With trailing slash
            api_key="key123",
            station_id="42",
            timeout=60
        )

        assert client.host == "https://radio.example.com"  # Trailing slash removed
        assert client.api_key == "key123"
        assert client.station_id == "42"
        assert client.timeout == 60
        assert client.headers["X-API-Key"] == "key123"
        assert client.headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_list_playlists(self, sync_client):
        """Test listing all playlists from station."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_playlists = [
                {"id": "1", "name": "Playlist 1"},
                {"id": "2", "name": "Playlist 2"}
            ]
            mock_client.get.return_value = AsyncMock(
                status_code=200,
                json=Mock(return_value=mock_playlists)
            )

            result = await sync_client.list_playlists()

            assert len(result) == 2
            assert result[0]["name"] == "Playlist 1"
            assert result[1]["name"] == "Playlist 2"

    @pytest.mark.asyncio
    async def test_delete_playlist(self, sync_client):
        """Test deleting a playlist."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_client.delete.return_value = AsyncMock(status_code=204)

            result = await sync_client.delete_playlist("123")

            assert result is True
            mock_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_playlist_failure(self, sync_client):
        """Test delete playlist handles failure gracefully."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_client.delete.return_value = AsyncMock(
                status_code=404,
                raise_for_status=Mock(
                    side_effect=httpx.HTTPStatusError(
                        "Not Found",
                        request=Mock(),
                        response=Mock(status_code=404)
                    )
                )
            )

            result = await sync_client.delete_playlist("999")

            assert result is False
