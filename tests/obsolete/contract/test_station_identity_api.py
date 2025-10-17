"""
Contract tests for Station Identity API (OpenAPI Specification Validation)

Tests validate API contracts against station-identity-api.yaml specification.
These tests MUST FAIL initially - no implementation exists yet (TDD RED phase).

FR-031: Document locking during playlist generation batches
"""

import pytest
from typing import Dict, Any
import yaml
from pathlib import Path


# Load OpenAPI specification
SPEC_PATH = Path("/workspaces/emby-to-m3u/specs/005-refactor-core-playlist/contracts/station-identity-api.yaml")


@pytest.fixture
def openapi_spec():
    """Load Station Identity API OpenAPI specification"""
    with open(SPEC_PATH) as f:
        return yaml.safe_load(f)


@pytest.fixture
def api_client():
    """
    Create API client for testing.

    THIS WILL FAIL - No implementation exists yet (TDD RED phase)
    """
    # This should create a real client, but will fail for now
    raise NotImplementedError(
        "Station Identity API not implemented yet. "
        "This is expected for TDD RED phase."
    )


@pytest.mark.contract
class TestStationIdentityLoad:
    """Test /station-identity/load endpoint"""

    def test_load_station_identity_success(self, api_client, openapi_spec):
        """
        Test successful loading of station-identity.md document

        Expected to FAIL - endpoint not implemented
        """
        request_body = {
            "document_path": "/workspaces/emby-to-m3u/station-identity.md"
        }

        # This will fail - endpoint doesn't exist
        response = api_client.post("/api/v1/station-identity/load", json=request_body)

        # Validate response schema matches OpenAPI spec
        assert response.status_code == 200
        data = response.json()

        # Validate StationIdentityDocument schema
        assert "document_path" in data
        assert "programming_structures" in data
        assert "rotation_strategy" in data
        assert "content_requirements" in data
        assert "genre_definitions" in data
        assert "version" in data  # SHA-256 hash
        assert "loaded_at" in data

        # Validate programming_structures
        assert isinstance(data["programming_structures"], list)
        for structure in data["programming_structures"]:
            assert "schedule_type" in structure
            assert structure["schedule_type"] in ["weekday", "saturday", "sunday"]
            assert "dayparts" in structure

    def test_load_station_identity_invalid_path(self, api_client):
        """Test 400 error on invalid document path"""
        request_body = {"document_path": ""}

        response = api_client.post("/api/v1/station-identity/load", json=request_body)

        assert response.status_code == 400
        error = response.json()
        assert "error" in error
        assert "message" in error

    def test_load_station_identity_not_found(self, api_client):
        """Test 404 error when document not found"""
        request_body = {
            "document_path": "/nonexistent/station-identity.md"
        }

        response = api_client.post("/api/v1/station-identity/load", json=request_body)

        assert response.status_code == 404
        error = response.json()
        assert "error" in error
        assert "message" in error


@pytest.mark.contract
class TestStationIdentityLocking:
    """Test /station-identity/lock and /station-identity/unlock endpoints"""

    def test_lock_station_identity_success(self, api_client):
        """Test acquiring exclusive lock (FR-031)"""
        import uuid

        request_body = {
            "session_id": str(uuid.uuid4())
        }

        response = api_client.post("/api/v1/station-identity/lock", json=request_body)

        assert response.status_code == 200
        data = response.json()

        # Validate lock response schema
        assert "lock_id" in data
        assert "lock_timestamp" in data
        assert "locked_by" in data

        # Validate UUID format
        uuid.UUID(data["lock_id"])

    def test_lock_already_locked(self, api_client):
        """Test 409 conflict when document already locked"""
        import uuid

        # First lock should succeed
        session_1 = str(uuid.uuid4())
        response1 = api_client.post(
            "/api/v1/station-identity/lock",
            json={"session_id": session_1}
        )
        assert response1.status_code == 200

        # Second lock should fail with 409
        session_2 = str(uuid.uuid4())
        response2 = api_client.post(
            "/api/v1/station-identity/lock",
            json={"session_id": session_2}
        )

        assert response2.status_code == 409
        error = response2.json()
        assert "error" in error
        assert "message" in error

    def test_unlock_station_identity_success(self, api_client):
        """Test releasing lock"""
        import uuid

        # Acquire lock first
        session_id = str(uuid.uuid4())
        lock_response = api_client.post(
            "/api/v1/station-identity/lock",
            json={"session_id": session_id}
        )
        lock_id = lock_response.json()["lock_id"]

        # Release lock
        unlock_response = api_client.post(
            "/api/v1/station-identity/unlock",
            json={"lock_id": lock_id}
        )

        assert unlock_response.status_code == 200

    def test_unlock_not_found(self, api_client):
        """Test 404 error when lock not found"""
        import uuid

        request_body = {
            "lock_id": str(uuid.uuid4())  # Non-existent lock
        }

        response = api_client.post("/api/v1/station-identity/unlock", json=request_body)

        assert response.status_code == 404
        error = response.json()
        assert "error" in error


