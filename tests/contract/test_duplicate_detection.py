"""Contract tests for duplicate detection (T007-T009)."""
import pytest
from src.azuracast.detection import check_file_exists_by_musicbrainz, check_file_exists_by_metadata, check_file_in_azuracast

class TestMusicBrainz:
    def test_mbid_match(self):
        known = [{"id": "1", "custom_fields": {"musicbrainz_trackid": "abc"}}]
        track = {"ProviderIds": {"MusicBrainzTrack": "abc"}}
        assert check_file_exists_by_musicbrainz(known, track) == "1"
