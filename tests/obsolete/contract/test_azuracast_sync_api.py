"""
Contract tests for AzuraCast Sync API (OpenAPI Specification Validation)

Tests validate API contracts against azuracast-sync-api.yaml specification.
These tests MUST FAIL initially - no implementation exists yet (TDD RED phase).

FR-016: AzuraCast playlist sync with dry-run support
"""

import pytest
from typing import Dict, Any
import yaml
from pathlib import Path


SPEC_PATH = Path("/workspaces/emby-to-m3u/specs/005-refactor-core-playlist/contracts/azuracast-sync-api.yaml")


@pytest.fixture
def openapi_spec():
    """Load AzuraCast Sync API OpenAPI specification"""
    with open(SPEC_PATH) as f:
        return yaml.safe_load(f)


@pytest.fixture
def api_client():
    """
    Create API client for testing.

    THIS WILL FAIL - No implementation exists yet (TDD RED phase)
    """
    raise NotImplementedError(
        "AzuraCast Sync API not implemented yet. "
        "This is expected for TDD RED phase."
    )


@pytest.mark.contract
class TestAzuraCastSync:
    """Test /azuracast/sync endpoint (FR-016)"""

    def test_sync_playlist_success(self, api_client):
        """Test successful playlist sync to AzuraCast"""
        import uuid

        request_body = {
            "playlist_id": str(uuid.uuid4()),
            "azuracast_playlist_name": "Morning Drive - 2025-10-06",
            "dry_run": False,
            "replace_existing": False,
            "schedule_config": {
                "schedule_type": "repeating",
                "start_time": "06:00:00",
                "end_time": "10:00:00",
                "days_of_week": [0, 1, 2, 3, 4],  # Monday-Friday
                "weight": 10
            }
        }

        response = api_client.post("/api/v1/azuracast/sync", json=request_body)

        assert response.status_code == 200
        data = response.json()

        # Validate SyncResponse schema
        assert "playlist_id" in data
        assert "azuracast_playlist_name" in data
        assert "status" in data
        assert data["status"] in ["success", "failed", "dry_run"]
        assert "dry_run" in data
        assert "tracks_synced" in data
        assert "tracks_failed" in data

        if not data["dry_run"] and data["status"] == "success":
            assert "azuracast_playlist_id" in data
            assert isinstance(data["azuracast_playlist_id"], int)

    def test_sync_playlist_dry_run(self, api_client):
        """Test dry-run mode without actual sync (FR-016)"""
        import uuid

        request_body = {
            "playlist_id": str(uuid.uuid4()),
            "azuracast_playlist_name": "Test Playlist",
            "dry_run": True,
            "replace_existing": False
        }

        response = api_client.post("/api/v1/azuracast/sync", json=request_body)

        assert response.status_code == 200
        data = response.json()

        assert data["dry_run"] is True
        assert data["status"] == "dry_run"
        assert data["azuracast_playlist_id"] is None

    def test_sync_playlist_replace_existing(self, api_client):
        """Test replacing existing playlist vs merge"""
        import uuid

        for replace_mode in [True, False]:
            request_body = {
                "playlist_id": str(uuid.uuid4()),
                "azuracast_playlist_name": "Existing Playlist",
                "dry_run": False,
                "replace_existing": replace_mode
            }

            response = api_client.post("/api/v1/azuracast/sync", json=request_body)

            if response.status_code == 200:
                data = response.json()
                assert "status" in data

    def test_sync_invalid_request(self, api_client):
        """Test 400 error on invalid sync request"""
        request_body = {
            "playlist_id": "invalid-uuid",
            "azuracast_playlist_name": ""
        }

        response = api_client.post("/api/v1/azuracast/sync", json=request_body)

        assert response.status_code == 400
        error = response.json()
        assert "error" in error
        assert "message" in error

    def test_sync_azuracast_unavailable(self, api_client):
        """Test 503 error when AzuraCast unavailable"""
        import uuid

        request_body = {
            "playlist_id": str(uuid.uuid4()),
            "azuracast_playlist_name": "Test Playlist",
            "dry_run": False
        }

        # Simulate AzuraCast being down
        response = api_client.post("/api/v1/azuracast/sync", json=request_body)

        if response.status_code == 503:
            error = response.json()
            assert "error" in error
            assert "message" in error


