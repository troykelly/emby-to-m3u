"""
Comprehensive tests for _prompt_builders module.

Tests all prompt building functions including:
- build_selection_prompt()
- build_relaxation_prompt()
- format_genre_requirements()
- format_era_requirements()
"""
import pytest
from datetime import time as time_obj

from src.ai_playlist._prompt_builders import (
    build_selection_prompt,
    build_relaxation_prompt,
    format_genre_requirements,
    format_era_requirements,
)
from src.ai_playlist.models import (
    LLMTrackSelectionRequest,
    TrackSelectionCriteria,
    BPMRange,
    GenreCriteria,
    EraCriteria,
)


class TestBuildSelectionPrompt:
    """Tests for build_selection_prompt()."""

    def test_build_prompt_with_custom_template(self):
        """Test that custom prompt template is returned if provided."""
        # Arrange
        criteria = TrackSelectionCriteria(
            bpm_ranges=[],
            genre_mix={},
            era_distribution={},
            australian_content_min=0.30,
            energy_flow_requirements=[],
            rotation_distribution={},
            no_repeat_window_hours=4.0,
        )
        custom_template = "Custom prompt template for testing"
        request = LLMTrackSelectionRequest(
            playlist_id="550e8400-e29b-41d4-a716-446655440000",
            criteria=criteria,
            target_track_count=12,
            prompt_template=custom_template,
            max_cost_usd=0.10,
        )

        # Act
        result = build_selection_prompt(request)

        # Assert
        assert result == custom_template

    def test_build_default_prompt_with_bpm_ranges(self):
        """Test building default prompt with BPM ranges."""
        # Arrange
        criteria = TrackSelectionCriteria(
            bpm_ranges=[
                BPMRange(
                    time_start=time_obj(6, 0),
                    time_end=time_obj(10, 0),
                    bpm_min=100,
                    bpm_max=130,
                ),
                BPMRange(
                    time_start=time_obj(10, 0),
                    time_end=time_obj(14, 0),
                    bpm_min=110,
                    bpm_max=140,
                ),
            ],
            genre_mix={
                "Electronic": GenreCriteria(target_percentage=0.50, tolerance=0.10),
                "Rock": GenreCriteria(target_percentage=0.30, tolerance=0.10),
            },
            era_distribution={
                "Current": EraCriteria("Current", 2023, 2025, 0.40, 0.10),
                "Recent": EraCriteria("Recent", 2018, 2023, 0.35, 0.10),
            },
            australian_content_min=0.30,
            energy_flow_requirements=["Build energy", "Maintain momentum"],
            rotation_distribution={},
            no_repeat_window_hours=4.0,
        )
        request = LLMTrackSelectionRequest(
            playlist_id="550e8400-e29b-41d4-a716-446655440000",
            criteria=criteria,
            target_track_count=12,
            max_cost_usd=0.10,
        )

        # Act
        result = build_selection_prompt(request)

        # Assert
        assert "100-140 BPM" in result  # min from first range, max from second
        assert "Electronic" in result
        assert "Rock" in result
        assert "30%" in result  # Australian content
        assert "12 tracks" in result
        assert "Build energy" in result

    def test_build_prompt_without_bpm_ranges(self):
        """Test building prompt when no BPM ranges specified."""
        # Arrange
        criteria = TrackSelectionCriteria(
            bpm_ranges=[],
            genre_mix={},
            era_distribution={},
            australian_content_min=0.30,
            energy_flow_requirements=[],
            rotation_distribution={},
            no_repeat_window_hours=4.0,
        )
        request = LLMTrackSelectionRequest(
            playlist_id="550e8400-e29b-41d4-a716-446655440000",
            criteria=criteria,
            target_track_count=10,
            max_cost_usd=0.10,
        )

        # Act
        result = build_selection_prompt(request)

        # Assert
        assert "No BPM constraints" in result
        assert "10 tracks" in result

    def test_build_prompt_without_energy_flow(self):
        """Test building prompt without energy flow requirements."""
        # Arrange
        criteria = TrackSelectionCriteria(
            bpm_ranges=[],
            genre_mix={},
            era_distribution={},
            australian_content_min=0.30,
            energy_flow_requirements=[],
            rotation_distribution={},
            no_repeat_window_hours=4.0,
        )
        request = LLMTrackSelectionRequest(
            playlist_id="550e8400-e29b-41d4-a716-446655440000",
            criteria=criteria,
            target_track_count=12,
            max_cost_usd=0.10,
        )

        # Act
        result = build_selection_prompt(request)

        # Assert
        assert "Natural flow" in result

    def test_build_prompt_includes_mcp_tools(self):
        """Test that prompt includes MCP tool instructions."""
        # Arrange
        criteria = TrackSelectionCriteria(
            bpm_ranges=[],
            genre_mix={},
            era_distribution={},
            australian_content_min=0.30,
            energy_flow_requirements=[],
            rotation_distribution={},
            no_repeat_window_hours=4.0,
        )
        request = LLMTrackSelectionRequest(
            playlist_id="550e8400-e29b-41d4-a716-446655440000",
            criteria=criteria,
            target_track_count=12,
            max_cost_usd=0.10,
        )

        # Act
        result = build_selection_prompt(request)

        # Assert
        assert "search_tracks" in result
        assert "get_genres" in result
        assert "search_similar" in result

    def test_build_prompt_includes_output_format(self):
        """Test that prompt includes JSON output format instructions."""
        # Arrange
        criteria = TrackSelectionCriteria(
            bpm_ranges=[],
            genre_mix={},
            era_distribution={},
            australian_content_min=0.30,
            energy_flow_requirements=[],
            rotation_distribution={},
            no_repeat_window_hours=4.0,
        )
        request = LLMTrackSelectionRequest(
            playlist_id="550e8400-e29b-41d4-a716-446655440000",
            criteria=criteria,
            target_track_count=12,
            max_cost_usd=0.10,
        )

        # Act
        result = build_selection_prompt(request)

        # Assert
        assert "JSON" in result
        assert "tracks:" in result or "tracks" in result
        assert "reasoning" in result


