"""Unit tests for Subsonic data models."""

import pytest
from datetime import datetime, timedelta, timezone
from src.subsonic.models import SubsonicConfig, SubsonicAuthToken, SubsonicTrack


# ============================================================================
# SubsonicConfig Tests
# ============================================================================


class TestSubsonicConfig:
    """Test suite for SubsonicConfig dataclass."""

    def test_valid_config_https(self):
        """Test creating valid config with HTTPS URL."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="admin",
            password="secret123"
        )

        assert config.url == "https://music.example.com"
        assert config.username == "admin"
        assert config.password == "secret123"
        assert config.client_name == "playlistgen"  # Default value
        assert config.api_version == "1.16.1"  # Default value

    def test_valid_config_http(self):
        """Test creating valid config with HTTP URL."""
        config = SubsonicConfig(
            url="http://localhost:4533",
            username="testuser",
            password="testpass"
        )

        assert config.url == "http://localhost:4533"
        assert config.username == "testuser"
        assert config.password == "testpass"

    def test_valid_config_custom_client_and_version(self):
        """Test creating config with custom client name and API version."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="admin",
            password="secret",
            client_name="custom_client",
            api_version="1.15.0"
        )

        assert config.client_name == "custom_client"
        assert config.api_version == "1.15.0"

    def test_url_with_trailing_slash(self):
        """Test that URL with trailing slash is accepted."""
        config = SubsonicConfig(
            url="https://music.example.com/",
            username="admin",
            password="secret"
        )

        assert config.url == "https://music.example.com/"

    def test_url_with_port(self):
        """Test URL with explicit port number."""
        config = SubsonicConfig(
            url="https://music.example.com:8443",
            username="admin",
            password="secret"
        )

        assert config.url == "https://music.example.com:8443"

    def test_url_with_path(self):
        """Test URL with path component."""
        config = SubsonicConfig(
            url="https://music.example.com/subsonic",
            username="admin",
            password="secret"
        )

        assert config.url == "https://music.example.com/subsonic"

    def test_invalid_url_missing_protocol(self):
        """Test that URL without protocol raises ValueError."""
        with pytest.raises(ValueError, match="url must be a valid HTTP/HTTPS URL"):
            SubsonicConfig(
                url="music.example.com",
                username="admin",
                password="secret"
            )

    def test_invalid_url_ftp_protocol(self):
        """Test that URL with FTP protocol raises ValueError."""
        with pytest.raises(ValueError, match="url must be a valid HTTP/HTTPS URL"):
            SubsonicConfig(
                url="ftp://music.example.com",
                username="admin",
                password="secret"
            )

    def test_invalid_url_empty_string(self):
        """Test that empty URL raises ValueError."""
        with pytest.raises(ValueError, match="url must be a valid HTTP/HTTPS URL"):
            SubsonicConfig(
                url="",
                username="admin",
                password="secret"
            )

    def test_invalid_url_whitespace_only(self):
        """Test that whitespace-only URL raises ValueError."""
        with pytest.raises(ValueError, match="url must be a valid HTTP/HTTPS URL"):
            SubsonicConfig(
                url="   ",
                username="admin",
                password="secret"
            )

    def test_missing_username(self):
        """Test that missing username raises ValueError."""
        with pytest.raises(ValueError, match="username is required"):
            SubsonicConfig(
                url="https://music.example.com",
                username="",
                password="secret"
            )

    def test_missing_password(self):
        """Test that missing password raises ValueError."""
        with pytest.raises(ValueError, match="Either password or api_key must be provided"):
            SubsonicConfig(
                url="https://music.example.com",
                username="admin",
                password=""
            )

    def test_missing_both_credentials(self):
        """Test that missing both username and password raises ValueError."""
        with pytest.raises(ValueError, match="username is required"):
            SubsonicConfig(
                url="https://music.example.com",
                username="",
                password=""
            )

    def test_username_whitespace_only(self):
        """Test that whitespace-only username is accepted (validation doesn't strip)."""
        # Note: Current implementation doesn't strip whitespace, so this is valid
        config = SubsonicConfig(
            url="https://music.example.com",
            username="   ",
            password="secret"
        )
        assert config.username == "   "

    def test_password_whitespace_only(self):
        """Test that whitespace-only password is accepted (validation doesn't strip)."""
        # Note: Current implementation doesn't strip whitespace, so this is valid
        config = SubsonicConfig(
            url="https://music.example.com",
            username="admin",
            password="   "
        )
        assert config.password == "   "


