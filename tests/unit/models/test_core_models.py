"""
Unit tests for core data models.

Tests cover all core entities from src/ai_playlist/models/core.py:
- StationIdentityDocument
- DaypartSpecification
- TrackSelectionCriteria
- PlaylistSpecification
- SelectedTrack
- Playlist
- DecisionLog
- ConstraintRelaxation
"""

import pytest
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile

from src.ai_playlist.models import (
    ScheduleType,
    ValidationStatus,
    DecisionType,
    BPMRange,
    GenreCriteria,
    EraCriteria,
    StationIdentityDocument,
    DaypartSpecification,
    TrackSelectionCriteria,
    PlaylistSpecification,
    SelectedTrack,
    Playlist,
    DecisionLog,
    ConstraintRelaxation,
)


class TestBPMRange:
    """Tests for BPMRange dataclass."""

    def test_valid_instantiation(self, valid_bpm_range):
        """Test creating valid BPMRange."""
        assert valid_bpm_range.time_start == time(6, 0)
        assert valid_bpm_range.time_end == time(10, 0)
        assert valid_bpm_range.bpm_min == 120
        assert valid_bpm_range.bpm_max == 140

    def test_validate_valid_range(self, valid_bpm_range):
        """Test validation passes for valid range."""
        errors = valid_bpm_range.validate()
        assert errors == []

    def test_validate_min_greater_than_max(self):
        """Test validation fails when min > max."""
        bpm_range = BPMRange(
            time_start=time(6, 0),
            time_end=time(10, 0),
            bpm_min=150,
            bpm_max=120,
        )
        errors = bpm_range.validate()
        assert len(errors) == 1
        assert "min (150) must be < max (120)" in errors[0]

    def test_validate_bpm_out_of_range(self):
        """Test validation fails for BPM outside 60-200."""
        bpm_range = BPMRange(
            time_start=time(6, 0),
            time_end=time(10, 0),
            bpm_min=30,
            bpm_max=250,
        )
        errors = bpm_range.validate()
        assert len(errors) == 2
        assert any("outside valid range 60-200" in e for e in errors)

    def test_validate_min_equals_max(self):
        """Test validation fails when min equals max."""
        bpm_range = BPMRange(
            time_start=time(6, 0),
            time_end=time(10, 0),
            bpm_min=140,
            bpm_max=140,
        )
        errors = bpm_range.validate()
        assert len(errors) == 1
        assert "min (140) must be < max (140)" in errors[0]


class TestGenreCriteria:
    """Tests for GenreCriteria dataclass."""

    def test_valid_instantiation(self, valid_genre_criteria):
        """Test creating valid GenreCriteria."""
        assert valid_genre_criteria.target_percentage == 0.40
        assert valid_genre_criteria.tolerance == 0.10

    def test_min_percentage_calculation(self, valid_genre_criteria):
        """Test min percentage property."""
        assert valid_genre_criteria.min_percentage == pytest.approx(0.30)  # 0.40 - 0.10

    def test_max_percentage_calculation(self, valid_genre_criteria):
        """Test max percentage property."""
        assert valid_genre_criteria.max_percentage == 0.50  # 0.40 + 0.10

    def test_min_percentage_clamped_at_zero(self):
        """Test min percentage doesn't go below 0."""
        criteria = GenreCriteria(target_percentage=0.05, tolerance=0.10)
        assert criteria.min_percentage == 0.0

    def test_max_percentage_clamped_at_one(self):
        """Test max percentage doesn't exceed 1.0."""
        criteria = GenreCriteria(target_percentage=0.95, tolerance=0.10)
        assert criteria.max_percentage == 1.0