@pytest.mark.contract
class TestScheduleConfiguration:
    """Test schedule configuration options"""

    def test_schedule_once(self, api_client):
        """Test one-time scheduled playlist"""
        import uuid

        request_body = {
            "playlist_id": str(uuid.uuid4()),
            "azuracast_playlist_name": "Special Event Playlist",
            "dry_run": True,
            "schedule_config": {
                "schedule_type": "once",
                "start_time": "20:00:00",
                "end_time": "22:00:00"
            }
        }

        response = api_client.post("/api/v1/azuracast/sync", json=request_body)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "dry_run"

    def test_schedule_repeating(self, api_client):
        """Test repeating scheduled playlist"""
        import uuid

        request_body = {
            "playlist_id": str(uuid.uuid4()),
            "azuracast_playlist_name": "Daily Morning Show",
            "dry_run": True,
            "schedule_config": {
                "schedule_type": "repeating",
                "start_time": "06:00:00",
                "end_time": "10:00:00",
                "days_of_week": [0, 1, 2, 3, 4],  # Weekdays
                "weight": 15
            }
        }

        response = api_client.post("/api/v1/azuracast/sync", json=request_body)

        assert response.status_code == 200

    def test_schedule_weight_validation(self, api_client):
        """Test playlist weight constraints"""
        import uuid

        for weight in [1, 50, 100]:
            request_body = {
                "playlist_id": str(uuid.uuid4()),
                "azuracast_playlist_name": f"Weighted Playlist {weight}",
                "dry_run": True,
                "schedule_config": {
                    "schedule_type": "repeating",
                    "weight": weight
                }
            }

            response = api_client.post("/api/v1/azuracast/sync", json=request_body)

            # Weight must be 1-100
            assert response.status_code in [200, 400]


@pytest.mark.contract
class TestBatchSync:
    """Test /azuracast/batch-sync endpoint"""

    def test_batch_sync_playlists(self, api_client):
        """Test syncing multiple playlists in batch"""
        import uuid

        request_body = {
            "playlist_ids": [str(uuid.uuid4()) for _ in range(3)],
            "dry_run": False,
            "replace_existing": False
        }

        response = api_client.post("/api/v1/azuracast/batch-sync", json=request_body)

        assert response.status_code == 200
        data = response.json()

        assert "batch_id" in data
        assert "total_playlists" in data
        assert data["total_playlists"] == 3
        assert "successful_syncs" in data
        assert "failed_syncs" in data
        assert "dry_run" in data
        assert "results" in data

        # Validate individual sync results
        assert len(data["results"]) == 3
        for result in data["results"]:
            assert "playlist_id" in result
            assert "status" in result

    def test_batch_sync_dry_run(self, api_client):
        """Test batch dry-run mode"""
        import uuid

        request_body = {
            "playlist_ids": [str(uuid.uuid4()) for _ in range(5)],
            "dry_run": True,
            "replace_existing": False
        }

        response = api_client.post("/api/v1/azuracast/batch-sync", json=request_body)

        assert response.status_code == 200
        data = response.json()

        assert data["dry_run"] is True

        # All results should be dry-run
        for result in data["results"]:
            assert result["dry_run"] is True
            assert result["status"] == "dry_run"

    def test_batch_sync_partial_failure(self, api_client):
        """Test handling partial failures in batch sync"""
        import uuid

        request_body = {
            "playlist_ids": [str(uuid.uuid4()) for _ in range(4)],
            "dry_run": False
        }

        response = api_client.post("/api/v1/azuracast/batch-sync", json=request_body)

        if response.status_code == 200:
            data = response.json()

            # Count successes and failures
            total = data["successful_syncs"] + data["failed_syncs"]
            assert total == data["total_playlists"]


@pytest.mark.contract
class TestAzuraCastConnection:
    """Test /azuracast/verify endpoint"""

    def test_verify_connection_success(self, api_client):
        """Test successful AzuraCast connection verification"""
        response = api_client.post("/api/v1/azuracast/verify")

        if response.status_code == 200:
            data = response.json()

            assert "connected" in data
            assert data["connected"] is True
            assert "azuracast_version" in data
            assert "station_name" in data
            assert "station_id" in data

            assert isinstance(data["station_id"], int)

    def test_verify_connection_invalid_credentials(self, api_client):
        """Test 401 error on invalid credentials"""
        response = api_client.post("/api/v1/azuracast/verify")

        if response.status_code == 401:
            error = response.json()
            assert "error" in error
            assert "message" in error

    def test_verify_connection_unavailable(self, api_client):
        """Test 503 error when AzuraCast unavailable"""
        response = api_client.post("/api/v1/azuracast/verify")

        if response.status_code == 503:
            error = response.json()
            assert "error" in error


