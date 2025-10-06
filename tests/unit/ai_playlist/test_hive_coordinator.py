"""
Unit Tests for Hive Coordinator

Tests agent spawning coordination and memory namespace usage.
"""

import pytest
import uuid
from unittest.mock import Mock, patch
from datetime import datetime

from src.ai_playlist.hive_coordinator import spawn_playlist_agents
from src.ai_playlist.models import (
    PlaylistSpec,
    DaypartSpec,
    TrackSelectionCriteria
)


class TestSpawnPlaylistAgents:
    """Test suite for spawn_playlist_agents function."""

    def test_spawn_agents_with_single_spec(self):
        """Test spawning agents with single playlist spec."""
        daypart = DaypartSpec(
            name="Test Show",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Rock": 0.50},
            era_distribution={"Current (0-2 years)": 0.60},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15
        )

        spec = PlaylistSpec(
            id=str(uuid.uuid4()),
            name="Monday_TestPlaylist_0600_1000",
            daypart=daypart,
            track_criteria=TrackSelectionCriteria(
                bpm_range=(90, 130),
                bpm_tolerance=10,
                genre_mix={"Rock": (0.45, 0.55)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.55, 0.65)},
                era_tolerance=0.05,
                australian_min=0.30,
                energy_flow="energetic"
            ),
            target_duration_minutes=240,
            created_at=datetime.now()
        )

        # Should not raise - function just logs coordination strategy
        spawn_playlist_agents([spec])

    def test_spawn_agents_with_multiple_specs(self):
        """Test spawning agents with multiple playlist specs."""
        daypart = DaypartSpec(
            name="Test Show",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Rock": 0.50},
            era_distribution={"Current (0-2 years)": 0.60},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15
        )

        specs = [
            PlaylistSpec(
                id=str(uuid.uuid4()),
                name=f"Monday_TestPlaylist{i}_0600_1000",
                daypart=daypart,
                track_criteria=TrackSelectionCriteria(
                    bpm_range=(90, 130),
                    bpm_tolerance=10,
                    genre_mix={"Rock": (0.45, 0.55)},
                    genre_tolerance=0.05,
                    era_distribution={"Current (0-2 years)": (0.55, 0.65)},
                    era_tolerance=0.05,
                    australian_min=0.30,
                    energy_flow="energetic"
                ),
                target_duration_minutes=240,
                created_at=datetime.now()
            )
            for i in range(5)
        ]

        # Should complete without error
        spawn_playlist_agents(specs)

    def test_spawn_agents_logs_coordination_info(self, caplog):
        """Test agent spawning logs coordination information."""
        import logging
        caplog.set_level(logging.INFO)

        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Rock": 0.50},
            era_distribution={"Current (0-2 years)": 0.60},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15
        )

        specs = [
            PlaylistSpec(
                id=str(uuid.uuid4()),
                name="Monday_TestPlaylist1_0600_1000",
                daypart=daypart,
                track_criteria=TrackSelectionCriteria(
                    bpm_range=(90, 130),
                    bpm_tolerance=10,
                    genre_mix={"Rock": (0.45, 0.55)},
                    genre_tolerance=0.05,
                    era_distribution={"Current (0-2 years)": (0.55, 0.65)},
                    era_tolerance=0.05,
                    australian_min=0.30,
                    energy_flow="energetic"
                ),
                target_duration_minutes=240,
                created_at=datetime.now()
            ),
            PlaylistSpec(
                id=str(uuid.uuid4()),
                name="Monday_TestPlaylist2_0600_1000",
                daypart=daypart,
                track_criteria=TrackSelectionCriteria(
                    bpm_range=(90, 130),
                    bpm_tolerance=10,
                    genre_mix={"Rock": (0.45, 0.55)},
                    genre_tolerance=0.05,
                    era_distribution={"Current (0-2 years)": (0.55, 0.65)},
                    era_tolerance=0.05,
                    australian_min=0.30,
                    energy_flow="energetic"
                ),
                target_duration_minutes=240,
                created_at=datetime.now()
            )
        ]

        spawn_playlist_agents(specs)

        # Verify logging mentions coordination
        assert any("Spawning hive coordination" in record.message for record in caplog.records)
        assert any("ai-playlist/" in record.message for record in caplog.records)

    def test_spawn_agents_handles_empty_list(self):
        """Test spawning agents with empty spec list."""
        # Should not crash with empty list
        spawn_playlist_agents([])

    def test_spawn_agents_logs_phase_information(self, caplog):
        """Test agent spawning logs all coordination phases."""
        import logging
        caplog.set_level(logging.DEBUG)

        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Rock": 0.50},
            era_distribution={"Current (0-2 years)": 0.60},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15
        )

        spec = PlaylistSpec(
            id=str(uuid.uuid4()),
            name="Monday_TestPlaylist_0600_1000",
            daypart=daypart,
            track_criteria=TrackSelectionCriteria(
                bpm_range=(90, 130),
                bpm_tolerance=10,
                genre_mix={"Rock": (0.45, 0.55)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.55, 0.65)},
                era_tolerance=0.05,
                australian_min=0.30,
                energy_flow="energetic"
            ),
            target_duration_minutes=240,
            created_at=datetime.now()
        )

        spawn_playlist_agents([spec])

        # Verify all phases are logged
        messages = [record.message for record in caplog.records]
        assert any("Phase 1" in msg and "parser" in msg for msg in messages)
        assert any("Phase 2" in msg and "planner" in msg for msg in messages)
        assert any("Phase 3" in msg and "selector" in msg for msg in messages)

    def test_spawn_agents_logs_spec_details(self, caplog):
        """Test agent spawning logs details for each spec."""
        import logging
        caplog.set_level(logging.DEBUG)

        daypart = DaypartSpec(
            name="Morning Show",
            day="Tuesday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Rock": 0.50},
            era_distribution={"Current (0-2 years)": 0.60},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15
        )

        spec = PlaylistSpec(
            id=str(uuid.uuid4()),
            name="Tuesday_MorningShow_0600_1000",
            daypart=daypart,
            track_criteria=TrackSelectionCriteria(
                bpm_range=(90, 130),
                bpm_tolerance=10,
                genre_mix={"Rock": (0.45, 0.55)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.55, 0.65)},
                era_tolerance=0.05,
                australian_min=0.30,
                energy_flow="energetic"
            ),
            target_duration_minutes=240,
            created_at=datetime.now()
        )

        spawn_playlist_agents([spec])

        # Verify spec details are logged
        messages = [record.message for record in caplog.records]
        assert any(spec.id in msg for msg in messages)  # Check for actual generated UUID
        assert any("Tuesday_MorningShow_0600_1000" in msg for msg in messages)

    def test_spawn_agents_indicates_mesh_topology(self, caplog):
        """Test agent spawning indicates mesh topology coordination."""
        import logging
        caplog.set_level(logging.DEBUG)

        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Rock": 0.50},
            era_distribution={"Current (0-2 years)": 0.60},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15
        )

        spec = PlaylistSpec(
            id=str(uuid.uuid4()),
            name="Monday_TestMesh_0600_1000",
            daypart=daypart,
            track_criteria=TrackSelectionCriteria(
                bpm_range=(90, 130),
                bpm_tolerance=10,
                genre_mix={"Rock": (0.45, 0.55)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.55, 0.65)},
                era_tolerance=0.05,
                australian_min=0.30,
                energy_flow="energetic"
            ),
            target_duration_minutes=240,
            created_at=datetime.now()
        )

        spawn_playlist_agents([spec])

        # Verify mesh topology is mentioned
        messages = [record.message for record in caplog.records]
        assert any("mesh topology" in msg.lower() for msg in messages)
