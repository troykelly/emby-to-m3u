"""Unit tests for Subsonic API response parsing and model validation.

Tests response parsing for getArtists, getArtist, getAlbum, getMusicFolders, and getGenres.
"""

import pytest
from unittest.mock import Mock

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
    from unittest.mock import patch

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


class TestGetArtistsResponse:
    """Test getArtists response parsing."""

    def test_parse_artists_response(self, subsonic_client):
        """Test parsing getArtists response with multiple artists."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "artists": {
                    "index": [
                        {
                            "name": "A",
                            "artist": [
                                {
                                    "id": "1",
                                    "name": "ABBA",
                                    "albumCount": 5,
                                    "coverArt": "ar-1",
                                },
                                {
                                    "id": "2",
                                    "name": "AC/DC",
                                    "albumCount": 10,
                                    "coverArt": "ar-2",
                                },
                            ],
                        },
                        {
                            "name": "B",
                            "artist": [
                                {
                                    "id": "3",
                                    "name": "The Beatles",
                                    "albumCount": 12,
                                    "coverArt": "ar-3",
                                    "starred": "2023-01-15T10:30:00.000Z",
                                }
                            ],
                        },
                    ]
                },
            }
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        artists = subsonic_client.get_artists()

        assert len(artists) == 3
        assert artists[0]["name"] == "ABBA"
        assert artists[0]["albumCount"] == 5
        assert artists[1]["name"] == "AC/DC"
        assert artists[2]["name"] == "The Beatles"
        assert "starred" in artists[2]

    def test_parse_empty_artists_response(self, subsonic_client):
        """Test parsing empty getArtists response."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "artists": {"index": []},
            }
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        artists = subsonic_client.get_artists()

        assert len(artists) == 0

    def test_parse_artists_with_music_folder_filter(self, subsonic_client):
        """Test parsing getArtists response with music folder filter."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "artists": {
                    "index": [
                        {
                            "name": "R",
                            "artist": [
                                {
                                    "id": "100",
                                    "name": "Radiohead",
                                    "albumCount": 8,
                                }
                            ],
                        }
                    ]
                },
            }
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        artists = subsonic_client.get_artists(music_folder_id="folder-1")

        assert len(artists) == 1
        assert artists[0]["name"] == "Radiohead"


class TestGetArtistResponse:
    """Test getArtist response with albums."""

    def test_parse_artist_with_albums(self, subsonic_client):
        """Test parsing getArtist response with album array."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "artist": {
                    "id": "1",
                    "name": "The Beatles",
                    "albumCount": 2,
                    "album": [
                        {
                            "id": "10",
                            "name": "Abbey Road",
                            "artist": "The Beatles",
                            "artistId": "1",
                            "coverArt": "al-10",
                            "songCount": 17,
                            "duration": 2829,
                            "created": "2023-01-01T00:00:00.000Z",
                            "year": 1969,
                            "genre": "Rock",
                        },
                        {
                            "id": "11",
                            "name": "Let It Be",
                            "artist": "The Beatles",
                            "artistId": "1",
                            "coverArt": "al-11",
                            "songCount": 12,
                            "duration": 2100,
                            "created": "2023-01-01T00:00:00.000Z",
                            "year": 1970,
                        },
                    ],
                },
            }
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        artist = subsonic_client.get_artist("1")

        assert artist["id"] == "1"
        assert artist["name"] == "The Beatles"
        assert len(artist["album"]) == 2
        assert artist["album"][0]["name"] == "Abbey Road"
        assert artist["album"][0]["year"] == 1969
        assert artist["album"][1]["name"] == "Let It Be"