class TestEraCriteria:
    """Tests for EraCriteria dataclass."""

    def test_valid_instantiation(self, valid_era_criteria):
        """Test creating valid EraCriteria."""
        assert valid_era_criteria.era_name == "Current"
        assert valid_era_criteria.min_year == 2023
        assert valid_era_criteria.max_year == 2025
        assert valid_era_criteria.target_percentage == 0.30

    def test_min_max_percentage_properties(self, valid_era_criteria):
        """Test min/max percentage properties."""
        assert valid_era_criteria.min_percentage == pytest.approx(0.20)  # 0.30 - 0.10
        assert valid_era_criteria.max_percentage == pytest.approx(0.40)  # 0.30 + 0.10


class TestStationIdentityDocument:
    """Tests for StationIdentityDocument dataclass."""

    def test_from_file_creates_document(self, tmp_path):
        """Test loading document from file."""
        test_file = tmp_path / "station-identity.md"
        test_file.write_text("# Test Station Identity\n\nTest content")

        doc = StationIdentityDocument.from_file(test_file)

        assert doc.document_path == test_file
        assert doc.version is not None  # SHA-256 hash
        assert len(doc.version) == 64  # SHA-256 is 64 hex chars
        assert doc.loaded_at <= datetime.now()
        assert doc.lock_id is None

    def test_acquire_lock_when_unlocked(self, tmp_path):
        """Test acquiring lock when document is unlocked."""
        test_file = tmp_path / "station-identity.md"
        test_file.write_text("Test")

        doc = StationIdentityDocument.from_file(test_file)
        result = doc.acquire_lock("session-123")

        assert result is True
        assert doc.lock_id is not None
        assert doc.locked_by == "session-123"
        assert doc.lock_timestamp <= datetime.now()

    def test_acquire_lock_when_locked(self, tmp_path):
        """Test acquiring lock when already locked."""
        test_file = tmp_path / "station-identity.md"
        test_file.write_text("Test")

        doc = StationIdentityDocument.from_file(test_file)
        doc.acquire_lock("session-123")
        result = doc.acquire_lock("session-456")

        assert result is False
        assert doc.locked_by == "session-123"  # Still locked by first session

    def test_release_lock(self, tmp_path):
        """Test releasing lock."""
        test_file = tmp_path / "station-identity.md"
        test_file.write_text("Test")

        doc = StationIdentityDocument.from_file(test_file)
        doc.acquire_lock("session-123")
        doc.release_lock()

        assert doc.lock_id is None
        assert doc.lock_timestamp is None
        assert doc.locked_by is None

    def test_validate_empty_programming_structures(self, tmp_path):
        """Test validation fails for empty programming structures."""
        test_file = tmp_path / "station-identity.md"
        test_file.write_text("Test")

        doc = StationIdentityDocument.from_file(test_file)
        errors = doc.validate()

        assert "At least one programming structure required" in errors

    def test_validate_australian_content_minimum(self, tmp_path):
        """Test validation fails for low Australian content."""
        test_file = tmp_path / "station-identity.md"
        test_file.write_text("Test")

        doc = StationIdentityDocument.from_file(test_file)
        doc.content_requirements.australian_content_min = 0.20  # Below 30%

        errors = doc.validate()
        assert any("Australian content minimum must be >= 30%" in e for e in errors)