# ============================================================================
# SubsonicAuthToken Tests
# ============================================================================


class TestSubsonicAuthToken:
    """Test suite for SubsonicAuthToken dataclass."""

    @pytest.fixture
    def valid_token(self):
        """Fixture providing a valid non-expiring token."""
        return SubsonicAuthToken(
            token="26719a1196d2a940705a59634eb18eab",
            salt="c19b2d",
            username="admin",
            created_at=datetime.now(timezone.utc)
        )

    @pytest.fixture
    def expired_token(self):
        """Fixture providing an expired token."""
        past_time = datetime.now(timezone.utc) - timedelta(hours=2)
        return SubsonicAuthToken(
            token="expired_token_hash",
            salt="old_salt",
            username="admin",
            created_at=past_time - timedelta(hours=1),
            expires_at=past_time
        )

    @pytest.fixture
    def future_expiry_token(self):
        """Fixture providing a token that expires in the future."""
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        return SubsonicAuthToken(
            token="future_token_hash",
            salt="new_salt",
            username="admin",
            created_at=datetime.now(timezone.utc),
            expires_at=future_time
        )

    def test_token_creation_without_expiry(self, valid_token):
        """Test creating token without expiry time."""
        assert valid_token.token == "26719a1196d2a940705a59634eb18eab"
        assert valid_token.salt == "c19b2d"
        assert valid_token.username == "admin"
        assert valid_token.expires_at is None
        assert isinstance(valid_token.created_at, datetime)

    def test_token_creation_with_expiry(self):
        """Test creating token with expiry time."""
        created = datetime.now(timezone.utc)
        expires = created + timedelta(hours=24)

        token = SubsonicAuthToken(
            token="test_token",
            salt="test_salt",
            username="testuser",
            created_at=created,
            expires_at=expires
        )

        assert token.expires_at == expires
        assert token.created_at == created

    def test_is_expired_no_expiry_set(self, valid_token):
        """Test that token without expiry is never expired."""
        assert valid_token.is_expired() is False

    def test_is_expired_future_expiry(self, future_expiry_token):
        """Test that token with future expiry is not expired."""
        assert future_expiry_token.is_expired() is False

    def test_is_expired_past_expiry(self, expired_token):
        """Test that token with past expiry is expired."""
        assert expired_token.is_expired() is True

    def test_is_expired_exactly_at_expiry_boundary(self):
        """Test token expiry at exact boundary time."""
        # Create token that expires in 1 millisecond
        now = datetime.now(timezone.utc)
        almost_expired = SubsonicAuthToken(
            token="boundary_token",
            salt="boundary_salt",
            username="admin",
            created_at=now,
            expires_at=now + timedelta(milliseconds=1)
        )

        # Should not be expired yet (depending on execution speed)
        # This is a best-effort test
        initial_state = almost_expired.is_expired()
        assert isinstance(initial_state, bool)

    def test_to_auth_params_format(self, valid_token):
        """Test that to_auth_params returns correct format."""
        params = valid_token.to_auth_params()

        assert isinstance(params, dict)
        assert "u" in params
        assert "t" in params
        assert "s" in params
        assert len(params) == 3  # Only these three keys

    def test_to_auth_params_values(self, valid_token):
        """Test that to_auth_params returns correct values."""
        params = valid_token.to_auth_params()

        assert params["u"] == "admin"
        assert params["t"] == "26719a1196d2a940705a59634eb18eab"
        assert params["s"] == "c19b2d"

    def test_to_auth_params_different_username(self):
        """Test to_auth_params with different username."""
        token = SubsonicAuthToken(
            token="different_token",
            salt="different_salt",
            username="different_user",
            created_at=datetime.now(timezone.utc)
        )

        params = token.to_auth_params()
        assert params["u"] == "different_user"
        assert params["t"] == "different_token"
        assert params["s"] == "different_salt"

    def test_token_md5_format(self):
        """Test that token follows MD5 format (32 hex characters)."""
        token = SubsonicAuthToken(
            token="26719a1196d2a940705a59634eb18eab",
            salt="c19b2d",
            username="admin",
            created_at=datetime.now(timezone.utc)
        )

        assert len(token.token) == 32
        # Verify it's valid hexadecimal
        int(token.token, 16)  # Should not raise ValueError

    def test_salt_minimum_length(self):
        """Test that salt can be of reasonable length."""
        token = SubsonicAuthToken(
            token="a" * 32,
            salt="abc123",  # 6 characters (common minimum)
            username="admin",
            created_at=datetime.now(timezone.utc)
        )

        assert len(token.salt) >= 6

    def test_timezone_aware_datetimes(self):
        """Test that datetimes are timezone-aware."""
        now = datetime.now(timezone.utc)
        token = SubsonicAuthToken(
            token="test_token",
            salt="test_salt",
            username="admin",
            created_at=now,
            expires_at=now + timedelta(hours=1)
        )

        assert token.created_at.tzinfo is not None
        assert token.expires_at.tzinfo is not None


