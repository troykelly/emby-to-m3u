"""Coverage tests for azuracast/playlist_sync.py missing lines.

Specifically targets lines 261-263: exception handling in _configure_schedule.
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime
from decimal import Decimal
import uuid
import httpx

from src.ai_playlist.azuracast.playlist_sync import AzuraCastPlaylistSync
from src.ai_playlist.models.core import Playlist, SelectedTrack, ValidationStatus


@pytest.fixture
def sync_client():
    """Create test sync client."""
    return AzuraCastPlaylistSync(
        host="https://test.azuracast.com",
        api_key="test_key",
        station_id="1"
    )


@pytest.fixture
def test_playlist():
    """Create test playlist."""
    tracks = [
        SelectedTrack(
            track_id="t1",
            title="Song",
            artist="Artist",
            album="Album",
            duration_seconds=180,
            is_australian=True,
            rotation_category="Power",
            position_in_playlist=0,
            selection_reasoning="test",
            validation_status=ValidationStatus.PASS,
            metadata_source="test",
            bpm=120,
            genre="Rock",
            year=2023,
            country="AU"
        )
    ]

    return Playlist(
        id=str(uuid.uuid4()),
        name="TestPlaylist",
        specification_id=str(uuid.uuid4()),
        tracks=tracks,
        validation_result=None,
        created_at=datetime.now(),
        cost_actual=Decimal("0.10"),
        generation_time_seconds=1.0
    )


class TestScheduleConfigurationExceptions:
    """Test exception handling in _configure_schedule (lines 261-263)."""

    @pytest.mark.asyncio
    async def test_schedule_config_exception_handled_gracefully(
        self, sync_client, test_playlist, tmp_path
    ):
        """Test that exceptions in _configure_schedule are caught and logged (lines 261-263)."""
        m3u_file = tmp_path / "test.m3u"
        m3u_file.write_text("#EXTM3U\n")

        schedule = {
            "start_time": "06:00",
            "end_time": "10:00",
            "days": [1, 2, 3, 4, 5]
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client

            # Mock successful playlist creation
            mock_client.get.return_value = AsyncMock(
                status_code=200,
                json=Mock(return_value=[])
            )
            mock_client.post.return_value = AsyncMock(
                status_code=201,
                json=Mock(return_value={"id": "123"})
            )

            # Mock schedule configuration to raise exception (triggers lines 261-263)
            mock_client.put.side_effect = httpx.HTTPError("Schedule config failed")

            # Act
            result = await sync_client.sync_playlist(
                playlist=test_playlist,
                m3u_path=m3u_file,
                schedule=schedule,
                dry_run=False
            )

            # Assert - sync should continue despite schedule failure
            assert result.playlist_id == "123"
            assert result.schedule_configured is False  # Schedule failed
            # But sync overall doesn't fail completely

    @pytest.mark.asyncio
    async def test_schedule_config_http_status_error(
        self, sync_client, test_playlist, tmp_path
    ):
        """Test HTTPStatusError in schedule config is caught (lines 261-263)."""
        m3u_file = tmp_path / "test.m3u"
        m3u_file.write_text("#EXTM3U\n")

        schedule = {"start_time": "06:00"}

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client

            mock_client.get.return_value = AsyncMock(
                status_code=200,
                json=Mock(return_value=[])
            )
            mock_client.post.return_value = AsyncMock(
                status_code=201,
                json=Mock(return_value={"id": "456"})
            )

            # Schedule config returns HTTP error
            error_response = Mock(status_code=500)
            mock_client.put.return_value = AsyncMock(
                status_code=500,
                raise_for_status=Mock(
                    side_effect=httpx.HTTPStatusError(
                        "Server error",
                        request=Mock(),
                        response=error_response
                    )
                )
            )

            # Act
            result = await sync_client.sync_playlist(
                playlist=test_playlist,
                m3u_path=m3u_file,
                schedule=schedule
            )

            # Assert - exception caught, sync continues
            assert result.playlist_id == "456"
            assert result.schedule_configured is False

    @pytest.mark.asyncio
    async def test_schedule_config_generic_exception(
        self, sync_client, test_playlist, tmp_path
    ):
        """Test generic Exception in schedule config (lines 261-263)."""
        m3u_file = tmp_path / "test.m3u"
        m3u_file.write_text("#EXTM3U\n")

        schedule = {"start_time": "06:00"}

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client

            mock_client.get.return_value = AsyncMock(
                status_code=200,
                json=Mock(return_value=[])
            )
            mock_client.post.return_value = AsyncMock(
                status_code=201,
                json=Mock(return_value={"id": "789"})
            )

            # Schedule config raises unexpected exception
            mock_client.put.side_effect = ValueError("Unexpected error")

            # Act
            result = await sync_client.sync_playlist(
                playlist=test_playlist,
                m3u_path=m3u_file,
                schedule=schedule
            )

            # Assert
            assert result.playlist_id == "789"
            assert result.schedule_configured is False