@pytest.mark.contract
class TestAzuraCastPlaylistListing:
    """Test /azuracast/playlists endpoint"""

    def test_list_azuracast_playlists(self, api_client):
        """Test retrieving all AzuraCast playlists"""
        response = api_client.get("/api/v1/azuracast/playlists")

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)

        # Validate AzuraCastPlaylist schema
        for playlist in data:
            assert "id" in playlist
            assert isinstance(playlist["id"], int)
            assert "name" in playlist
            assert "type" in playlist
            assert playlist["type"] in [
                "default",
                "once_per_x_songs",
                "once_per_x_minutes",
                "once_per_hour",
                "custom"
            ]
            assert "source" in playlist
            assert playlist["source"] in ["songs", "remote_url"]
            assert "order" in playlist
            assert playlist["order"] in ["shuffle", "random", "sequential"]
            assert "is_enabled" in playlist
            assert "weight" in playlist
            assert "num_songs" in playlist

    def test_playlist_schedule_items(self, api_client):
        """Test playlist schedule items structure"""
        response = api_client.get("/api/v1/azuracast/playlists")

        if response.status_code == 200:
            data = response.json()

            for playlist in data:
                if "schedule_items" in playlist:
                    assert isinstance(playlist["schedule_items"], list)

                    for schedule_item in playlist["schedule_items"]:
                        assert "start_time" in schedule_item
                        assert "end_time" in schedule_item
                        assert "days" in schedule_item

                        # Unix timestamps
                        assert isinstance(schedule_item["start_time"], int)
                        assert isinstance(schedule_item["end_time"], int)

                        # Days array
                        assert isinstance(schedule_item["days"], list)


@pytest.mark.contract
class TestSyncResponseDetails:
    """Test detailed sync response validation"""

    def test_sync_response_warnings(self, api_client):
        """Test warnings in sync response"""
        import uuid

        request_body = {
            "playlist_id": str(uuid.uuid4()),
            "azuracast_playlist_name": "Test Playlist",
            "dry_run": False
        }

        response = api_client.post("/api/v1/azuracast/sync", json=request_body)

        if response.status_code == 200:
            data = response.json()

            if "warnings" in data:
                assert isinstance(data["warnings"], list)
                for warning in data["warnings"]:
                    assert isinstance(warning, str)

    def test_sync_response_errors(self, api_client):
        """Test errors array in sync response"""
        import uuid

        request_body = {
            "playlist_id": str(uuid.uuid4()),
            "azuracast_playlist_name": "Test Playlist",
            "dry_run": False
        }

        response = api_client.post("/api/v1/azuracast/sync", json=request_body)

        if response.status_code == 200:
            data = response.json()

            if "errors" in data:
                assert isinstance(data["errors"], list)

    def test_sync_response_timing(self, api_client):
        """Test sync duration tracking"""
        import uuid

        request_body = {
            "playlist_id": str(uuid.uuid4()),
            "azuracast_playlist_name": "Test Playlist",
            "dry_run": True
        }

        response = api_client.post("/api/v1/azuracast/sync", json=request_body)

        if response.status_code == 200:
            data = response.json()

            if "sync_duration_seconds" in data:
                assert isinstance(data["sync_duration_seconds"], (int, float))
                assert data["sync_duration_seconds"] >= 0

    def test_sync_response_azuracast_url(self, api_client):
        """Test AzuraCast UI URL in response"""
        import uuid

        request_body = {
            "playlist_id": str(uuid.uuid4()),
            "azuracast_playlist_name": "Test Playlist",
            "dry_run": False
        }

        response = api_client.post("/api/v1/azuracast/sync", json=request_body)

        if response.status_code == 200:
            data = response.json()

            if data["status"] == "success":
                # URL should be provided for successful syncs
                if "azuracast_url" in data and data["azuracast_url"]:
                    assert isinstance(data["azuracast_url"], str)
                    assert data["azuracast_url"].startswith("http")
