"""
Contract tests for AI/ML Playlist Generation API (OpenAPI Specification Validation)

Tests validate API contracts against playlist-generation-api.yaml specification.
These tests MUST FAIL initially - no implementation exists yet (TDD RED phase).

FR-005 to FR-009: AI/ML track selection with cost controls
FR-030: Cost budget allocation and tracking
FR-025, FR-026: Playlist validation
FR-018, FR-027: Decision logging
"""

import pytest
from typing import Dict, Any
import yaml
from pathlib import Path
from decimal import Decimal


SPEC_PATH = Path("/workspaces/emby-to-m3u/specs/005-refactor-core-playlist/contracts/playlist-generation-api.yaml")


@pytest.fixture
def openapi_spec():
    """Load Playlist Generation API OpenAPI specification"""
    with open(SPEC_PATH) as f:
        return yaml.safe_load(f)


@pytest.fixture
def api_client():
    """
    Create API client for testing.

    THIS WILL FAIL - No implementation exists yet (TDD RED phase)
    """
    raise NotImplementedError(
        "Playlist Generation API not implemented yet. "
        "This is expected for TDD RED phase."
    )


@pytest.mark.contract
class TestPlaylistGeneration:
    """Test /playlists/generate endpoint (FR-005 to FR-009)"""

    def test_generate_playlist_success(self, api_client):
        """Test successful playlist generation with AI/ML"""
        import uuid

        request_body = {
            "daypart_id": str(uuid.uuid4()),
            "generation_date": "2025-10-06",
            "cost_budget": "5.00",
            "budget_mode": "suggested",
            "allow_constraint_relaxation": True,
            "max_relaxation_steps": 3
        }

        response = api_client.post("/api/v1/playlists/generate", json=request_body)

        assert response.status_code == 200
        data = response.json()

        # Validate PlaylistGenerationResponse schema
        assert "playlist_id" in data
        assert "name" in data
        assert "status" in data
        assert data["status"] in ["completed", "completed_with_warnings", "failed"]
        assert "track_count" in data
        assert "cost_actual" in data
        assert "generation_time_seconds" in data

        # Validate cost tracking
        assert isinstance(data["cost_actual"], str)  # Decimal string
        cost_actual = Decimal(data["cost_actual"])

        if data.get("cost_budget"):
            cost_budget = Decimal(data["cost_budget"])
            assert "budget_exceeded" in data

    def test_generate_playlist_hard_budget_exceeded(self, api_client):
        """Test 402 error when hard budget limit exceeded (FR-009, FR-030)"""
        import uuid

        request_body = {
            "daypart_id": str(uuid.uuid4()),
            "generation_date": "2025-10-06",
            "cost_budget": "0.01",  # Very low budget
            "budget_mode": "hard",  # Hard limit enforcement
            "allow_constraint_relaxation": True
        }

        response = api_client.post("/api/v1/playlists/generate", json=request_body)

        # Should fail with 402 Payment Required when budget exceeded
        if response.status_code == 402:
            error = response.json()

            # Validate CostBudgetExceeded schema
            assert "error" in error
            assert error["error"] == "cost_budget_exceeded"
            assert "message" in error
            assert "budget_mode" in error
            assert error["budget_mode"] == "hard"
            assert "cost_budget" in error
            assert "cost_actual" in error
            assert "cost_overage" in error

    def test_generate_playlist_suggested_budget(self, api_client):
        """Test suggested budget mode allows overage (FR-009)"""
        import uuid

        request_body = {
            "daypart_id": str(uuid.uuid4()),
            "generation_date": "2025-10-06",
            "cost_budget": "1.00",
            "budget_mode": "suggested",  # Allows overage
            "allow_constraint_relaxation": True
        }

        response = api_client.post("/api/v1/playlists/generate", json=request_body)

        # Should succeed even if budget exceeded
        assert response.status_code == 200
        data = response.json()

        if data.get("budget_exceeded"):
            assert data["budget_mode"] == "suggested"

    def test_generate_playlist_constraint_relaxation(self, api_client):
        """Test progressive constraint relaxation (FR-028)"""
        import uuid

        request_body = {
            "daypart_id": str(uuid.uuid4()),
            "generation_date": "2025-10-06",
            "allow_constraint_relaxation": True,
            "max_relaxation_steps": 5
        }

        response = api_client.post("/api/v1/playlists/generate", json=request_body)

        assert response.status_code == 200
        data = response.json()

        assert "constraint_relaxations_applied" in data
        assert isinstance(data["constraint_relaxations_applied"], int)
        assert 0 <= data["constraint_relaxations_applied"] <= 5

    def test_generate_playlist_validation_summary(self, api_client):
        """Test validation summary in generation response"""
        import uuid

        request_body = {
            "daypart_id": str(uuid.uuid4()),
            "generation_date": "2025-10-06"
        }

        response = api_client.post("/api/v1/playlists/generate", json=request_body)

        assert response.status_code == 200
        data = response.json()

        if "validation_summary" in data:
            summary = data["validation_summary"]
            assert "overall_status" in summary
            assert summary["overall_status"] in ["pass", "fail", "warning"]
            assert "compliance_percentage" in summary