class TestDaypartSpecification:
    """Tests for DaypartSpecification dataclass."""

    def test_valid_instantiation(self, valid_daypart_spec):
        """Test creating valid DaypartSpecification."""
        assert valid_daypart_spec.id == "daypart-001"
        assert valid_daypart_spec.name == "Morning Drive: Production Call"
        assert valid_daypart_spec.schedule_type == ScheduleType.WEEKDAY
        assert valid_daypart_spec.duration_hours == 4.0

    def test_calculate_target_track_count(self, valid_daypart_spec):
        """Test track count calculation."""
        min_tracks, max_tracks = valid_daypart_spec.calculate_target_track_count()
        assert min_tracks == 40  # 4 hours * 10 tracks/hour
        assert max_tracks == 48  # 4 hours * 12 tracks/hour

    def test_get_bpm_range_at_time(self, valid_daypart_spec):
        """Test getting BPM range for specific time."""
        bpm_range = valid_daypart_spec.get_bpm_range_at_time(time(8, 0))
        assert bpm_range is not None
        assert bpm_range.bpm_min == 120
        assert bpm_range.bpm_max == 140

    def test_get_bpm_range_outside_daypart(self, valid_daypart_spec):
        """Test BPM range returns None for time outside daypart."""
        bpm_range = valid_daypart_spec.get_bpm_range_at_time(time(14, 0))
        assert bpm_range is None

    def test_validate_invalid_time_range(self, valid_bpm_range):
        """Test validation fails for end time before start time."""
        daypart = DaypartSpecification(
            id="test",
            name="Test",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time(10, 0),
            time_end=time(6, 0),  # Before start
            duration_hours=4.0,
            target_demographic="Test",
            bpm_progression=[valid_bpm_range],
            genre_mix={"Rock": 1.0},
            era_distribution={"Current": 1.0},
            mood_guidelines=["test"],
            content_focus="Test",
            rotation_percentages={"Power": 1.0},
            tracks_per_hour=(10, 12),
        )

        errors = daypart.validate()
        assert any("End time" in e and "must be after start time" in e for e in errors)

    def test_validate_genre_mix_sum(self, valid_bpm_range):
        """Test validation fails for genre mix not summing to 1.0."""
        daypart = DaypartSpecification(
            id="test",
            name="Test",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time(6, 0),
            time_end=time(10, 0),
            duration_hours=4.0,
            target_demographic="Test",
            bpm_progression=[valid_bpm_range],
            genre_mix={"Rock": 0.40, "Pop": 0.40},  # Sum = 0.80, not 1.0
            era_distribution={"Current": 1.0},
            mood_guidelines=["test"],
            content_focus="Test",
            rotation_percentages={"Power": 1.0},
            tracks_per_hour=(10, 12),
        )

        errors = daypart.validate()
        assert any("Genre mix percentages" in e and "must equal 1.0" in e for e in errors)

    def test_validate_era_distribution_sum(self, valid_bpm_range):
        """Test validation fails for era distribution not summing to 1.0."""
        daypart = DaypartSpecification(
            id="test",
            name="Test",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time(6, 0),
            time_end=time(10, 0),
            duration_hours=4.0,
            target_demographic="Test",
            bpm_progression=[valid_bpm_range],
            genre_mix={"Rock": 1.0},
            era_distribution={"Current": 0.30, "Recent": 0.30},  # Sum = 0.60
            mood_guidelines=["test"],
            content_focus="Test",
            rotation_percentages={"Power": 1.0},
            tracks_per_hour=(10, 12),
        )

        errors = daypart.validate()
        assert any("Era distribution percentages" in e and "must equal 1.0" in e for e in errors)

    def test_validate_tracks_per_hour(self, valid_bpm_range):
        """Test validation for tracks per hour."""
        daypart = DaypartSpecification(
            id="test",
            name="Test",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time(6, 0),
            time_end=time(10, 0),
            duration_hours=4.0,
            target_demographic="Test",
            bpm_progression=[valid_bpm_range],
            genre_mix={"Rock": 1.0},
            era_distribution={"Current": 1.0},
            mood_guidelines=["test"],
            content_focus="Test",
            rotation_percentages={"Power": 1.0},
            tracks_per_hour=(0, 12),  # Min is 0
        )

        errors = daypart.validate()
        assert any("Minimum tracks per hour must be > 0" in e for e in errors)

    def test_validate_max_less_than_min_tracks(self, valid_bpm_range):
        """Test validation fails when max < min tracks per hour."""
        daypart = DaypartSpecification(
            id="test",
            name="Test",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time(6, 0),
            time_end=time(10, 0),
            duration_hours=4.0,
            target_demographic="Test",
            bpm_progression=[valid_bpm_range],
            genre_mix={"Rock": 1.0},
            era_distribution={"Current": 1.0},
            mood_guidelines=["test"],
            content_focus="Test",
            rotation_percentages={"Power": 1.0},
            tracks_per_hour=(12, 10),  # Max < Min
        )

        errors = daypart.validate()
        assert any("Maximum tracks per hour must be >= minimum" in e for e in errors)


