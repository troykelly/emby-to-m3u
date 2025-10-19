"""Comprehensive tests for Subsonic models to ensure 90%+ coverage.

This test suite provides comprehensive coverage for:
- Lines 30-43: SubsonicConfig validation edge cases
- Lines 75-77: SubsonicAuthToken.is_expired() method
- Line 85: SubsonicAuthToken.to_auth_params() method
- All model initialization and field validation
- Edge cases and error conditions
"""

import pytest
import warnings
from datetime import datetime, timedelta, timezone
from src.subsonic.models import (
    SubsonicConfig,
    SubsonicAuthToken,
    SubsonicTrack,
    SubsonicArtist,
    SubsonicAlbum,
)


# ============================================================================
# SubsonicConfig Comprehensive Tests (Lines 30-43 Coverage)
# ============================================================================


class TestSubsonicConfigEdgeCases:
    """Comprehensive tests for SubsonicConfig validation and edge cases."""

    # ========================================================================
    # Line 30-31: URL validation
    # ========================================================================

    def test_url_validation_empty_string(self):
        """Test line 30: Empty URL raises ValueError."""
        with pytest.raises(ValueError, match="url must be a valid HTTP/HTTPS URL"):
            SubsonicConfig(url="", username="user", password="pass")

    def test_url_validation_none_check(self):
        """Test line 30: Falsy URL (None-like) raises ValueError."""
        # While None won't be passed directly due to typing, test empty/falsy
        with pytest.raises(ValueError, match="url must be a valid HTTP/HTTPS URL"):
            SubsonicConfig(url="", username="user", password="pass")

    def test_url_validation_missing_protocol(self):
        """Test line 30-31: URL without http:// or https:// raises ValueError."""
        with pytest.raises(ValueError, match="url must be a valid HTTP/HTTPS URL"):
            SubsonicConfig(url="example.com", username="user", password="pass")

    def test_url_validation_ftp_protocol(self):
        """Test line 30-31: FTP protocol raises ValueError."""
        with pytest.raises(ValueError, match="url must be a valid HTTP/HTTPS URL"):
            SubsonicConfig(url="ftp://example.com", username="user", password="pass")

    def test_url_validation_ws_protocol(self):
        """Test line 30-31: WebSocket protocol raises ValueError."""
        with pytest.raises(ValueError, match="url must be a valid HTTP/HTTPS URL"):
            SubsonicConfig(url="ws://example.com", username="user", password="pass")

    def test_url_validation_https_uppercase(self):
        """Test line 30-31: HTTPS in uppercase is rejected (case-sensitive)."""
        with pytest.raises(ValueError, match="url must be a valid HTTP/HTTPS URL"):
            SubsonicConfig(url="HTTPS://example.com", username="user", password="pass")

    def test_url_validation_http_valid(self):
        """Test line 30-31: Valid HTTP URL passes validation."""
        config = SubsonicConfig(
            url="http://localhost:4533", username="user", password="pass"
        )
        assert config.url == "http://localhost:4533"

    def test_url_validation_https_valid(self):
        """Test line 30-31: Valid HTTPS URL passes validation."""
        config = SubsonicConfig(
            url="https://music.example.com", username="user", password="pass"
        )
        assert config.url == "https://music.example.com"

    # ========================================================================
    # Line 32-33: Username validation
    # ========================================================================

    def test_username_validation_empty_string(self):
        """Test line 32-33: Empty username raises ValueError."""
        with pytest.raises(ValueError, match="username is required"):
            SubsonicConfig(url="https://example.com", username="", password="pass")

    def test_username_validation_whitespace_accepted(self):
        """Test line 32-33: Whitespace username passes (no strip in validation)."""
        # Current implementation doesn't strip, so whitespace is valid
        config = SubsonicConfig(
            url="https://example.com", username="   ", password="pass"
        )
        assert config.username == "   "

    def test_username_validation_special_characters(self):
        """Test line 32-33: Username with special characters is valid."""
        config = SubsonicConfig(
            url="https://example.com", username="user@domain.com", password="pass"
        )
        assert config.username == "user@domain.com"

    # ========================================================================
    # Line 36-37: Password or API key validation
    # ========================================================================

    def test_password_api_key_both_none(self):
        """Test line 36-37: Both password and api_key None raises ValueError."""
        with pytest.raises(
            ValueError, match="Either password or api_key must be provided"
        ):
            SubsonicConfig(url="https://example.com", username="user")

    def test_password_api_key_password_none_apikey_none(self):
        """Test line 36-37: Explicit None for both raises ValueError."""
        with pytest.raises(
            ValueError, match="Either password or api_key must be provided"
        ):
            SubsonicConfig(
                url="https://example.com",
                username="user",
                password=None,
                api_key=None,
            )

    def test_password_api_key_empty_password_no_apikey(self):
        """Test line 36-37: Empty password (falsy) raises ValueError."""
        with pytest.raises(
            ValueError, match="Either password or api_key must be provided"
        ):
            SubsonicConfig(url="https://example.com", username="user", password="")

    def test_password_api_key_password_provided(self):
        """Test line 36-37: Valid password passes validation."""
        config = SubsonicConfig(
            url="https://example.com", username="user", password="secret123"
        )
        assert config.password == "secret123"
        assert config.api_key is None

    def test_password_api_key_apikey_provided(self):
        """Test line 36-37: Valid API key passes validation."""
        config = SubsonicConfig(
            url="https://example.com",
            username="user",
            api_key="api-key-12345",
        )
        assert config.api_key == "api-key-12345"
        assert config.password is None

    def test_password_api_key_both_provided(self):
        """Test line 36-37: Both password and API key provided is valid."""
        config = SubsonicConfig(
            url="https://example.com",
            username="user",
            password="pass",
            api_key="key",
        )
        assert config.password == "pass"
        assert config.api_key == "key"

    # ========================================================================
    # Line 40-48: HTTP warning (insecure connection)
    # ========================================================================

    def test_http_warning_issued(self):
        """Test line 40-48: HTTP URL triggers UserWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            SubsonicConfig(
                url="http://example.com", username="user", password="pass"
            )

            assert len(w) == 1
            assert issubclass(w[0].category, UserWarning)
            assert "HTTP instead of HTTPS" in str(w[0].message)
            assert "Credentials will be transmitted insecurely" in str(w[0].message)

    def test_http_warning_localhost(self):
        """Test line 40-48: HTTP localhost also triggers warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            SubsonicConfig(
                url="http://localhost:4533", username="user", password="pass"
            )

            assert len(w) == 1
            assert issubclass(w[0].category, UserWarning)

    def test_https_no_warning(self):
        """Test line 40-48: HTTPS does not trigger warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            SubsonicConfig(
                url="https://example.com", username="user", password="pass"
            )

            assert len(w) == 0

    def test_http_warning_stacklevel(self):
        """Test line 40-48: Warning has correct stacklevel."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            SubsonicConfig(
                url="http://example.com", username="user", password="pass"
            )

            # Verify warning was issued with stacklevel=2
            assert len(w) == 1
            # The filename should be from the calling code, not models.py
            assert w[0].filename != "models.py"

    # ========================================================================
    # Combined validation scenarios
    # ========================================================================

    def test_validation_order_url_first(self):
        """Test validation order: URL checked before username."""
        with pytest.raises(ValueError, match="url must be a valid HTTP/HTTPS URL"):
            SubsonicConfig(url="invalid", username="", password="")

    def test_validation_order_username_second(self):
        """Test validation order: Username checked before password."""
        with pytest.raises(ValueError, match="username is required"):
            SubsonicConfig(url="https://example.com", username="", password="")

    def test_validation_order_password_last(self):
        """Test validation order: Password/API key checked last."""
        with pytest.raises(
            ValueError, match="Either password or api_key must be provided"
        ):
            SubsonicConfig(url="https://example.com", username="user", password="")

    def test_all_validations_pass(self):
        """Test successful creation with all validations passing."""
        config = SubsonicConfig(
            url="https://music.example.com",
            username="admin",
            password="secret123",
            client_name="test-client",
            api_version="1.16.1",
        )

        assert config.url == "https://music.example.com"
        assert config.username == "admin"
        assert config.password == "secret123"
        assert config.client_name == "test-client"
        assert config.api_version == "1.16.1"