class TestGetAlbumResponse:
    """Test getAlbum response with songs."""

    def test_parse_album_with_songs(self, subsonic_client):
        """Test parsing getAlbum response with song array."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "album": {
                    "id": "10",
                    "name": "Abbey Road",
                    "artist": "The Beatles",
                    "artistId": "1",
                    "songCount": 3,
                    "song": [
                        {
                            "id": "100",
                            "parent": "10",
                            "albumId": "10",
                            "artistId": "1",
                            "isDir": False,
                            "isVideo": False,
                            "type": "music",
                            "title": "Come Together",
                            "album": "Abbey Road",
                            "artist": "The Beatles",
                            "track": 1,
                            "year": 1969,
                            "genre": "Rock",
                            "coverArt": "al-10",
                            "size": 5242880,
                            "contentType": "audio/mpeg",
                            "suffix": "mp3",
                            "duration": 259,
                            "bitRate": 320,
                            "path": "The Beatles/Abbey Road/01 - Come Together.mp3",
                            "created": "2023-01-01T00:00:00.000Z",
                        },
                        {
                            "id": "101",
                            "parent": "10",
                            "albumId": "10",
                            "artistId": "1",
                            "isDir": False,
                            "isVideo": False,
                            "type": "music",
                            "title": "Something",
                            "album": "Abbey Road",
                            "artist": "The Beatles",
                            "track": 2,
                            "year": 1969,
                            "genre": "Rock",
                            "coverArt": "al-10",
                            "size": 4194304,
                            "contentType": "audio/mpeg",
                            "suffix": "mp3",
                            "duration": 182,
                            "bitRate": 320,
                            "path": "The Beatles/Abbey Road/02 - Something.mp3",
                            "created": "2023-01-01T00:00:00.000Z",
                        },
                        {
                            "id": "102",
                            "parent": "10",
                            "albumId": "10",
                            "artistId": "1",
                            "isDir": False,
                            "isVideo": False,
                            "type": "music",
                            "title": "Here Comes the Sun",
                            "album": "Abbey Road",
                            "artist": "The Beatles",
                            "track": 7,
                            "year": 1969,
                            "genre": "Rock",
                            "coverArt": "al-10",
                            "size": 3145728,
                            "contentType": "audio/mpeg",
                            "suffix": "mp3",
                            "duration": 185,
                            "bitRate": 320,
                            "path": "The Beatles/Abbey Road/07 - Here Comes the Sun.mp3",
                            "created": "2023-01-01T00:00:00.000Z",
                        },
                    ],
                },
            }
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        tracks = subsonic_client.get_album("10")

        assert len(tracks) == 3
        assert all(isinstance(track, SubsonicTrack) for track in tracks)

        # Verify first track
        track = tracks[0]
        assert track.id == "100"
        assert track.title == "Come Together"
        assert track.parent == "10"
        assert track.albumId == "10"
        assert track.artistId == "1"
        assert track.isDir is False
        assert track.isVideo is False
        assert track.type == "music"
        assert track.track == 1
        assert track.duration == 259

    def test_parse_album_filters_video_content(self, subsonic_client):
        """Test that getAlbum filters out video files (isVideo=true)."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "album": {
                    "id": "10",
                    "name": "Album with Video",
                    "songCount": 2,
                    "song": [
                        {
                            "id": "100",
                            "parent": "10",
                            "albumId": "10",
                            "artistId": "1",
                            "isDir": False,
                            "isVideo": False,
                            "type": "music",
                            "title": "Audio Track",
                            "album": "Album with Video",
                            "artist": "Artist",
                            "duration": 180,
                            "path": "Artist/Album/track.mp3",
                            "suffix": "mp3",
                            "created": "2023-01-01T00:00:00.000Z",
                        },
                        {
                            "id": "101",
                            "parent": "10",
                            "albumId": "10",
                            "artistId": "1",
                            "isDir": False,
                            "isVideo": True,  # Video file - should be filtered
                            "type": "video",
                            "title": "Music Video",
                            "album": "Album with Video",
                            "artist": "Artist",
                            "duration": 200,
                            "path": "Artist/Album/video.mp4",
                            "suffix": "mp4",
                            "created": "2023-01-01T00:00:00.000Z",
                        },
                    ],
                },
            }
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        tracks = subsonic_client.get_album("10")

        # Should only have 1 track (video filtered out)
        assert len(tracks) == 1
        assert tracks[0].title == "Audio Track"
        assert tracks[0].isVideo is False


class TestGetMusicFoldersResponse:
    """Test getMusicFolders response parsing."""

    def test_parse_music_folders(self, subsonic_client):
        """Test parsing getMusicFolders response."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "musicFolders": {
                    "musicFolder": [
                        {"id": "1", "name": "Music Library"},
                        {"id": "2", "name": "Audiobooks"},
                        {"id": "3", "name": "Podcasts"},
                    ]
                },
            }
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        folders = subsonic_client.get_music_folders()

        assert len(folders) == 3
        assert folders[0]["name"] == "Music Library"
        assert folders[1]["name"] == "Audiobooks"
        assert folders[2]["name"] == "Podcasts"

    def test_parse_empty_music_folders(self, subsonic_client):
        """Test parsing empty getMusicFolders response."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "musicFolders": {"musicFolder": []},
            }
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        folders = subsonic_client.get_music_folders()

        assert len(folders) == 0


class TestGetGenresResponse:
    """Test getGenres response parsing."""

    def test_parse_genres(self, subsonic_client):
        """Test parsing getGenres response."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "genres": {
                    "genre": [
                        {"value": "Rock", "songCount": 1500, "albumCount": 120},
                        {"value": "Jazz", "songCount": 800, "albumCount": 75},
                        {"value": "Classical", "songCount": 2000, "albumCount": 200},
                    ]
                },
            }
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        genres = subsonic_client.get_genres()

        assert len(genres) == 3
        assert genres[0]["value"] == "Rock"
        assert genres[0]["songCount"] == 1500
        assert genres[1]["value"] == "Jazz"
        assert genres[2]["value"] == "Classical"


class TestSubsonicTrackModel:
    """Test SubsonicTrack model with critical ID3 fields."""

    def test_subsonic_track_with_all_fields(self):
        """Test SubsonicTrack creation with all fields populated."""
        track = SubsonicTrack(
            id="100",
            title="Come Together",
            artist="The Beatles",
            album="Abbey Road",
            duration=259,
            path="The Beatles/Abbey Road/01 - Come Together.mp3",
            suffix="mp3",
            created="2023-01-01T00:00:00.000Z",
            # Critical ID3 fields
            parent="10",
            albumId="10",
            artistId="1",
            isDir=False,
            isVideo=False,
            type="music",
            # Optional fields
            genre="Rock",
            track=1,
            discNumber=1,
            year=1969,
            musicBrainzId="mb-track-id",
            coverArt="al-10",
            size=5242880,
            bitRate=320,
            contentType="audio/mpeg",
        )

        assert track.id == "100"
        assert track.title == "Come Together"
        assert track.parent == "10"
        assert track.albumId == "10"
        assert track.artistId == "1"
        assert track.isDir is False
        assert track.isVideo is False
        assert track.type == "music"

    def test_subsonic_track_with_minimal_fields(self):
        """Test SubsonicTrack creation with only required fields."""
        track = SubsonicTrack(
            id="100",
            title="Test Track",
            artist="Test Artist",
            album="Test Album",
            duration=180,
            path="path/to/track.mp3",
            suffix="mp3",
            created="2023-01-01T00:00:00.000Z",
        )

        assert track.id == "100"
        assert track.title == "Test Track"
        # Optional fields should be None or default
        assert track.parent is None
        assert track.albumId is None
        assert track.artistId is None
        assert track.isDir is False
        assert track.isVideo is False
        assert track.type is None