class TestTrackSelectionCriteria:
    """Tests for TrackSelectionCriteria dataclass."""

    def test_valid_instantiation(self, valid_track_criteria):
        """Test creating valid TrackSelectionCriteria."""
        assert len(valid_track_criteria.bpm_ranges) == 1
        assert len(valid_track_criteria.genre_mix) == 2
        assert valid_track_criteria.australian_content_min == 0.30

    def test_from_daypart_conversion(self, valid_daypart_spec):
        """Test creating criteria from daypart."""
        criteria = TrackSelectionCriteria.from_daypart(valid_daypart_spec)

        assert len(criteria.bpm_ranges) == len(valid_daypart_spec.bpm_progression)
        assert criteria.australian_content_min == 0.30
        assert criteria.no_repeat_window_hours == valid_daypart_spec.duration_hours

    def test_validate_australian_content_range(self, valid_bpm_range):
        """Test validation for Australian content range."""
        criteria = TrackSelectionCriteria(
            bpm_ranges=[valid_bpm_range],
            genre_mix={"Rock": GenreCriteria(1.0)},
            era_distribution={"Current": EraCriteria("Current", 2023, 2025, 1.0)},
            australian_content_min=0.20,  # Below minimum
            energy_flow_requirements=["test"],
            rotation_distribution={"Power": 1.0},
            no_repeat_window_hours=4.0,
        )

        errors = criteria.validate()
        assert any("Australian content minimum" in e and "must be 0.30-1.0" in e for e in errors)

    def test_validate_negative_no_repeat_window(self, valid_bpm_range):
        """Test validation fails for negative no-repeat window."""
        criteria = TrackSelectionCriteria(
            bpm_ranges=[valid_bpm_range],
            genre_mix={"Rock": GenreCriteria(1.0)},
            era_distribution={"Current": EraCriteria("Current", 2023, 2025, 1.0)},
            australian_content_min=0.30,
            energy_flow_requirements=["test"],
            rotation_distribution={"Power": 1.0},
            no_repeat_window_hours=-1.0,
        )

        errors = criteria.validate()
        assert any("No-repeat window must be >= 0 hours" in e for e in errors)

    def test_validate_genre_mix_sum(self, valid_bpm_range):
        """Test validation for genre mix percentages."""
        criteria = TrackSelectionCriteria(
            bpm_ranges=[valid_bpm_range],
            genre_mix={
                "Rock": GenreCriteria(0.40),
                "Pop": GenreCriteria(0.40),  # Sum = 0.80
            },
            era_distribution={"Current": EraCriteria("Current", 2023, 2025, 1.0)},
            australian_content_min=0.30,
            energy_flow_requirements=["test"],
            rotation_distribution={"Power": 1.0},
            no_repeat_window_hours=4.0,
        )

        errors = criteria.validate()
        assert any("Genre criteria percentages" in e and "must equal 1.0" in e for e in errors)