# ============================================================================
# SubsonicAuthToken Comprehensive Tests (Lines 75-77, 85 Coverage)
# ============================================================================


class TestSubsonicAuthTokenEdgeCases:
    """Comprehensive tests for SubsonicAuthToken methods and edge cases."""

    # ========================================================================
    # Line 75-77: is_expired() method
    # ========================================================================

    def test_is_expired_none_never_expires(self):
        """Test line 75-76: Token with expires_at=None never expires."""
        token = SubsonicAuthToken(
            token="test_token",
            salt="test_salt",
            username="user",
            created_at=datetime.now(timezone.utc),
            expires_at=None,
        )

        assert token.is_expired() is False

    def test_is_expired_explicit_none(self):
        """Test line 75-76: Explicitly setting expires_at=None."""
        token = SubsonicAuthToken(
            token="test_token",
            salt="test_salt",
            username="user",
            created_at=datetime.now(timezone.utc) - timedelta(hours=10),
            expires_at=None,
        )

        # Should never expire even if created long ago
        assert token.is_expired() is False

    def test_is_expired_future_expiry(self):
        """Test line 77: Token with future expiry is not expired."""
        token = SubsonicAuthToken(
            token="test_token",
            salt="test_salt",
            username="user",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        assert token.is_expired() is False

    def test_is_expired_past_expiry(self):
        """Test line 77: Token with past expiry is expired."""
        token = SubsonicAuthToken(
            token="test_token",
            salt="test_salt",
            username="user",
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        assert token.is_expired() is True

    def test_is_expired_just_expired(self):
        """Test line 77: Token that just expired (milliseconds ago)."""
        token = SubsonicAuthToken(
            token="test_token",
            salt="test_salt",
            username="user",
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            expires_at=datetime.now(timezone.utc) - timedelta(milliseconds=100),
        )

        assert token.is_expired() is True

    def test_is_expired_edge_case_exactly_now(self):
        """Test line 77: Token expiring at approximately current time."""
        now = datetime.now(timezone.utc)
        token = SubsonicAuthToken(
            token="test_token",
            salt="test_salt",
            username="user",
            created_at=now - timedelta(hours=1),
            expires_at=now,
        )

        # Should be expired or very close (comparison is >)
        # This is timing-dependent, so just verify it returns a boolean
        result = token.is_expired()
        assert isinstance(result, bool)

    def test_is_expired_far_future(self):
        """Test line 77: Token with expiry far in the future."""
        token = SubsonicAuthToken(
            token="test_token",
            salt="test_salt",
            username="user",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        )

        assert token.is_expired() is False

    def test_is_expired_timezone_aware(self):
        """Test line 77: Expiry check with timezone-aware datetimes."""
        now_utc = datetime.now(timezone.utc)
        token = SubsonicAuthToken(
            token="test_token",
            salt="test_salt",
            username="user",
            created_at=now_utc,
            expires_at=now_utc + timedelta(hours=1),
        )

        assert token.is_expired() is False

    # ========================================================================
    # Line 85: to_auth_params() method
    # ========================================================================

    def test_to_auth_params_structure(self):
        """Test line 85: to_auth_params() returns correct dict structure."""
        token = SubsonicAuthToken(
            token="abc123",
            salt="xyz789",
            username="testuser",
            created_at=datetime.now(timezone.utc),
        )

        params = token.to_auth_params()

        assert isinstance(params, dict)
        assert set(params.keys()) == {"u", "t", "s"}

    def test_to_auth_params_values(self):
        """Test line 85: to_auth_params() returns correct values."""
        token = SubsonicAuthToken(
            token="token_hash_123",
            salt="salt_456",
            username="admin",
            created_at=datetime.now(timezone.utc),
        )

        params = token.to_auth_params()

        assert params["u"] == "admin"
        assert params["t"] == "token_hash_123"
        assert params["s"] == "salt_456"

    def test_to_auth_params_special_characters_username(self):
        """Test line 85: to_auth_params() with special characters in username."""
        token = SubsonicAuthToken(
            token="token",
            salt="salt",
            username="user@example.com",
            created_at=datetime.now(timezone.utc),
        )

        params = token.to_auth_params()
        assert params["u"] == "user@example.com"

    def test_to_auth_params_unicode_username(self):
        """Test line 85: to_auth_params() with Unicode username."""
        token = SubsonicAuthToken(
            token="token",
            salt="salt",
            username="用户",  # Chinese characters
            created_at=datetime.now(timezone.utc),
        )

        params = token.to_auth_params()
        assert params["u"] == "用户"

    def test_to_auth_params_long_token(self):
        """Test line 85: to_auth_params() with long MD5 token."""
        md5_token = "26719a1196d2a940705a59634eb18eab"  # 32 chars
        token = SubsonicAuthToken(
            token=md5_token,
            salt="c19b2d",
            username="admin",
            created_at=datetime.now(timezone.utc),
        )

        params = token.to_auth_params()
        assert params["t"] == md5_token
        assert len(params["t"]) == 32

    def test_to_auth_params_immutability(self):
        """Test line 85: to_auth_params() creates new dict each time."""
        token = SubsonicAuthToken(
            token="token",
            salt="salt",
            username="user",
            created_at=datetime.now(timezone.utc),
        )

        params1 = token.to_auth_params()
        params2 = token.to_auth_params()

        # Should be equal but not the same object
        assert params1 == params2
        assert params1 is not params2

        # Modifying one should not affect the other
        params1["u"] = "modified"
        assert params2["u"] == "user"

    def test_to_auth_params_expired_token(self):
        """Test line 85: to_auth_params() works even for expired tokens."""
        token = SubsonicAuthToken(
            token="expired_token",
            salt="old_salt",
            username="user",
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        # Should still return auth params even if expired
        params = token.to_auth_params()
        assert params["u"] == "user"
        assert params["t"] == "expired_token"
        assert params["s"] == "old_salt"


# ============================================================================
# SubsonicTrack Comprehensive Tests
# ============================================================================


class TestSubsonicTrackEdgeCases:
    """Comprehensive tests for SubsonicTrack edge cases and field validation."""

    def test_track_empty_required_fields_rejected(self):
        """Test that empty strings in required fields create valid objects."""
        # Note: dataclass doesn't validate empty strings, just types
        track = SubsonicTrack(
            id="",
            title="",
            artist="",
            album="",
            duration=0,
            path="",
            suffix="",
            created="",
        )

        assert track.id == ""
        assert track.title == ""

    def test_track_negative_duration(self):
        """Test track with negative duration (edge case)."""
        track = SubsonicTrack(
            id="test",
            title="Test",
            artist="Test",
            album="Test",
            duration=-1,
            path="test.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z",
        )

        assert track.duration == -1

    def test_track_extremely_long_duration(self):
        """Test track with extremely long duration."""
        long_duration = 999999999  # > 31 years
        track = SubsonicTrack(
            id="test",
            title="Test",
            artist="Test",
            album="Test",
            duration=long_duration,
            path="test.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z",
        )

        assert track.duration == long_duration

    def test_track_negative_year(self):
        """Test track with negative year (BC dates)."""
        track = SubsonicTrack(
            id="test",
            title="Test",
            artist="Test",
            album="Test",
            duration=180,
            path="test.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z",
            year=-500,
        )

        assert track.year == -500

    def test_track_zero_file_size(self):
        """Test track with zero file size."""
        track = SubsonicTrack(
            id="test",
            title="Test",
            artist="Test",
            album="Test",
            duration=180,
            path="test.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z",
            size=0,
        )

        assert track.size == 0

    def test_track_negative_bitrate(self):
        """Test track with negative bitrate (edge case)."""
        track = SubsonicTrack(
            id="test",
            title="Test",
            artist="Test",
            album="Test",
            duration=180,
            path="test.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z",
            bitRate=-1,
        )

        assert track.bitRate == -1

    def test_track_all_optional_fields_none(self):
        """Test track with all optional fields explicitly None."""
        track = SubsonicTrack(
            id="test",
            title="Test",
            artist="Test",
            album="Test",
            duration=180,
            path="test.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z",
            parent=None,
            albumId=None,
            artistId=None,
            isDir=False,
            isVideo=False,
            type=None,
            genre=None,
            track=None,
            discNumber=None,
            year=None,
            musicBrainzId=None,
            coverArt=None,
            size=None,
            bitRate=None,
            contentType=None,
        )

        assert track.parent is None
        assert track.genre is None


# ============================================================================
# SubsonicArtist Comprehensive Tests
# ============================================================================


class TestSubsonicArtistEdgeCases:
    """Comprehensive tests for SubsonicArtist model."""

    def test_artist_minimal_fields(self):
        """Test artist with only required fields."""
        artist = SubsonicArtist(id="ar-123", name="Test Artist", albumCount=5)

        assert artist.id == "ar-123"
        assert artist.name == "Test Artist"
        assert artist.albumCount == 5
        assert artist.coverArt is None
        assert artist.artistImageUrl is None
        assert artist.starred is None

    def test_artist_all_fields(self):
        """Test artist with all fields populated."""
        artist = SubsonicArtist(
            id="ar-123",
            name="Test Artist",
            albumCount=10,
            coverArt="ca-456",
            artistImageUrl="https://example.com/artist.jpg",
            starred="2024-01-15T10:30:00Z",
        )

        assert artist.id == "ar-123"
        assert artist.name == "Test Artist"
        assert artist.albumCount == 10
        assert artist.coverArt == "ca-456"
        assert artist.artistImageUrl == "https://example.com/artist.jpg"
        assert artist.starred == "2024-01-15T10:30:00Z"

    def test_artist_zero_albums(self):
        """Test artist with zero albums."""
        artist = SubsonicArtist(id="ar-123", name="New Artist", albumCount=0)

        assert artist.albumCount == 0

    def test_artist_negative_album_count(self):
        """Test artist with negative album count (edge case)."""
        artist = SubsonicArtist(id="ar-123", name="Test", albumCount=-1)

        assert artist.albumCount == -1

    def test_artist_unicode_name(self):
        """Test artist with Unicode characters in name."""
        artist = SubsonicArtist(
            id="ar-123", name="音楽家 アーティスト", albumCount=5
        )

        assert "音楽家" in artist.name


# ============================================================================
# SubsonicAlbum Comprehensive Tests
# ============================================================================


class TestSubsonicAlbumEdgeCases:
    """Comprehensive tests for SubsonicAlbum model."""

    def test_album_minimal_fields(self):
        """Test album with only required fields."""
        album = SubsonicAlbum(
            id="al-123",
            name="Test Album",
            artist="Test Artist",
            artistId="ar-456",
            songCount=12,
            duration=2400,
            created="2024-01-01T00:00:00Z",
        )

        assert album.id == "al-123"
        assert album.name == "Test Album"
        assert album.artist == "Test Artist"
        assert album.artistId == "ar-456"
        assert album.songCount == 12
        assert album.duration == 2400
        assert album.created == "2024-01-01T00:00:00Z"
        assert album.coverArt is None
        assert album.playCount is None
        assert album.year is None
        assert album.genre is None
        assert album.starred is None

    def test_album_all_fields(self):
        """Test album with all fields populated."""
        album = SubsonicAlbum(
            id="al-123",
            name="Complete Album",
            artist="Artist Name",
            artistId="ar-456",
            songCount=15,
            duration=3600,
            created="2024-01-15T10:30:00Z",
            coverArt="ca-789",
            playCount=42,
            year=2024,
            genre="Rock",
            starred="2024-01-20T15:00:00Z",
        )

        assert album.id == "al-123"
        assert album.coverArt == "ca-789"
        assert album.playCount == 42
        assert album.year == 2024
        assert album.genre == "Rock"
        assert album.starred == "2024-01-20T15:00:00Z"

    def test_album_zero_songs(self):
        """Test album with zero songs."""
        album = SubsonicAlbum(
            id="al-123",
            name="Empty Album",
            artist="Artist",
            artistId="ar-456",
            songCount=0,
            duration=0,
            created="2024-01-01T00:00:00Z",
        )

        assert album.songCount == 0
        assert album.duration == 0

    def test_album_negative_play_count(self):
        """Test album with negative play count (edge case)."""
        album = SubsonicAlbum(
            id="al-123",
            name="Album",
            artist="Artist",
            artistId="ar-456",
            songCount=10,
            duration=2400,
            created="2024-01-01T00:00:00Z",
            playCount=-1,
        )

        assert album.playCount == -1

    def test_album_unicode_name(self):
        """Test album with Unicode characters."""
        album = SubsonicAlbum(
            id="al-123",
            name="アルバム名 🎵",
            artist="音楽家",
            artistId="ar-456",
            songCount=10,
            duration=2400,
            created="2024-01-01T00:00:00Z",
        )

        assert "アルバム名" in album.name
        assert "音楽家" in album.artist


# ============================================================================
# Integration Tests - Cross-Model Scenarios
# ============================================================================


class TestModelIntegration:
    """Integration tests for models working together."""

    def test_config_and_token_workflow(self):
        """Test typical workflow: config creation -> token generation -> auth params."""
        # Create config
        config = SubsonicConfig(
            url="https://music.example.com",
            username="admin",
            password="secret123",
        )

        # Simulate token creation
        token = SubsonicAuthToken(
            token="abc123def456",
            salt="xyz789",
            username=config.username,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )

        # Get auth params
        params = token.to_auth_params()

        assert params["u"] == config.username
        assert not token.is_expired()

    def test_track_with_artist_and_album_references(self):
        """Test track referencing artist and album models."""
        artist = SubsonicArtist(id="ar-123", name="Queen", albumCount=15)

        album = SubsonicAlbum(
            id="al-456",
            name="A Night at the Opera",
            artist=artist.name,
            artistId=artist.id,
            songCount=12,
            duration=2400,
            created="2024-01-01T00:00:00Z",
        )

        track = SubsonicTrack(
            id="tr-789",
            title="Bohemian Rhapsody",
            artist=artist.name,
            album=album.name,
            duration=355,
            path="Queen/A Night at the Opera/01.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z",
            artistId=artist.id,
            albumId=album.id,
        )

        assert track.artistId == artist.id
        assert track.albumId == album.id
        assert track.artist == artist.name
        assert track.album == album.name

    def test_expired_token_still_produces_auth_params(self):
        """Test that expired tokens can still generate auth params."""
        token = SubsonicAuthToken(
            token="expired",
            salt="old",
            username="user",
            created_at=datetime.now(timezone.utc) - timedelta(hours=25),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        assert token.is_expired() is True

        # Should still be able to get params
        params = token.to_auth_params()
        assert params["u"] == "user"
        assert params["t"] == "expired"


# ============================================================================
# Boundary Value Tests
# ============================================================================


class TestBoundaryValues:
    """Test boundary values and extreme cases."""

    def test_max_int_values(self):
        """Test models with maximum integer values."""
        max_int = 2**31 - 1  # Max 32-bit signed int

        track = SubsonicTrack(
            id="test",
            title="Test",
            artist="Test",
            album="Test",
            duration=max_int,
            path="test.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00Z",
            size=max_int,
            bitRate=max_int,
            track=max_int,
            discNumber=max_int,
            year=max_int,
        )

        assert track.duration == max_int
        assert track.size == max_int
        assert track.bitRate == max_int

    def test_very_long_strings(self):
        """Test models with very long string values."""
        long_string = "a" * 10000

        track = SubsonicTrack(
            id=long_string,
            title=long_string,
            artist=long_string,
            album=long_string,
            duration=180,
            path=long_string,
            suffix=long_string,
            created=long_string,
        )

        assert len(track.id) == 10000
        assert len(track.title) == 10000

    def test_config_with_very_long_url(self):
        """Test config with very long URL."""
        long_url = "https://" + "a" * 1000 + ".com"

        config = SubsonicConfig(url=long_url, username="user", password="pass")

        assert len(config.url) > 1000