@pytest.mark.contract
class TestPlaylistRetrieval:
    """Test /playlists/{playlist_id} endpoint"""

    def test_get_playlist(self, api_client):
        """Test retrieving generated playlist"""
        import uuid

        playlist_id = str(uuid.uuid4())
        response = api_client.get(f"/api/v1/playlists/{playlist_id}")

        if response.status_code == 200:
            data = response.json()

            # Validate Playlist schema
            assert "id" in data
            assert "name" in data
            assert "specification_id" in data
            assert "tracks" in data
            assert "validation_result" in data
            assert "created_at" in data
            assert "cost_actual" in data
            assert "generation_time_seconds" in data
            assert "constraint_relaxations" in data

            # Validate tracks array
            assert isinstance(data["tracks"], list)
            for track in data["tracks"]:
                self._validate_selected_track(track)

    def test_get_playlist_not_found(self, api_client):
        """Test 404 error when playlist not found"""
        import uuid

        playlist_id = str(uuid.uuid4())
        response = api_client.get(f"/api/v1/playlists/{playlist_id}")

        assert response.status_code == 404
        error = response.json()
        assert "error" in error

    @staticmethod
    def _validate_selected_track(track: Dict[str, Any]):
        """Validate SelectedTrack schema with AI reasoning (FR-007)"""
        # Required fields
        assert "track_id" in track
        assert "title" in track
        assert "artist" in track
        assert "album" in track
        assert "duration_seconds" in track
        assert "is_australian" in track
        assert "rotation_category" in track
        assert "position_in_playlist" in track
        assert "selection_reasoning" in track  # AI explanation (FR-007)
        assert "validation_status" in track
        assert "metadata_source" in track

        # Validate constraints
        assert track["rotation_category"] in ["Power", "Medium", "Light", "Recurrent", "Library"]
        assert track["validation_status"] in ["pass", "fail", "warning"]
        assert track["metadata_source"] in ["library", "lastfm", "aubio"]

        # Selection reasoning must be present (FR-007)
        assert len(track["selection_reasoning"]) > 0


@pytest.mark.contract
class TestPlaylistValidation:
    """Test /playlists/{playlist_id}/validate endpoint (FR-025, FR-026)"""

    def test_validate_playlist(self, api_client):
        """Test complete playlist validation"""
        import uuid

        playlist_id = str(uuid.uuid4())
        response = api_client.post(f"/api/v1/playlists/{playlist_id}/validate")

        if response.status_code == 200:
            data = response.json()

            # Validate ValidationResult schema
            assert "playlist_id" in data
            assert "overall_status" in data
            assert data["overall_status"] in ["pass", "fail", "warning"]
            assert "constraint_scores" in data
            assert "flow_quality_metrics" in data
            assert "compliance_percentage" in data
            assert "validated_at" in data

            # Validate compliance percentage
            assert 0.0 <= data["compliance_percentage"] <= 1.0

    def test_constraint_scores_validation(self, api_client):
        """Test constraint score schema (FR-025)"""
        import uuid

        playlist_id = str(uuid.uuid4())
        response = api_client.post(f"/api/v1/playlists/{playlist_id}/validate")

        if response.status_code == 200:
            data = response.json()
            scores = data["constraint_scores"]

            for constraint_name, score in scores.items():
                # Validate ConstraintScore schema
                assert "constraint_name" in score
                assert "target_value" in score
                assert "actual_value" in score
                assert "tolerance" in score
                assert "is_compliant" in score
                assert "deviation_percentage" in score

                assert isinstance(score["is_compliant"], bool)

    def test_flow_quality_metrics(self, api_client):
        """Test flow quality metrics validation (FR-026)"""
        import uuid

        playlist_id = str(uuid.uuid4())
        response = api_client.post(f"/api/v1/playlists/{playlist_id}/validate")

        if response.status_code == 200:
            data = response.json()
            metrics = data["flow_quality_metrics"]

            # Validate FlowQualityMetrics schema
            assert "bpm_variance" in metrics
            assert "bpm_progression_coherence" in metrics
            assert "energy_consistency" in metrics
            assert "genre_diversity_index" in metrics
            assert "overall_quality_score" in metrics

            # Validate ranges
            assert 0.0 <= metrics["bpm_progression_coherence"] <= 1.0
            assert 0.0 <= metrics["energy_consistency"] <= 1.0
            assert 0.0 <= metrics["genre_diversity_index"] <= 1.0
            assert 0.0 <= metrics["overall_quality_score"] <= 1.0