class TestPlaylistSpecification:
    """Tests for PlaylistSpecification dataclass."""

    def test_valid_instantiation(self, valid_playlist_spec):
        """Test creating valid PlaylistSpecification."""
        assert valid_playlist_spec.id == "playlist-spec-001"
        assert valid_playlist_spec.target_track_count_min == 40
        assert valid_playlist_spec.target_track_count_max == 48
        assert valid_playlist_spec.cost_budget_allocated == Decimal("0.50")

    def test_from_daypart_creation(self, valid_daypart_spec):
        """Test creating playlist spec from daypart."""
        gen_date = date(2025, 1, 15)
        spec = PlaylistSpecification.from_daypart(
            valid_daypart_spec,
            gen_date,
            cost_budget=Decimal("0.50"),
        )

        assert spec.source_daypart_id == valid_daypart_spec.id
        assert spec.generation_date == gen_date
        assert spec.cost_budget_allocated == Decimal("0.50")
        assert "Morning Drive" in spec.name
        assert "2025-01-15" in spec.name

    def test_validate_track_count_minimum(self, valid_daypart_spec, valid_track_criteria):
        """Test validation fails for zero minimum tracks."""
        spec = PlaylistSpecification(
            id="test",
            name="Test",
            source_daypart_id=valid_daypart_spec.id,
            generation_date=date.today(),
            target_duration_minutes=240,
            target_track_count_min=0,  # Invalid
            target_track_count_max=10,
            track_selection_criteria=valid_track_criteria,
            created_at=datetime.now(),
        )

        errors = spec.validate()
        assert any("Minimum track count must be > 0" in e for e in errors)

    def test_validate_max_less_than_min(self, valid_daypart_spec, valid_track_criteria):
        """Test validation fails when max < min tracks."""
        spec = PlaylistSpecification(
            id="test",
            name="Test",
            source_daypart_id=valid_daypart_spec.id,
            generation_date=date.today(),
            target_duration_minutes=240,
            target_track_count_min=50,
            target_track_count_max=40,  # Less than min
            track_selection_criteria=valid_track_criteria,
            created_at=datetime.now(),
        )

        errors = spec.validate()
        assert any("Maximum track count must be >= minimum" in e for e in errors)

    def test_validate_negative_cost_budget(self, valid_daypart_spec, valid_track_criteria):
        """Test validation fails for negative cost budget."""
        spec = PlaylistSpecification(
            id="test",
            name="Test",
            source_daypart_id=valid_daypart_spec.id,
            generation_date=date.today(),
            target_duration_minutes=240,
            target_track_count_min=40,
            target_track_count_max=48,
            track_selection_criteria=valid_track_criteria,
            created_at=datetime.now(),
            cost_budget_allocated=Decimal("-0.10"),
        )

        errors = spec.validate()
        assert any("Cost budget must be > 0 if set" in e for e in errors)


class TestSelectedTrack:
    """Tests for SelectedTrack dataclass."""

    def test_valid_instantiation(self, valid_selected_track):
        """Test creating valid SelectedTrack."""
        assert valid_selected_track.track_id == "track-123"
        assert valid_selected_track.title == "Test Song"
        assert valid_selected_track.is_australian is True
        assert valid_selected_track.validation_status == ValidationStatus.PASS

    def test_validate_against_criteria_pass(self, valid_selected_track, valid_track_criteria):
        """Test validation passes for compliant track."""
        status = valid_selected_track.validate_against_criteria(
            valid_track_criteria,
            time(8, 0),  # Within daypart
        )
        assert status == ValidationStatus.PASS
        assert len(valid_selected_track.validation_notes) == 0

    def test_validate_against_criteria_bpm_out_of_range(self, valid_track_criteria):
        """Test validation fails for BPM out of range."""
        track = SelectedTrack(
            track_id="test",
            title="Test",
            artist="Test",
            album="Test",
            duration_seconds=240,
            is_australian=True,
            rotation_category="Power",
            position_in_playlist=0,
            selection_reasoning="Test",
            validation_status=ValidationStatus.PASS,
            metadata_source="test",
            bpm=200,  # Way out of range (120-140)
            genre="Rock",
            year=2024,
        )

        status = track.validate_against_criteria(valid_track_criteria, time(8, 0))
        assert status == ValidationStatus.FAIL or status == ValidationStatus.WARNING
        assert any("BPM" in note and "outside range" in note for note in track.validation_notes)

    def test_validate_missing_bpm(self, valid_track_criteria):
        """Test validation with missing BPM metadata."""
        track = SelectedTrack(
            track_id="test",
            title="Test",
            artist="Test",
            album="Test",
            duration_seconds=240,
            is_australian=True,
            rotation_category="Power",
            position_in_playlist=0,
            selection_reasoning="Test",
            validation_status=ValidationStatus.PASS,
            metadata_source="test",
            bpm=None,  # Missing
            genre="Rock",
            year=2024,
        )

        status = track.validate_against_criteria(valid_track_criteria, time(8, 0))
        assert any("BPM metadata missing" in note for note in track.validation_notes)

    def test_to_m3u_entry(self, valid_selected_track):
        """Test M3U entry generation."""
        entry = valid_selected_track.to_m3u_entry()
        assert "#EXTINF:240,Test Artist - Test Song" in entry
        assert "track-123" in entry