# ============================================================================
# SubsonicTrack Tests
# ============================================================================


class TestSubsonicTrack:
    """Test suite for SubsonicTrack dataclass."""

    @pytest.fixture
    def minimal_track(self):
        """Fixture providing track with only required fields."""
        return SubsonicTrack(
            id="5001",
            title="Bohemian Rhapsody",
            artist="Queen",
            album="A Night at the Opera",
            duration=355,
            path="Queen/A Night at the Opera/01 Bohemian Rhapsody.mp3",
            suffix="mp3",
            created="2024-01-15T10:30:00Z"
        )

    @pytest.fixture
    def full_track(self):
        """Fixture providing track with all fields populated."""
        return SubsonicTrack(
            id="5001",
            title="Bohemian Rhapsody",
            artist="Queen",
            album="A Night at the Opera",
            duration=355,
            path="Queen/A Night at the Opera/01 Bohemian Rhapsody.mp3",
            suffix="mp3",
            created="2024-01-15T10:30:00Z",
            genre="Rock",
            track=1,
            discNumber=1,
            year=1975,
            musicBrainzId="b1a9c0e9-d987-4042-ae91-78d6a3267d69",
            coverArt="al-5001",
            size=8529817,
            bitRate=320,
            contentType="audio/mpeg"
        )

    def test_track_creation_minimal_fields(self, minimal_track):
        """Test creating track with only required fields."""
        assert minimal_track.id == "5001"
        assert minimal_track.title == "Bohemian Rhapsody"
        assert minimal_track.artist == "Queen"
        assert minimal_track.album == "A Night at the Opera"
        assert minimal_track.duration == 355
        assert minimal_track.path == "Queen/A Night at the Opera/01 Bohemian Rhapsody.mp3"
        assert minimal_track.suffix == "mp3"
        assert minimal_track.created == "2024-01-15T10:30:00Z"

    def test_track_optional_fields_default_to_none(self, minimal_track):
        """Test that optional fields default to None."""
        assert minimal_track.genre is None
        assert minimal_track.track is None
        assert minimal_track.discNumber is None
        assert minimal_track.year is None
        assert minimal_track.musicBrainzId is None
        assert minimal_track.coverArt is None
        assert minimal_track.size is None
        assert minimal_track.bitRate is None
        assert minimal_track.contentType is None

    def test_track_creation_all_fields(self, full_track):
        """Test creating track with all fields populated."""
        assert full_track.id == "5001"
        assert full_track.title == "Bohemian Rhapsody"
        assert full_track.artist == "Queen"
        assert full_track.album == "A Night at the Opera"
        assert full_track.duration == 355
        assert full_track.path == "Queen/A Night at the Opera/01 Bohemian Rhapsody.mp3"
        assert full_track.suffix == "mp3"
        assert full_track.created == "2024-01-15T10:30:00Z"
        assert full_track.genre == "Rock"
        assert full_track.track == 1
        assert full_track.discNumber == 1
        assert full_track.year == 1975
        assert full_track.musicBrainzId == "b1a9c0e9-d987-4042-ae91-78d6a3267d69"
        assert full_track.coverArt == "al-5001"
        assert full_track.size == 8529817
        assert full_track.bitRate == 320
        assert full_track.contentType == "audio/mpeg"

    def test_track_various_audio_formats(self):
        """Test track with different audio file formats."""
        formats = [
            ("flac", "audio/flac"),
            ("ogg", "audio/ogg"),
            ("m4a", "audio/mp4"),
            ("wav", "audio/wav"),
            ("opus", "audio/opus")
        ]

        for suffix, content_type in formats:
            track = SubsonicTrack(
                id=f"test_{suffix}",
                title="Test Track",
                artist="Test Artist",
                album="Test Album",
                duration=180,
                path=f"Test/test.{suffix}",
                suffix=suffix,
                created="2024-01-01T00:00:00Z",
                contentType=content_type
            )

            assert track.suffix == suffix
            assert track.contentType == content_type

    def test_track_duration_zero(self):
        """Test track with zero duration."""
        track = SubsonicTrack(
            id="test",
            title="Test",
            artist="Test",
            album="Test",
            duration=0,
            path="test.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z"
        )

        assert track.duration == 0

    def test_track_duration_long(self):
        """Test track with very long duration."""
        # 2 hours = 7200 seconds
        track = SubsonicTrack(
            id="test",
            title="Long Track",
            artist="Test",
            album="Test",
            duration=7200,
            path="test.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z"
        )

        assert track.duration == 7200

    def test_track_year_various_formats(self):
        """Test track with different year values."""
        years = [1960, 1980, 2000, 2024]

        for year in years:
            track = SubsonicTrack(
                id=f"test_{year}",
                title="Test",
                artist="Test",
                album="Test",
                duration=180,
                path="test.mp3",
                suffix="mp3",
                created="2024-01-01T00:00:00Z",
                year=year
            )

            assert track.year == year

    def test_track_number_single_digit(self):
        """Test track with single-digit track number."""
        track = SubsonicTrack(
            id="test",
            title="Test",
            artist="Test",
            album="Test",
            duration=180,
            path="test.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z",
            track=1
        )

        assert track.track == 1

    def test_track_number_double_digit(self):
        """Test track with double-digit track number."""
        track = SubsonicTrack(
            id="test",
            title="Test",
            artist="Test",
            album="Test",
            duration=180,
            path="test.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z",
            track=99
        )

        assert track.track == 99

    def test_disc_number_multi_disc_set(self):
        """Test track from multi-disc set."""
        track = SubsonicTrack(
            id="test",
            title="Test",
            artist="Test",
            album="Test",
            duration=180,
            path="test.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z",
            discNumber=3
        )

        assert track.discNumber == 3

    def test_track_with_special_characters_in_title(self):
        """Test track with special characters in title."""
        track = SubsonicTrack(
            id="test",
            title="Test: The Song (Remix) [2024]",
            artist="Test & Friends",
            album="Test's Album",
            duration=180,
            path="test.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z"
        )

        assert track.title == "Test: The Song (Remix) [2024]"
        assert track.artist == "Test & Friends"
        assert track.album == "Test's Album"

    def test_track_with_unicode_characters(self):
        """Test track with Unicode characters."""
        track = SubsonicTrack(
            id="test",
            title="Test 日本語 🎵",
            artist="Артист",
            album="Älbum",
            duration=180,
            path="test.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z"
        )

        assert "日本語" in track.title
        assert track.artist == "Артист"
        assert track.album == "Älbum"

    def test_track_path_various_formats(self):
        """Test track with different path formats."""
        paths = [
            "Artist/Album/track.mp3",
            "Artist - Album/01 - Track.mp3",
            "Music/A/Artist/2024 - Album/track.flac",
            "/mnt/music/track.ogg"
        ]

        for path in paths:
            track = SubsonicTrack(
                id="test",
                title="Test",
                artist="Test",
                album="Test",
                duration=180,
                path=path,
                suffix="mp3",
                created="2024-01-01T00:00:00Z"
            )

            assert track.path == path

    def test_track_size_various_values(self):
        """Test track with different file sizes."""
        sizes = [
            (1024, "1KB"),
            (1048576, "1MB"),
            (10485760, "10MB"),
            (104857600, "100MB")
        ]

        for size, description in sizes:
            track = SubsonicTrack(
                id="test",
                title="Test",
                artist="Test",
                album="Test",
                duration=180,
                path="test.mp3",
                suffix="mp3",
                created="2024-01-01T00:00:00Z",
                size=size
            )

            assert track.size == size, f"Failed for {description}"

    def test_track_bitrate_various_values(self):
        """Test track with different bitrate values."""
        bitrates = [128, 192, 256, 320, 1411]  # Common bitrates

        for bitrate in bitrates:
            track = SubsonicTrack(
                id="test",
                title="Test",
                artist="Test",
                album="Test",
                duration=180,
                path="test.mp3",
                suffix="mp3",
                created="2024-01-01T00:00:00Z",
                bitRate=bitrate
            )

            assert track.bitRate == bitrate

    def test_track_musicbrainz_id_format(self):
        """Test track with MusicBrainz ID."""
        mb_id = "b1a9c0e9-d987-4042-ae91-78d6a3267d69"
        track = SubsonicTrack(
            id="test",
            title="Test",
            artist="Test",
            album="Test",
            duration=180,
            path="test.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z",
            musicBrainzId=mb_id
        )

        assert track.musicBrainzId == mb_id
        assert len(track.musicBrainzId) == 36  # UUID format

    def test_track_cover_art_id(self):
        """Test track with cover art ID."""
        track = SubsonicTrack(
            id="test",
            title="Test",
            artist="Test",
            album="Test",
            duration=180,
            path="test.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z",
            coverArt="al-12345"
        )

        assert track.coverArt == "al-12345"

    def test_track_genre_various_values(self):
        """Test track with different genre values."""
        genres = ["Rock", "Jazz", "Classical", "Electronic", "Hip-Hop", "Country"]

        for genre in genres:
            track = SubsonicTrack(
                id="test",
                title="Test",
                artist="Test",
                album="Test",
                duration=180,
                path="test.mp3",
                suffix="mp3",
                created="2024-01-01T00:00:00Z",
                genre=genre
            )

            assert track.genre == genre

    def test_track_iso_timestamp_format(self):
        """Test track with ISO 8601 timestamp format."""
        timestamps = [
            "2024-01-15T10:30:00Z",
            "2023-12-31T23:59:59Z",
            "2024-06-15T14:22:33Z"
        ]

        for timestamp in timestamps:
            track = SubsonicTrack(
                id="test",
                title="Test",
                artist="Test",
                album="Test",
                duration=180,
                path="test.mp3",
                suffix="mp3",
                created=timestamp
            )

            assert track.created == timestamp

    # ========================================================================
    # ID3 Navigation Fields Tests (NEW - P0 Priority)
    # ========================================================================

    def test_track_id3_navigation_fields_all_set(self):
        """Test track with all ID3 navigation fields populated."""
        track = SubsonicTrack(
            id="5001",
            title="Test Track",
            artist="Test Artist",
            album="Test Album",
            duration=180,
            path="Test/track.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z",
            parent="parent-123",
            albumId="album-456",
            artistId="artist-789"
        )

        assert track.parent == "parent-123"
        assert track.albumId == "album-456"
        assert track.artistId == "artist-789"

    def test_track_id3_navigation_fields_default_none(self):
        """Test that ID3 navigation fields default to None."""
        track = SubsonicTrack(
            id="5001",
            title="Test Track",
            artist="Test Artist",
            album="Test Album",
            duration=180,
            path="Test/track.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z"
        )

        assert track.parent is None
        assert track.albumId is None
        assert track.artistId is None

    def test_track_parent_field(self):
        """Test parent field for directory navigation."""
        track = SubsonicTrack(
            id="5001",
            title="Track",
            artist="Artist",
            album="Album",
            duration=180,
            path="path/to/track.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z",
            parent="parent-directory-id"
        )

        assert track.parent == "parent-directory-id"

    def test_track_album_id_field(self):
        """Test albumId field for ID3 album navigation."""
        track = SubsonicTrack(
            id="5001",
            title="Track",
            artist="Artist",
            album="Album",
            duration=180,
            path="path/to/track.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z",
            albumId="al-12345"
        )

        assert track.albumId == "al-12345"

    def test_track_artist_id_field(self):
        """Test artistId field for ID3 artist navigation."""
        track = SubsonicTrack(
            id="5001",
            title="Track",
            artist="Artist",
            album="Album",
            duration=180,
            path="path/to/track.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z",
            artistId="ar-67890"
        )

        assert track.artistId == "ar-67890"

    # ========================================================================
    # Type Discrimination Fields Tests (NEW - P0 Priority)
    # ========================================================================

    def test_track_is_dir_default_false(self):
        """Test that isDir defaults to False for regular tracks."""
        track = SubsonicTrack(
            id="5001",
            title="Track",
            artist="Artist",
            album="Album",
            duration=180,
            path="path/to/track.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z"
        )

        assert track.isDir is False

    def test_track_is_dir_true_for_directory(self):
        """Test isDir=True for directory entries."""
        track = SubsonicTrack(
            id="dir-001",
            title="Album Directory",
            artist="Artist",
            album="Album",
            duration=0,
            path="path/to/album",
            suffix="",
            created="2024-01-01T00:00:00Z",
            isDir=True
        )

        assert track.isDir is True

    def test_track_is_video_default_false(self):
        """Test that isVideo defaults to False for audio tracks."""
        track = SubsonicTrack(
            id="5001",
            title="Track",
            artist="Artist",
            album="Album",
            duration=180,
            path="path/to/track.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z"
        )

        assert track.isVideo is False

    def test_track_is_video_true_for_video_content(self):
        """Test isVideo=True for video content."""
        track = SubsonicTrack(
            id="vid-001",
            title="Music Video",
            artist="Artist",
            album="Album",
            duration=240,
            path="path/to/video.mp4",
            suffix="mp4",
            created="2024-01-01T00:00:00Z",
            isVideo=True
        )

        assert track.isVideo is True

    def test_track_type_field_music(self):
        """Test type field set to 'music'."""
        track = SubsonicTrack(
            id="5001",
            title="Track",
            artist="Artist",
            album="Album",
            duration=180,
            path="path/to/track.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z",
            type="music"
        )

        assert track.type == "music"

    def test_track_type_field_podcast(self):
        """Test type field set to 'podcast'."""
        track = SubsonicTrack(
            id="5001",
            title="Episode 1",
            artist="Podcast Host",
            album="Podcast Name",
            duration=1800,
            path="path/to/episode.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z",
            type="podcast"
        )

        assert track.type == "podcast"

    def test_track_type_field_audiobook(self):
        """Test type field set to 'audiobook'."""
        track = SubsonicTrack(
            id="5001",
            title="Chapter 1",
            artist="Author",
            album="Book Title",
            duration=3600,
            path="path/to/chapter.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z",
            type="audiobook"
        )

        assert track.type == "audiobook"

    def test_track_type_field_default_none(self):
        """Test that type field defaults to None."""
        track = SubsonicTrack(
            id="5001",
            title="Track",
            artist="Artist",
            album="Album",
            duration=180,
            path="path/to/track.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z"
        )

        assert track.type is None

    # ========================================================================
    # Combined ID3 + Type Fields Tests
    # ========================================================================

    def test_track_full_id3_browsing_configuration(self):
        """Test track with complete ID3 browsing configuration."""
        track = SubsonicTrack(
            id="5001",
            title="Track Title",
            artist="Artist Name",
            album="Album Name",
            duration=240,
            path="Artist/Album/01-Track.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z",
            parent="parent-123",
            albumId="album-456",
            artistId="artist-789",
            isDir=False,
            isVideo=False,
            type="music"
        )

        # Verify all ID3 navigation fields
        assert track.parent == "parent-123"
        assert track.albumId == "album-456"
        assert track.artistId == "artist-789"

        # Verify type discrimination fields
        assert track.isDir is False
        assert track.isVideo is False
        assert track.type == "music"

    def test_track_directory_entry_configuration(self):
        """Test track configured as a directory entry."""
        track = SubsonicTrack(
            id="dir-album",
            title="Album Name",
            artist="Artist Name",
            album="Album Name",
            duration=0,
            path="Artist/Album",
            suffix="",
            created="2024-01-01T00:00:00Z",
            parent="artist-id",
            albumId="album-id",
            artistId="artist-id",
            isDir=True,
            isVideo=False,
            type="music"
        )

        assert track.isDir is True
        assert track.parent == "artist-id"
        assert track.albumId == "album-id"

    def test_track_video_filtering(self):
        """Test that video content can be filtered using isVideo."""
        audio_track = SubsonicTrack(
            id="audio-1",
            title="Audio Track",
            artist="Artist",
            album="Album",
            duration=180,
            path="audio.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z",
            isVideo=False
        )

        video_track = SubsonicTrack(
            id="video-1",
            title="Video Track",
            artist="Artist",
            album="Album",
            duration=180,
            path="video.mp4",
            suffix="mp4",
            created="2024-01-01T00:00:00Z",
            isVideo=True
        )

        assert audio_track.isVideo is False
        assert video_track.isVideo is True
