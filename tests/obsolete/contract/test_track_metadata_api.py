"""
Contract tests for Track Metadata API (OpenAPI Specification Validation)

Tests validate API contracts against track-metadata-api.yaml specification.
These tests MUST FAIL initially - no implementation exists yet (TDD RED phase).

FR-029: Metadata enhancement from Last.fm and aubio
FR-010: Track search from music library
FR-011: Track validation against criteria
"""

import pytest
from typing import Dict, Any
import yaml
from pathlib import Path


SPEC_PATH = Path("/workspaces/emby-to-m3u/specs/005-refactor-core-playlist/contracts/track-metadata-api.yaml")


@pytest.fixture
def openapi_spec():
    """Load Track Metadata API OpenAPI specification"""
    with open(SPEC_PATH) as f:
        return yaml.safe_load(f)


@pytest.fixture
def api_client():
    """
    Create API client for testing.

    THIS WILL FAIL - No implementation exists yet (TDD RED phase)
    """
    raise NotImplementedError(
        "Track Metadata API not implemented yet. "
        "This is expected for TDD RED phase."
    )


@pytest.mark.contract
class TestTrackSearch:
    """Test /tracks/search endpoint"""

    def test_search_tracks_success(self, api_client):
        """Test successful track search with criteria (FR-010)"""
        request_body = {
            "criteria": {
                "bpm_ranges": [
                    {
                        "time_start": "06:00:00",
                        "time_end": "07:00:00",
                        "bpm_min": 90,
                        "bpm_max": 115
                    }
                ],
                "genre_mix": {
                    "Contemporary Alternative": {
                        "target_percentage": 0.25,
                        "tolerance": 0.10
                    }
                },
                "era_distribution": {
                    "Current": {
                        "era_name": "Current",
                        "min_year": 2023,
                        "max_year": 2025,
                        "target_percentage": 0.40,
                        "tolerance": 0.10
                    }
                },
                "australian_content_min": 0.30,
                "energy_flow_requirements": ["uplifting", "positive"],
                "rotation_distribution": {
                    "Power": 0.40,
                    "Medium": 0.30
                },
                "no_repeat_window_hours": 24.0
            },
            "limit": 100,
            "offset": 0
        }

        response = api_client.post("/api/v1/tracks/search", json=request_body)

        assert response.status_code == 200
        data = response.json()

        # Validate response schema
        assert "tracks" in data
        assert "total_count" in data
        assert "search_time_ms" in data

        assert isinstance(data["tracks"], list)
        assert isinstance(data["total_count"], int)

        # Validate TrackMetadata schema for each track
        for track in data["tracks"]:
            self._validate_track_metadata(track)

    def test_search_with_exclusions(self, api_client):
        """Test track search with exclusion list (no-repeat enforcement)"""
        request_body = {
            "criteria": {
                "bpm_ranges": [{"time_start": "06:00:00", "time_end": "10:00:00", "bpm_min": 90, "bpm_max": 130}],
                "genre_mix": {},
                "era_distribution": {},
                "australian_content_min": 0.30,
                "energy_flow_requirements": [],
                "rotation_distribution": {},
                "no_repeat_window_hours": 24.0
            },
            "exclude_track_ids": ["track_001", "track_002", "track_003"]
        }

        response = api_client.post("/api/v1/tracks/search", json=request_body)

        assert response.status_code == 200
        data = response.json()

        # Verify excluded tracks are not in results
        returned_ids = [t["track_id"] for t in data["tracks"]]
        for excluded_id in request_body["exclude_track_ids"]:
            assert excluded_id not in returned_ids

    def test_search_invalid_criteria(self, api_client):
        """Test 400 error on invalid search criteria"""
        request_body = {
            "criteria": {
                # Missing required fields
                "bpm_ranges": []
            }
        }

        response = api_client.post("/api/v1/tracks/search", json=request_body)

        assert response.status_code == 400
        error = response.json()
        assert "error" in error
        assert "message" in error

    @staticmethod
    def _validate_track_metadata(track: Dict[str, Any]):
        """Validate TrackMetadata schema"""
        # Required fields
        assert "track_id" in track
        assert "title" in track
        assert "artist" in track
        assert "album" in track
        assert "duration_seconds" in track
        assert "is_australian" in track
        assert "rotation_category" in track
        assert "metadata_source" in track
        assert "metadata_completeness" in track

        # Validate constraints
        assert track["duration_seconds"] >= 1
        assert isinstance(track["is_australian"], bool)
        assert track["rotation_category"] in ["Power", "Medium", "Light", "Recurrent", "Library"]
        assert track["metadata_source"] in ["library", "lastfm", "aubio", "mixed"]
        assert 0.0 <= track["metadata_completeness"] <= 1.0

        # Optional fields with constraints
        if track.get("bpm"):
            assert 60 <= track["bpm"] <= 200

        if track.get("year"):
            assert track["year"] >= 1900