class TestPlaylist:
    """Tests for Playlist dataclass."""

    def test_create_from_specification(self, valid_playlist_spec):
        """Test creating playlist from specification."""
        playlist = Playlist.create(valid_playlist_spec)

        assert playlist.specification_id == valid_playlist_spec.id
        assert playlist.name == valid_playlist_spec.name
        assert len(playlist.tracks) == 0
        assert playlist.cost_actual == Decimal("0.00")

    def test_add_track(self, valid_playlist, valid_selected_track):
        """Test adding track to playlist."""
        initial_count = len(valid_playlist.tracks)
        new_track = SelectedTrack(
            track_id="track-456",
            title="Another Song",
            artist="Another Artist",
            album="Another Album",
            duration_seconds=200,
            is_australian=False,
            rotation_category="Medium",
            position_in_playlist=0,  # Will be updated
            selection_reasoning="Test",
            validation_status=ValidationStatus.PASS,
            metadata_source="test",
            bpm=135,
            genre="Pop",
            year=2023,
        )

        valid_playlist.add_track(new_track)

        assert len(valid_playlist.tracks) == initial_count + 1
        assert new_track.position_in_playlist == initial_count

    def test_calculate_australian_percentage(self, valid_playlist_spec):
        """Test Australian percentage calculation."""
        playlist = Playlist.create(valid_playlist_spec)

        # Add Australian track
        track1 = SelectedTrack(
            track_id="1", title="T1", artist="A1", album="A1", duration_seconds=240,
            is_australian=True, rotation_category="Power", position_in_playlist=0,
            selection_reasoning="Test", validation_status=ValidationStatus.PASS,
            metadata_source="test",
        )
        # Add non-Australian track
        track2 = SelectedTrack(
            track_id="2", title="T2", artist="A2", album="A2", duration_seconds=240,
            is_australian=False, rotation_category="Power", position_in_playlist=1,
            selection_reasoning="Test", validation_status=ValidationStatus.PASS,
            metadata_source="test",
        )

        playlist.add_track(track1)
        playlist.add_track(track2)

        assert playlist.calculate_australian_percentage() == 0.5

    def test_calculate_genre_distribution(self, valid_playlist_spec):
        """Test genre distribution calculation."""
        playlist = Playlist.create(valid_playlist_spec)

        for i, genre in enumerate(["Rock", "Rock", "Pop"]):
            track = SelectedTrack(
                track_id=str(i), title=f"T{i}", artist=f"A{i}", album=f"A{i}",
                duration_seconds=240, is_australian=True, rotation_category="Power",
                position_in_playlist=i, selection_reasoning="Test",
                validation_status=ValidationStatus.PASS, metadata_source="test",
                genre=genre,
            )
            playlist.add_track(track)

        distribution = playlist.calculate_genre_distribution()
        assert distribution["Rock"] == pytest.approx(2/3)
        assert distribution["Pop"] == pytest.approx(1/3)

    def test_to_m3u_format(self, valid_playlist):
        """Test M3U playlist export."""
        m3u = valid_playlist.to_m3u()

        assert "#EXTM3U" in m3u
        assert f"#PLAYLIST:{valid_playlist.name}" in m3u
        assert "Test Artist - Test Song" in m3u

    def test_validate_empty_playlist(self, valid_playlist_spec):
        """Test validation fails for empty playlist."""
        playlist = Playlist.create(valid_playlist_spec)
        errors = playlist.validate()

        assert any("must contain at least 1 track" in e for e in errors)

    def test_validate_position_gaps(self, valid_playlist_spec):
        """Test validation fails for position gaps."""
        playlist = Playlist.create(valid_playlist_spec)

        track1 = SelectedTrack(
            track_id="1", title="T1", artist="A1", album="A1", duration_seconds=240,
            is_australian=True, rotation_category="Power", position_in_playlist=0,
            selection_reasoning="Test", validation_status=ValidationStatus.PASS,
            metadata_source="test",
        )
        track2 = SelectedTrack(
            track_id="2", title="T2", artist="A2", album="A2", duration_seconds=240,
            is_australian=True, rotation_category="Power", position_in_playlist=2,  # Gap!
            selection_reasoning="Test", validation_status=ValidationStatus.PASS,
            metadata_source="test",
        )

        playlist.tracks = [track1, track2]
        errors = playlist.validate()

        assert any("positions must be sequential" in e for e in errors)