@pytest.mark.contract
class TestPlaylistExport:
    """Test /playlists/{playlist_id}/export endpoint (FR-016)"""

    def test_export_playlist_m3u(self, api_client):
        """Test M3U export for AzuraCast sync"""
        import uuid

        playlist_id = str(uuid.uuid4())
        response = api_client.get(f"/api/v1/playlists/{playlist_id}/export")

        if response.status_code == 200:
            assert response.headers["content-type"] == "audio/x-mpegurl"
            m3u_content = response.text

            # Validate M3U format
            assert m3u_content.startswith("#EXTM3U")
            assert "#PLAYLIST:" in m3u_content
            assert "#EXTINF:" in m3u_content

    def test_export_playlist_formats(self, api_client):
        """Test different M3U export formats"""
        import uuid

        playlist_id = str(uuid.uuid4())

        for format_type in ["m3u", "m3u8", "extm3u"]:
            response = api_client.get(
                f"/api/v1/playlists/{playlist_id}/export",
                params={"format": format_type}
            )

            if response.status_code == 200:
                assert response.headers["content-type"] == "audio/x-mpegurl"


@pytest.mark.contract
class TestDecisionLog:
    """Test /playlists/{playlist_id}/decision-log endpoint (FR-018, FR-027)"""

    def test_get_decision_log(self, api_client):
        """Test retrieving AI decision audit trail"""
        import uuid

        playlist_id = str(uuid.uuid4())
        response = api_client.get(f"/api/v1/playlists/{playlist_id}/decision-log")

        if response.status_code == 200:
            data = response.json()

            assert "playlist_id" in data
            assert "total_entries" in data
            assert "total_cost" in data
            assert "total_execution_time_ms" in data
            assert "entries" in data

            # Validate DecisionLogEntry schema
            for entry in data["entries"]:
                assert "id" in entry
                assert "playlist_id" in entry
                assert "decision_type" in entry
                assert entry["decision_type"] in ["track_selection", "validation", "error", "relaxation", "metadata_retrieval"]
                assert "timestamp" in entry
                assert "decision_data" in entry
                assert "cost_incurred" in entry
                assert "execution_time_ms" in entry

    def test_filter_decision_log_by_type(self, api_client):
        """Test filtering decision log by decision type"""
        import uuid

        playlist_id = str(uuid.uuid4())

        for decision_type in ["track_selection", "validation", "error", "relaxation", "metadata_retrieval"]:
            response = api_client.get(
                f"/api/v1/playlists/{playlist_id}/decision-log",
                params={"decision_type": decision_type}
            )

            if response.status_code == 200:
                data = response.json()

                # All entries should match filter
                for entry in data["entries"]:
                    assert entry["decision_type"] == decision_type


@pytest.mark.contract
class TestBatchGeneration:
    """Test /playlists/batch-generate endpoint (FR-030)"""

    def test_batch_generate_playlists(self, api_client):
        """Test batch playlist generation with shared budget"""
        import uuid

        request_body = {
            "daypart_ids": [str(uuid.uuid4()) for _ in range(3)],
            "generation_date": "2025-10-06",
            "total_cost_budget": "15.00",
            "budget_mode": "suggested",
            "allocation_strategy": "dynamic",
            "allow_constraint_relaxation": True
        }

        response = api_client.post("/api/v1/playlists/batch-generate", json=request_body)

        if response.status_code == 200:
            data = response.json()

            assert "batch_id" in data
            assert "total_playlists" in data
            assert data["total_playlists"] == 3
            assert "estimated_cost" in data
            assert "budget_mode" in data
            assert "allocation_strategy" in data
            assert data["allocation_strategy"] in ["dynamic", "equal"]

    def test_batch_generate_hard_budget_exceeded(self, api_client):
        """Test 402 error when batch budget exceeded (FR-030)"""
        import uuid

        request_body = {
            "daypart_ids": [str(uuid.uuid4()) for _ in range(5)],
            "generation_date": "2025-10-06",
            "total_cost_budget": "0.10",  # Very low budget for 5 playlists
            "budget_mode": "hard"
        }

        response = api_client.post("/api/v1/playlists/batch-generate", json=request_body)

        if response.status_code == 402:
            error = response.json()
            assert error["error"] == "cost_budget_exceeded"
            assert error["budget_mode"] == "hard"

    def test_batch_status(self, api_client):
        """Test batch generation status monitoring"""
        import uuid

        batch_id = str(uuid.uuid4())
        response = api_client.get(f"/api/v1/playlists/batch/{batch_id}/status")

        if response.status_code == 200:
            data = response.json()

            # Validate BatchGenerationStatus schema
            assert "batch_id" in data
            assert "status" in data
            assert data["status"] in ["pending", "in_progress", "completed", "failed"]
            assert "playlists_requested" in data
            assert "playlists_completed" in data
            assert "playlists_failed" in data
            assert "total_cost_actual" in data
            assert "budget_exceeded" in data
            assert "started_at" in data
            assert "playlist_results" in data

    def test_budget_allocation_strategies(self, api_client):
        """Test dynamic vs equal budget allocation (FR-030)"""
        import uuid

        for strategy in ["dynamic", "equal"]:
            request_body = {
                "daypart_ids": [str(uuid.uuid4()) for _ in range(3)],
                "generation_date": "2025-10-06",
                "total_cost_budget": "10.00",
                "allocation_strategy": strategy
            }

            response = api_client.post("/api/v1/playlists/batch-generate", json=request_body)

            if response.status_code == 200:
                data = response.json()
                assert data["allocation_strategy"] == strategy