@pytest.mark.contract
class TestTrackMetadataRetrieval:
    """Test /tracks/{track_id}/metadata endpoint"""

    def test_get_track_metadata_success(self, api_client):
        """Test retrieving complete metadata for track"""
        track_id = "test_track_001"

        response = api_client.get(f"/api/v1/tracks/{track_id}/metadata")

        assert response.status_code == 200
        track = response.json()

        # Validate TrackMetadata schema
        assert track["track_id"] == track_id
        assert "title" in track
        assert "artist" in track
        assert "metadata_source" in track

    def test_get_track_metadata_with_enhancement(self, api_client):
        """Test metadata retrieval with auto-enhancement (FR-029)"""
        track_id = "test_track_002"

        response = api_client.get(
            f"/api/v1/tracks/{track_id}/metadata",
            params={"enhance": True}
        )

        assert response.status_code == 200
        track = response.json()

        # Should attempt to enhance missing fields
        assert "metadata_source" in track

    def test_get_track_metadata_not_found(self, api_client):
        """Test 404 error when track not found"""
        track_id = "nonexistent_track"

        response = api_client.get(f"/api/v1/tracks/{track_id}/metadata")

        assert response.status_code == 404
        error = response.json()
        assert "error" in error


@pytest.mark.contract
class TestMetadataEnhancement:
    """Test /tracks/{track_id}/enhance endpoint (FR-029)"""

    def test_enhance_metadata_lastfm(self, api_client):
        """Test metadata enhancement from Last.fm"""
        track_id = "test_track_003"

        response = api_client.post(
            f"/api/v1/tracks/{track_id}/enhance",
            json={"force_aubio": False}
        )

        assert response.status_code == 200
        data = response.json()

        # Validate enhancement response schema
        assert "track_id" in data
        assert data["track_id"] == track_id
        assert "enhanced_fields" in data
        assert "metadata_source" in data
        assert data["metadata_source"] in ["library", "lastfm", "aubio"]
        assert "metadata" in data

        assert isinstance(data["enhanced_fields"], list)

    def test_enhance_metadata_aubio_fallback(self, api_client):
        """Test fallback to aubio when Last.fm unavailable"""
        track_id = "test_track_004"

        response = api_client.post(
            f"/api/v1/tracks/{track_id}/enhance",
            json={"force_aubio": True}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["metadata_source"] == "aubio"
        assert "bpm" in data["enhanced_fields"]

    def test_enhance_metadata_caching(self, api_client):
        """Test that enhanced metadata is permanently cached (FR-029)"""
        track_id = "test_track_005"

        # First enhancement
        response1 = api_client.post(f"/api/v1/tracks/{track_id}/enhance")
        assert response1.status_code == 200

        # Second request should use cached data
        response2 = api_client.get(f"/api/v1/tracks/{track_id}/metadata")
        assert response2.status_code == 200

        metadata = response2.json()
        assert metadata["metadata_source"] in ["lastfm", "aubio"]

    def test_enhance_metadata_not_found(self, api_client):
        """Test 404 error when track not found"""
        track_id = "nonexistent_track"

        response = api_client.post(f"/api/v1/tracks/{track_id}/enhance")

        assert response.status_code == 404

    def test_enhance_metadata_failure(self, api_client):
        """Test 500 error when enhancement fails"""
        track_id = "bad_track"

        # Simulate enhancement failure
        response = api_client.post(f"/api/v1/tracks/{track_id}/enhance")

        # Should return 500 if both Last.fm and aubio fail
        if response.status_code == 500:
            error = response.json()
            assert "error" in error
            assert "message" in error


@pytest.mark.contract
class TestTrackValidation:
    """Test /tracks/validate endpoint (FR-011)"""

    def test_validate_track_success(self, api_client):
        """Test track validation against criteria"""
        request_body = {
            "track_id": "test_track_006",
            "criteria": {
                "bpm_ranges": [
                    {
                        "time_start": "06:00:00",
                        "time_end": "07:00:00",
                        "bpm_min": 90,
                        "bpm_max": 115
                    }
                ],
                "genre_mix": {
                    "Contemporary Alternative": {
                        "target_percentage": 0.25
                    }
                },
                "era_distribution": {},
                "australian_content_min": 0.30,
                "energy_flow_requirements": ["uplifting"],
                "rotation_distribution": {},
                "no_repeat_window_hours": 24.0
            },
            "playlist_time": "06:30:00"
        }

        response = api_client.post("/api/v1/tracks/validate", json=request_body)

        assert response.status_code == 200
        data = response.json()

        # Validate validation result schema
        assert "track_id" in data
        assert "validation_status" in data
        assert data["validation_status"] in ["pass", "fail", "warning"]
        assert "validation_notes" in data
        assert "criteria_matched" in data

        assert isinstance(data["validation_notes"], list)
        assert isinstance(data["criteria_matched"], list)

    def test_validate_track_bpm_check(self, api_client):
        """Test BPM range validation at specific playlist time"""
        request_body = {
            "track_id": "test_track_007",
            "criteria": {
                "bpm_ranges": [
                    {
                        "time_start": "06:00:00",
                        "time_end": "07:00:00",
                        "bpm_min": 90,
                        "bpm_max": 115
                    },
                    {
                        "time_start": "07:00:00",
                        "time_end": "08:00:00",
                        "bpm_min": 110,
                        "bpm_max": 130
                    }
                ],
                "genre_mix": {},
                "era_distribution": {},
                "australian_content_min": 0.30,
                "energy_flow_requirements": [],
                "rotation_distribution": {},
                "no_repeat_window_hours": 24.0,
                "tolerance_bpm": 10
            },
            "playlist_time": "06:45:00"
        }

        response = api_client.post("/api/v1/tracks/validate", json=request_body)

        assert response.status_code == 200
        data = response.json()

        # Should validate against 06:00-07:00 BPM range
        if "bpm" in data["criteria_matched"]:
            assert data["validation_status"] in ["pass", "warning"]

    def test_validate_track_tolerance_handling(self, api_client):
        """Test tolerance parameters in validation"""
        request_body = {
            "track_id": "test_track_008",
            "criteria": {
                "bpm_ranges": [{"time_start": "06:00:00", "time_end": "10:00:00", "bpm_min": 100, "bpm_max": 120}],
                "genre_mix": {
                    "Alternative": {"target_percentage": 0.30, "tolerance": 0.10}
                },
                "era_distribution": {
                    "Current": {
                        "era_name": "Current",
                        "min_year": 2023,
                        "max_year": 2025,
                        "target_percentage": 0.40,
                        "tolerance": 0.10
                    }
                },
                "australian_content_min": 0.30,
                "energy_flow_requirements": [],
                "rotation_distribution": {},
                "no_repeat_window_hours": 24.0,
                "tolerance_bpm": 10,
                "tolerance_genre_percent": 0.10,
                "tolerance_era_percent": 0.10
            },
            "playlist_time": "06:00:00"
        }

        response = api_client.post("/api/v1/tracks/validate", json=request_body)

        assert response.status_code == 200
        data = response.json()

        # Validation should use tolerance values
        assert "validation_status" in data


@pytest.mark.contract
class TestSpecialtyConstraints:
    """Test specialty constraint validation"""

    def test_australian_only_constraint(self, api_client):
        """Test australian_only specialty constraint"""
        request_body = {
            "track_id": "test_track_009",
            "criteria": {
                "bpm_ranges": [{"time_start": "06:00:00", "time_end": "10:00:00", "bpm_min": 90, "bpm_max": 130}],
                "genre_mix": {},
                "era_distribution": {},
                "australian_content_min": 0.30,
                "energy_flow_requirements": [],
                "rotation_distribution": {},
                "no_repeat_window_hours": 24.0,
                "specialty_constraints": {
                    "constraint_type": "australian_only",
                    "description": "Australian music hour",
                    "parameters": {}
                }
            },
            "playlist_time": "06:00:00"
        }

        response = api_client.post("/api/v1/tracks/validate", json=request_body)

        assert response.status_code == 200
        data = response.json()

        # Track must be Australian
        if data["validation_status"] == "pass":
            assert "is_australian" in data["criteria_matched"]