class TestBuildRelaxationPrompt:
    """Tests for build_relaxation_prompt()."""

    def test_build_relaxation_prompt_iteration_0(self):
        """Test relaxation prompt for iteration 0 (strict)."""
        # Arrange
        criteria = TrackSelectionCriteria(
            bpm_ranges=[
                BPMRange(
                    time_start=time_obj(6, 0),
                    time_end=time_obj(10, 0),
                    bpm_min=100,
                    bpm_max=120,
                )
            ],
            genre_mix={
                "Electronic": GenreCriteria(target_percentage=0.50, tolerance=0.10),
            },
            era_distribution={
                "Current": EraCriteria("Current", 2023, 2025, 0.40, 0.10),
            },
            australian_content_min=0.30,
            energy_flow_requirements=[],
            rotation_distribution={},
            no_repeat_window_hours=4.0,
        )

        # Act
        result = build_relaxation_prompt(criteria, iteration=0)

        # Assert
        assert "(Strict criteria)" in result
        assert "NON-NEGOTIABLE" in result  # Australian content
        assert "30%" in result

    def test_build_relaxation_prompt_iteration_1(self):
        """Test relaxation prompt for iteration 1 (BPM relaxed)."""
        # Arrange
        criteria = TrackSelectionCriteria(
            bpm_ranges=[],
            genre_mix={},
            era_distribution={},
            australian_content_min=0.30,
            energy_flow_requirements=[],
            rotation_distribution={},
            no_repeat_window_hours=4.0,
        )

        # Act
        result = build_relaxation_prompt(criteria, iteration=1)

        # Assert
        assert "(BPM relaxed ±10)" in result

    def test_build_relaxation_prompt_iteration_2(self):
        """Test relaxation prompt for iteration 2 (BPM + Genre)."""
        # Arrange
        criteria = TrackSelectionCriteria(
            bpm_ranges=[],
            genre_mix={},
            era_distribution={},
            australian_content_min=0.30,
            energy_flow_requirements=[],
            rotation_distribution={},
            no_repeat_window_hours=4.0,
        )

        # Act
        result = build_relaxation_prompt(criteria, iteration=2)

        # Assert
        assert "(BPM + Genre relaxed)" in result

    def test_build_relaxation_prompt_iteration_3(self):
        """Test relaxation prompt for iteration 3 (full relaxation)."""
        # Arrange
        criteria = TrackSelectionCriteria(
            bpm_ranges=[],
            genre_mix={},
            era_distribution={},
            australian_content_min=0.30,
            energy_flow_requirements=[],
            rotation_distribution={},
            no_repeat_window_hours=4.0,
        )

        # Act
        result = build_relaxation_prompt(criteria, iteration=3)

        # Assert
        assert "(BPM + Genre + Era relaxed)" in result


class TestFormatGenreRequirements:
    """Tests for format_genre_requirements()."""

    def test_format_genre_requirements_with_tuples(self):
        """Test formatting genre requirements with tuple format."""
        # Arrange
        genre_mix = {
            "Electronic": (0.40, 0.60),
            "Rock": (0.20, 0.40),
            "Pop": (0.10, 0.30),
        }

        # Act
        result = format_genre_requirements(genre_mix)

        # Assert
        assert "Electronic: 40%-60%" in result
        assert "Rock: 20%-40%" in result
        assert "Pop: 10%-30%" in result

    def test_format_genre_requirements_empty_dict(self):
        """Test formatting empty genre requirements."""
        # Arrange
        genre_mix = {}

        # Act
        result = format_genre_requirements(genre_mix)

        # Assert
        assert result == ""

    def test_format_genre_requirements_single_genre(self):
        """Test formatting single genre requirement."""
        # Arrange
        genre_mix = {"Electronic": (0.50, 0.70)}

        # Act
        result = format_genre_requirements(genre_mix)

        # Assert
        assert "Electronic: 50%-70%" in result


class TestFormatEraRequirements:
    """Tests for format_era_requirements()."""

    def test_format_era_requirements_with_tuples(self):
        """Test formatting era requirements with tuple format."""
        # Arrange
        era_distribution = {
            "Current": (0.30, 0.50),
            "Recent": (0.25, 0.45),
            "Classic": (0.10, 0.30),
        }

        # Act
        result = format_era_requirements(era_distribution)

        # Assert
        assert "Current: 30%-50%" in result
        assert "Recent: 25%-45%" in result
        assert "Classic: 10%-30%" in result

    def test_format_era_requirements_empty_dict(self):
        """Test formatting empty era requirements."""
        # Arrange
        era_distribution = {}

        # Act
        result = format_era_requirements(era_distribution)

        # Assert
        assert result == ""

    def test_format_era_requirements_single_era(self):
        """Test formatting single era requirement."""
        # Arrange
        era_distribution = {"Current": (0.40, 0.60)}

        # Act
        result = format_era_requirements(era_distribution)

        # Assert
        assert "Current: 40%-60%" in result
