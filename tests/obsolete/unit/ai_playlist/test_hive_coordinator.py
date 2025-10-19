"""
Unit Tests for Hive Coordinator

Tests agent spawning coordination and memory namespace usage.
"""

import pytest
import uuid
from unittest.mock import Mock, patch
from datetime import datetime, time

from src.ai_playlist.hive_coordinator import spawn_playlist_agents
from src.ai_playlist.models import (
    ScheduleType,
    BPMRange,
    GenreCriteria,
    EraCriteria,
    PlaylistSpec,
    DaypartSpec,
    TrackSelectionCriteria
)


class TestSpawnPlaylistAgents:
    """Test suite for spawn_playlist_agents function."""

    def test_spawn_agents_with_single_spec(self):
        """Test spawning agents with single playlist spec."""
        daypart = DaypartSpec(
            id="test-daypart-001",
            name="Test Show",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time(6, 0),
            time_end=time(10, 0),
            duration_hours=4.0,
            target_demographic="Test audience",
            bpm_progression=[BPMRange(time(6, 0), time(10, 0), 90, 130)],
            genre_mix={"Alternative": 0.25, "Rock": 0.50, "Pop": 0.25},
            era_distribution={"Current (0-2 years)": 0.40, "Recent (2-5 years)": 0.40, "Modern Classics": 0.20},
            mood_guidelines=["energetic"],
            content_focus="Test programming",
            rotation_percentages={"Power": 0.30, "Medium": 0.40, "Light": 0.30},
            tracks_per_hour=(15, 15),
        )

        spec = PlaylistSpec(
            id=str(uuid.uuid4()),
            name="Monday_TestPlaylist_0600_1000",
            daypart=daypart,
            track_criteria=TrackSelectionCriteria(
            bpm_ranges=[BPMRange(time(0, 0), time(23, 59), 90, 130)],
            genre_mix={
                "Alternative": GenreCriteria(target_percentage=0.25, tolerance=0.05),
            },
            era_distribution={
                "Current (0-2 years)": EraCriteria("Current (0-2 years)", 2023, 2025, 0.40, 0.05),
            },
            australian_content_min=0.30,
            energy_flow_requirements=["energetic"],
            rotation_distribution={"Power": 0.30, "Medium": 0.40, "Light": 0.30},
            no_repeat_window_hours=4.0,
            excluded_track_ids=[],
        ),
            target_duration_minutes=240,
            created_at=datetime.now()
        )

        # Should not raise - function just logs coordination strategy
        spawn_playlist_agents([spec])

    def test_spawn_agents_with_multiple_specs(self):
        """Test spawning agents with multiple playlist specs."""
        daypart = DaypartSpec(
            id="test-daypart-001",
            name="Test Show",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time(6, 0),
            time_end=time(10, 0),
            duration_hours=4.0,
            target_demographic="Test audience",
            bpm_progression=[BPMRange(time(6, 0), time(10, 0), 90, 130)],
            genre_mix={"Alternative": 0.25, "Rock": 0.50, "Pop": 0.25},
            era_distribution={"Current (0-2 years)": 0.40, "Recent (2-5 years)": 0.40, "Modern Classics": 0.20},
            mood_guidelines=["energetic"],
            content_focus="Test programming",
            rotation_percentages={"Power": 0.30, "Medium": 0.40, "Light": 0.30},
            tracks_per_hour=(15, 15),
        )

        specs = [
            PlaylistSpec(
                id=str(uuid.uuid4()),
                name=f"Monday_TestPlaylist{i}_0600_1000",
                daypart=daypart,
                track_criteria=TrackSelectionCriteria(
            bpm_ranges=[BPMRange(time(0, 0), time(23, 59), 90, 130)],
            genre_mix={
                "Alternative": GenreCriteria(target_percentage=0.25, tolerance=0.05),
            },
            era_distribution={
                "Current (0-2 years)": EraCriteria("Current (0-2 years)", 2023, 2025, 0.40, 0.05),
            },
            australian_content_min=0.30,
            energy_flow_requirements=["energetic"],
            rotation_distribution={"Power": 0.30, "Medium": 0.40, "Light": 0.30},
            no_repeat_window_hours=4.0,
            excluded_track_ids=[],
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
            id="test-daypart-001",
            name="Test Show",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time(6, 0),
            time_end=time(10, 0),
            duration_hours=4.0,
            target_demographic="Test audience",
            bpm_progression=[BPMRange(time(6, 0), time(10, 0), 90, 130)],
            genre_mix={"Alternative": 0.25, "Rock": 0.50, "Pop": 0.25},
            era_distribution={"Current (0-2 years)": 0.40, "Recent (2-5 years)": 0.40, "Modern Classics": 0.20},
            mood_guidelines=["energetic"],
            content_focus="Test programming",
            rotation_percentages={"Power": 0.30, "Medium": 0.40, "Light": 0.30},
            tracks_per_hour=(15, 15),
        )

        specs = [
            PlaylistSpec(
                id=str(uuid.uuid4()),
                name="Monday_TestPlaylist1_0600_1000",
                daypart=daypart,
                track_criteria=TrackSelectionCriteria(
            bpm_ranges=[BPMRange(time(0, 0), time(23, 59), 90, 130)],
            genre_mix={
                "Alternative": GenreCriteria(target_percentage=0.25, tolerance=0.05),
            },
            era_distribution={
                "Current (0-2 years)": EraCriteria("Current (0-2 years)", 2023, 2025, 0.40, 0.05),
            },
            australian_content_min=0.30,
            energy_flow_requirements=["energetic"],
            rotation_distribution={"Power": 0.30, "Medium": 0.40, "Light": 0.30},
            no_repeat_window_hours=4.0,
            excluded_track_ids=[],
        ),
                target_duration_minutes=240,
                created_at=datetime.now()
            ),
            PlaylistSpec(
                id=str(uuid.uuid4()),
                name="Monday_TestPlaylist2_0600_1000",
                daypart=daypart,
                track_criteria=TrackSelectionCriteria(
            bpm_ranges=[BPMRange(time(0, 0), time(23, 59), 90, 130)],
            genre_mix={
                "Alternative": GenreCriteria(target_percentage=0.25, tolerance=0.05),
            },
            era_distribution={
                "Current (0-2 years)": EraCriteria("Current (0-2 years)", 2023, 2025, 0.40, 0.05),
            },
            australian_content_min=0.30,
            energy_flow_requirements=["energetic"],
            rotation_distribution={"Power": 0.30, "Medium": 0.40, "Light": 0.30},
            no_repeat_window_hours=4.0,
            excluded_track_ids=[],
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
            id="test-daypart-001",
            name="Test Show",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time(6, 0),
            time_end=time(10, 0),
            duration_hours=4.0,
            target_demographic="Test audience",
            bpm_progression=[BPMRange(time(6, 0), time(10, 0), 90, 130)],
            genre_mix={"Alternative": 0.25, "Rock": 0.50, "Pop": 0.25},
            era_distribution={"Current (0-2 years)": 0.40, "Recent (2-5 years)": 0.40, "Modern Classics": 0.20},
            mood_guidelines=["energetic"],
            content_focus="Test programming",
            rotation_percentages={"Power": 0.30, "Medium": 0.40, "Light": 0.30},
            tracks_per_hour=(15, 15),
        )

        spec = PlaylistSpec(
            id=str(uuid.uuid4()),
            name="Monday_TestPlaylist_0600_1000",
            daypart=daypart,
            track_criteria=TrackSelectionCriteria(
            bpm_ranges=[BPMRange(time(0, 0), time(23, 59), 90, 130)],
            genre_mix={
                "Alternative": GenreCriteria(target_percentage=0.25, tolerance=0.05),
            },
            era_distribution={
                "Current (0-2 years)": EraCriteria("Current (0-2 years)", 2023, 2025, 0.40, 0.05),
            },
            australian_content_min=0.30,
            energy_flow_requirements=["energetic"],
            rotation_distribution={"Power": 0.30, "Medium": 0.40, "Light": 0.30},
            no_repeat_window_hours=4.0,
            excluded_track_ids=[],
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
            id="test-daypart-001",
            name="Test Show",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time(6, 0),
            time_end=time(10, 0),
            duration_hours=4.0,
            target_demographic="Test audience",
            bpm_progression=[BPMRange(time(6, 0), time(10, 0), 90, 130)],
            genre_mix={"Alternative": 0.25, "Rock": 0.50, "Pop": 0.25},
            era_distribution={"Current (0-2 years)": 0.40, "Recent (2-5 years)": 0.40, "Modern Classics": 0.20},
            mood_guidelines=["energetic"],
            content_focus="Test programming",
            rotation_percentages={"Power": 0.30, "Medium": 0.40, "Light": 0.30},
            tracks_per_hour=(15, 15),
        )

        spec = PlaylistSpec(
            id=str(uuid.uuid4()),
            name="Tuesday_MorningShow_0600_1000",
            daypart=daypart,
            track_criteria=TrackSelectionCriteria(
            bpm_ranges=[BPMRange(time(0, 0), time(23, 59), 90, 130)],
            genre_mix={
                "Alternative": GenreCriteria(target_percentage=0.25, tolerance=0.05),
            },
            era_distribution={
                "Current (0-2 years)": EraCriteria("Current (0-2 years)", 2023, 2025, 0.40, 0.05),
            },
            australian_content_min=0.30,
            energy_flow_requirements=["energetic"],
            rotation_distribution={"Power": 0.30, "Medium": 0.40, "Light": 0.30},
            no_repeat_window_hours=4.0,
            excluded_track_ids=[],
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
            id="test-daypart-001",
            name="Test Show",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time(6, 0),
            time_end=time(10, 0),
            duration_hours=4.0,
            target_demographic="Test audience",
            bpm_progression=[BPMRange(time(6, 0), time(10, 0), 90, 130)],
            genre_mix={"Alternative": 0.25, "Rock": 0.50, "Pop": 0.25},
            era_distribution={"Current (0-2 years)": 0.40, "Recent (2-5 years)": 0.40, "Modern Classics": 0.20},
            mood_guidelines=["energetic"],
            content_focus="Test programming",
            rotation_percentages={"Power": 0.30, "Medium": 0.40, "Light": 0.30},
            tracks_per_hour=(15, 15),
        )

        spec = PlaylistSpec(
            id=str(uuid.uuid4()),
            name="Monday_TestMesh_0600_1000",
            daypart=daypart,
            track_criteria=TrackSelectionCriteria(
            bpm_ranges=[BPMRange(time(0, 0), time(23, 59), 90, 130)],
            genre_mix={
                "Alternative": GenreCriteria(target_percentage=0.25, tolerance=0.05),
            },
            era_distribution={
                "Current (0-2 years)": EraCriteria("Current (0-2 years)", 2023, 2025, 0.40, 0.05),
            },
            australian_content_min=0.30,
            energy_flow_requirements=["energetic"],
            rotation_distribution={"Power": 0.30, "Medium": 0.40, "Light": 0.30},
            no_repeat_window_hours=4.0,
            excluded_track_ids=[],
        ),
            target_duration_minutes=240,
            created_at=datetime.now()
        )

        spawn_playlist_agents([spec])

        # Verify mesh topology is mentioned
        messages = [record.message for record in caplog.records]
        assert any("mesh topology" in msg.lower() for msg in messages)