class TestDecisionLog:
    """Tests for DecisionLog dataclass."""

    def test_log_track_selection(self, valid_selected_track):
        """Test creating track selection log."""
        log = DecisionLog.log_track_selection(
            playlist_id="playlist-001",
            track=valid_selected_track,
            criteria_matched=["bpm", "genre"],
            cost=Decimal("0.002"),
            execution_time_ms=150,
        )

        assert log.playlist_id == "playlist-001"
        assert log.decision_type == DecisionType.TRACK_SELECTION
        assert log.cost_incurred == Decimal("0.002")
        assert log.execution_time_ms == 150
        assert log.decision_data["track_id"] == "track-123"

    def test_log_constraint_relaxation(self, valid_constraint_relaxation):
        """Test creating constraint relaxation log."""
        log = DecisionLog.log_constraint_relaxation(
            playlist_id="playlist-001",
            relaxation=valid_constraint_relaxation,
            cost=Decimal("0.001"),
            execution_time_ms=100,
        )

        assert log.decision_type == DecisionType.RELAXATION
        assert log.decision_data["constraint_type"] == "bpm"
        assert log.decision_data["step"] == 1

    def test_log_error(self):
        """Test creating error log."""
        log = DecisionLog.log_error(
            playlist_id="playlist-001",
            error_message="Test error",
            error_type="ValueError",
            traceback="Test traceback",
            cost=Decimal("0.005"),
        )

        assert log.decision_type == DecisionType.ERROR
        assert log.decision_data["error_message"] == "Test error"
        assert log.decision_data["error_type"] == "ValueError"
        assert log.execution_time_ms == 0

    def test_to_dict(self, valid_decision_log):
        """Test dictionary conversion."""
        data = valid_decision_log.to_dict()

        assert "id" in data
        assert "playlist_id" in data
        assert data["decision_type"] == "track_selection"
        assert "timestamp" in data
        assert "decision_data" in data


class TestConstraintRelaxation:
    """Tests for ConstraintRelaxation dataclass."""

    def test_valid_instantiation(self, valid_constraint_relaxation):
        """Test creating valid ConstraintRelaxation."""
        assert valid_constraint_relaxation.step == 1
        assert valid_constraint_relaxation.constraint_type == "bpm"
        assert valid_constraint_relaxation.original_value == "120-140"
        assert valid_constraint_relaxation.relaxed_value == "110-150"
        assert "Insufficient tracks" in valid_constraint_relaxation.reason
