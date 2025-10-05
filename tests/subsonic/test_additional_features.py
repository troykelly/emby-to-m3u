"""Unit tests for additional Subsonic API features (search, playlists, cover art, etc)."""

import pytest
from unittest.mock import Mock, patch

from src.subsonic.client import SubsonicClient
from src.subsonic.models import SubsonicConfig, SubsonicTrack


@pytest.fixture
def subsonic_config():
    """Create test Subsonic configuration."""
    return SubsonicConfig(
        url="https://test.example.com",
        username="testuser",
        password="testpass",
    )


@pytest.fixture
def subsonic_client(subsonic_config):
    """Create SubsonicClient with mocked httpx.Client."""
    with patch.object(SubsonicClient, "__init__", lambda x, y, z=None: None):
        client = SubsonicClient.__new__(SubsonicClient)
        client.config = subsonic_config
        client._base_url = subsonic_config.url
        client.opensubsonic = False
        client.opensubsonic_version = None
        client.rate_limit = None
        client._request_times = None
        client.client = Mock()
        yield client


class TestSearch3:
    """Test search3 functionality."""

    def test_search3_success(self, subsonic_client):
        """Test successful search3 query."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "searchResult3": {
                    "artist": [{"id": "1", "name": "The Beatles"}],
                    "album": [{"id": "10", "name": "Abbey Road"}],
                    "song": [
                        {
                            "id": "100",
                            "title": "Come Together",
                            "artist": "The Beatles",
                            "album": "Abbey Road",
                        }
                    ],
                },
            }
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        result = subsonic_client.search3("beatles", artist_count=10, album_count=10, song_count=10)

        assert "searchResult3" in result
        assert len(result["searchResult3"]["artist"]) == 1
        assert len(result["searchResult3"]["album"]) == 1
        assert len(result["searchResult3"]["song"]) == 1


class TestPlaylists:
    """Test playlist functionality."""

    def test_get_playlists_success(self, subsonic_client):
        """Test get_playlists returns playlist list."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "playlists": {
                    "playlist": [
                        {"id": "1", "name": "Favorites", "owner": "testuser", "songCount": 25},
                        {"id": "2", "name": "Rock Classics", "owner": "testuser", "songCount": 50},
                    ]
                },
            }
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        playlists = subsonic_client.get_playlists()

        assert len(playlists) == 2
        assert playlists[0]["name"] == "Favorites"
        assert playlists[1]["name"] == "Rock Classics"

    def test_get_playlists_with_username(self, subsonic_client):
        """Test get_playlists with specific username."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "playlists": {
                    "playlist": [
                        {"id": "3", "name": "User Playlist", "owner": "otheruser", "songCount": 10}
                    ]
                },
            }
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        playlists = subsonic_client.get_playlists(username="otheruser")

        assert len(playlists) == 1
        assert playlists[0]["owner"] == "otheruser"

    def test_get_playlist_success(self, subsonic_client):
        """Test get_playlist returns tracks."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "playlist": {
                    "id": "1",
                    "name": "Favorites",
                    "entry": [
                        {
                            "id": "100",
                            "title": "Song 1",
                            "artist": "Artist 1",
                            "album": "Album 1",
                            "duration": 180,
                            "path": "path1.mp3",
                            "suffix": "mp3",
                            "created": "2023-01-01T00:00:00.000Z",
                        },
                        {
                            "id": "101",
                            "title": "Song 2",
                            "artist": "Artist 2",
                            "album": "Album 2",
                            "duration": 200,
                            "path": "path2.mp3",
                            "suffix": "mp3",
                            "created": "2023-01-01T00:00:00.000Z",
                        },
                    ],
                },
            }
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        tracks = subsonic_client.get_playlist("1")

        assert len(tracks) == 2
        assert all(isinstance(track, SubsonicTrack) for track in tracks)
        assert tracks[0].title == "Song 1"
        assert tracks[1].title == "Song 2"


class TestCoverArt:
    """Test cover art functionality."""

    def test_get_cover_art_success(self, subsonic_client):
        """Test get_cover_art downloads image."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "image/jpeg"}
        mock_response.content = b"fake_image_data"

        subsonic_client.client.get = Mock(return_value=mock_response)
        image_data = subsonic_client.get_cover_art("cover-123")

        assert image_data == b"fake_image_data"

    def test_get_cover_art_with_size(self, subsonic_client):
        """Test get_cover_art with size parameter."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "image/jpeg"}
        mock_response.content = b"fake_resized_image"

        subsonic_client.client.get = Mock(return_value=mock_response)
        image_data = subsonic_client.get_cover_art("cover-123", size=300)

        assert image_data == b"fake_resized_image"

    def test_get_cover_art_error_response(self, subsonic_client):
        """Test get_cover_art handles JSON error response."""
        from src.subsonic.exceptions import SubsonicNotFoundError

        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 70, "message": "Cover art not found"},
            }
        }

        subsonic_client.client.get = Mock(return_value=mock_response)

        with pytest.raises(SubsonicNotFoundError):
            subsonic_client.get_cover_art("invalid-cover")


class TestDownloadTrack:
    """Test download track functionality."""

    def test_download_track_success(self, subsonic_client):
        """Test download_track downloads binary audio."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "audio/mpeg"}
        mock_response.content = b"fake_audio_data"

        subsonic_client.client.get = Mock(return_value=mock_response)
        audio_data = subsonic_client.download_track("track-123")

        assert audio_data == b"fake_audio_data"

    def test_download_track_error_response(self, subsonic_client):
        """Test download_track handles JSON error response."""
        from src.subsonic.exceptions import SubsonicNotFoundError

        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 70, "message": "Track not found"},
            }
        }

        subsonic_client.client.get = Mock(return_value=mock_response)

        with pytest.raises(SubsonicNotFoundError):
            subsonic_client.download_track("invalid-track")


class TestMusicFoldersGenresScan:
    """Test music folders, genres, and scan status."""

    def test_get_music_folders_success(self, subsonic_client):
        """Test get_music_folders returns folder list."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "musicFolders": {
                    "musicFolder": [
                        {"id": "1", "name": "Music"},
                        {"id": "2", "name": "Audiobooks"},
                    ]
                },
            }
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        folders = subsonic_client.get_music_folders()

        assert len(folders) == 2
        assert folders[0]["name"] == "Music"

    def test_get_genres_success(self, subsonic_client):
        """Test get_genres returns genre list."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "genres": {
                    "genre": [
                        {"value": "Rock", "songCount": 1000, "albumCount": 100},
                        {"value": "Jazz", "songCount": 500, "albumCount": 50},
                    ]
                },
            }
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        genres = subsonic_client.get_genres()

        assert len(genres) == 2
        assert genres[0]["value"] == "Rock"

    def test_get_scan_status_scanning(self, subsonic_client):
        """Test get_scan_status when scan in progress."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "scanStatus": {"scanning": True, "count": 1500},
            }
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        status = subsonic_client.get_scan_status()

        assert status["scanning"] is True
        assert status["count"] == 1500

    def test_get_scan_status_idle(self, subsonic_client):
        """Test get_scan_status when no scan in progress."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "scanStatus": {"scanning": False},
            }
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        status = subsonic_client.get_scan_status()

        assert status["scanning"] is False