@pytest.mark.contract
class TestStationIdentityDayparts:
    """Test /station-identity/dayparts endpoint"""

    def test_get_all_dayparts(self, api_client):
        """Test retrieving all daypart specifications"""
        response = api_client.get("/api/v1/station-identity/dayparts")

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)

        # Validate DaypartSpecification schema
        for daypart in data:
            assert "id" in daypart
            assert "name" in daypart
            assert "schedule_type" in daypart
            assert daypart["schedule_type"] in ["weekday", "saturday", "sunday"]
            assert "time_start" in daypart
            assert "time_end" in daypart
            assert "duration_hours" in daypart
            assert "target_demographic" in daypart
            assert "bpm_progression" in daypart
            assert "genre_mix" in daypart
            assert "era_distribution" in daypart
            assert "mood_guidelines" in daypart
            assert "content_focus" in daypart
            assert "rotation_percentages" in daypart
            assert "tracks_per_hour" in daypart

            # Validate tracks_per_hour structure
            tph = daypart["tracks_per_hour"]
            assert "min" in tph
            assert "max" in tph
            assert tph["min"] >= 1
            assert tph["max"] >= tph["min"]

    def test_get_dayparts_filtered_by_schedule(self, api_client):
        """Test filtering dayparts by schedule type"""
        for schedule_type in ["weekday", "saturday", "sunday"]:
            response = api_client.get(
                "/api/v1/station-identity/dayparts",
                params={"schedule_type": schedule_type}
            )

            assert response.status_code == 200
            data = response.json()

            # All returned dayparts should match filter
            for daypart in data:
                assert daypart["schedule_type"] == schedule_type

    def test_bpm_range_validation(self, api_client):
        """Test BPM range schema validation in dayparts"""
        response = api_client.get("/api/v1/station-identity/dayparts")
        data = response.json()

        for daypart in data:
            for bpm_range in daypart["bpm_progression"]:
                assert "time_start" in bpm_range
                assert "time_end" in bpm_range
                assert "bpm_min" in bpm_range
                assert "bpm_max" in bpm_range

                # Validate BPM constraints
                assert 60 <= bpm_range["bpm_min"] <= 200
                assert 60 <= bpm_range["bpm_max"] <= 200
                assert bpm_range["bpm_max"] >= bpm_range["bpm_min"]


@pytest.mark.contract
class TestStationIdentityDataModels:
    """Test data model schema validation"""

    def test_rotation_strategy_schema(self, api_client):
        """Test RotationStrategy schema structure"""
        # Load document to access rotation strategy
        response = api_client.post(
            "/api/v1/station-identity/load",
            json={"document_path": "/workspaces/emby-to-m3u/station-identity.md"}
        )

        data = response.json()
        rotation = data["rotation_strategy"]

        assert "categories" in rotation

        # Validate rotation categories
        expected_categories = ["Power", "Medium", "Light", "Recurrent", "Library"]
        for category_name in expected_categories:
            assert category_name in rotation["categories"]
            category = rotation["categories"][category_name]

            assert "name" in category
            assert category["name"] in expected_categories
            assert "spins_per_week" in category
            assert category["spins_per_week"] >= 0
            assert "lifecycle_weeks" in category
            assert category["lifecycle_weeks"] >= 1

    def test_content_requirements_schema(self, api_client):
        """Test ContentRequirements schema"""
        response = api_client.post(
            "/api/v1/station-identity/load",
            json={"document_path": "/workspaces/emby-to-m3u/station-identity.md"}
        )

        data = response.json()
        content_req = data["content_requirements"]

        assert "australian_content_min" in content_req
        assert "australian_content_target" in content_req

        # Validate constraints
        assert 0.30 <= content_req["australian_content_min"] <= 1.0
        assert 0.30 <= content_req["australian_content_target"] <= 1.0
        assert content_req["australian_content_target"] >= content_req["australian_content_min"]

    def test_genre_definitions_schema(self, api_client):
        """Test GenreDefinition schema"""
        response = api_client.post(
            "/api/v1/station-identity/load",
            json={"document_path": "/workspaces/emby-to-m3u/station-identity.md"}
        )

        data = response.json()
        genres = data["genre_definitions"]

        assert isinstance(genres, list)

        for genre in genres:
            assert "name" in genre
            assert "description" in genre
            assert "typical_bpm_range" in genre

            bpm_range = genre["typical_bpm_range"]
            assert "min" in bpm_range
            assert "max" in bpm_range
            assert bpm_range["max"] >= bpm_range["min"]
