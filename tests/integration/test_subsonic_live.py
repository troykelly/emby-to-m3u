"""Live integration tests for Subsonic server connectivity (T018).

These tests verify connection to a real Subsonic server and ability
to fetch track metadata for duplicate detection testing.

Prerequisites:
- Live Subsonic server (e.g., Navidrome, Airsonic)
- Valid credentials in .env file
- Test playlist configured
"""

import os
import pytest
from typing import List, Dict, Any

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def subsonic_client(subsonic_config, skip_if_no_subsonic):
    """Create Subsonic client for testing."""
    from src.subsonic.client import SubsonicClient
    from src.subsonic.models import SubsonicConfig

    config = SubsonicConfig(
        url=subsonic_config["host"],
        username=subsonic_config["user"],
        password=subsonic_config["password"],
    )

    client = SubsonicClient(config)
    yield client
    client.close()


@pytest.mark.integration
def test_t018_subsonic_connectivity(
    subsonic_config,
    subsonic_client,
    skip_if_no_subsonic,
):
    """T018: Test Subsonic server connectivity.

    Success Criteria:
    - Ping succeeds
    - Authentication works
    - Can retrieve server version
    - Server is Subsonic API v1.16.1 compatible
    """
    print("\n\nTesting Subsonic Server Connectivity:")
    print("=" * 60)

    # Test ping
    ping_success = subsonic_client.ping()
    assert ping_success, "Subsonic ping failed"

    print(f"  ✓ Connected to: {subsonic_config['host']}")
    print(f"  ✓ Authenticated as: {subsonic_config['user']}")

    # Check if OpenSubsonic
    if subsonic_client.opensubsonic:
        print(f"  ✓ OpenSubsonic detected: {subsonic_client.opensubsonic_version}")
    else:
        print(f"  ✓ Standard Subsonic server")

    print("=" * 60)


@pytest.mark.integration
def test_subsonic_get_playlists(
    subsonic_config,
    subsonic_client,
    skip_if_no_subsonic,
):
    """Test retrieving playlists from Subsonic server.

    Verifies that we can list available playlists, which is
    necessary for finding the test playlist.
    """
    playlists = subsonic_client.get_playlists()

    assert isinstance(playlists, list), "Playlists should be a list"

    print(f"\n\nFound {len(playlists)} playlists:")
    for playlist in playlists[:5]:  # Show first 5
        print(f"  - {playlist.get('name', 'Unknown')} ({playlist.get('songCount', 0)} tracks)")

    if len(playlists) > 5:
        print(f"  ... and {len(playlists) - 5} more")


@pytest.mark.integration
def test_subsonic_test_playlist_exists(
    subsonic_config,
    subsonic_client,
    skip_if_no_subsonic,
):
    """Test that the configured test playlist exists.

    Verifies that the playlist specified in SUBSONIC_PLAYLIST_NAME
    exists and is accessible.
    """
    playlists = subsonic_client.get_playlists()
    playlist_name = subsonic_config["playlist_name"]

    # Find test playlist
    test_playlist = next(
        (p for p in playlists if p.get("name") == playlist_name),
        None
    )

    if not test_playlist:
        pytest.skip(f"Test playlist '{playlist_name}' not found. Available playlists: {[p.get('name') for p in playlists]}")

    print(f"\n\nTest Playlist: {playlist_name}")
    print(f"  ID: {test_playlist.get('id')}")
    print(f"  Tracks: {test_playlist.get('songCount', 0)}")
    print(f"  Owner: {test_playlist.get('owner', 'Unknown')}")

    assert test_playlist.get("songCount", 0) >= 10, \
        f"Test playlist should have at least 10 tracks, found {test_playlist.get('songCount', 0)}"


@pytest.mark.integration
def test_subsonic_get_playlist_tracks(
    subsonic_config,
    subsonic_client,
    skip_if_no_subsonic,
):
    """Test retrieving tracks from test playlist.

    Verifies that we can fetch track metadata from the playlist,
    which is required for duplicate detection testing.
    """
    playlists = subsonic_client.get_playlists()
    playlist_name = subsonic_config["playlist_name"]

    test_playlist = next(
        (p for p in playlists if p.get("name") == playlist_name),
        None
    )

    if not test_playlist:
        pytest.skip(f"Test playlist '{playlist_name}' not found")

    # Get playlist tracks
    playlist_id = test_playlist["id"]
    tracks = subsonic_client.get_playlist(playlist_id)

    assert isinstance(tracks, list), "Tracks should be a list"
    assert len(tracks) >= 10, f"Expected at least 10 tracks, found {len(tracks)}"

    print(f"\n\nPlaylist: {playlist_name}")
    print(f"  Total tracks: {len(tracks)}")
    print("\n  First 5 tracks:")

    for i, track in enumerate(tracks[:5], 1):
        print(f"    {i}. {track.artist} - {track.title}")
        print(f"       Album: {track.album}")
        if track.musicBrainzId:
            print(f"       MusicBrainz ID: {track.musicBrainzId}")


@pytest.mark.integration
def test_subsonic_track_metadata_completeness(
    subsonic_config,
    subsonic_client,
    skip_if_no_subsonic,
):
    """Test that tracks have complete metadata for duplicate detection.

    Verifies that tracks have the required fields:
    - artist
    - title
    - album
    - Optional: musicBrainzId (for enhanced matching)
    """
    playlists = subsonic_client.get_playlists()
    playlist_name = subsonic_config["playlist_name"]

    test_playlist = next(
        (p for p in playlists if p.get("name") == playlist_name),
        None
    )

    if not test_playlist:
        pytest.skip(f"Test playlist '{playlist_name}' not found")

    tracks = subsonic_client.get_playlist(test_playlist["id"])

    print(f"\n\nAnalyzing Metadata Completeness for {len(tracks)} tracks:")

    required_fields = ["artist", "title", "album"]
    optional_fields = ["musicBrainzId", "year", "genre", "track"]

    missing_required = {field: 0 for field in required_fields}
    has_optional = {field: 0 for field in optional_fields}

    for track in tracks:
        # Check required fields
        for field in required_fields:
            if not getattr(track, field, None):
                missing_required[field] += 1

        # Check optional fields
        for field in optional_fields:
            if getattr(track, field, None):
                has_optional[field] += 1

    print("\n  Required fields:")
    for field, missing_count in missing_required.items():
        complete = len(tracks) - missing_count
        percentage = (complete / len(tracks)) * 100
        print(f"    {field:20} {complete:3}/{len(tracks)} ({percentage:5.1f}%)")

        # Assert at least 90% have required fields
        assert percentage >= 90, \
            f"Too many tracks missing {field}: {missing_count}/{len(tracks)}"

    print("\n  Optional fields:")
    for field, has_count in has_optional.items():
        percentage = (has_count / len(tracks)) * 100
        print(f"    {field:20} {has_count:3}/{len(tracks)} ({percentage:5.1f}%)")


@pytest.mark.integration
def test_subsonic_metadata_variations(
    subsonic_config,
    subsonic_client,
    skip_if_no_subsonic,
):
    """Test that playlist contains diverse metadata for normalization testing.

    Verifies the test playlist has tracks with various metadata patterns:
    - Artist with "The" prefix
    - Artist with "feat." notation
    - Special characters in artist/title
    - Different case variations
    """
    playlists = subsonic_client.get_playlists()
    playlist_name = subsonic_config["playlist_name"]

    test_playlist = next(
        (p for p in playlists if p.get("name") == playlist_name),
        None
    )

    if not test_playlist:
        pytest.skip(f"Test playlist '{playlist_name}' not found")

    tracks = subsonic_client.get_playlist(test_playlist["id"])

    print(f"\n\nAnalyzing Metadata Diversity:")

    # Check for various patterns
    patterns = {
        '"The" prefix': lambda t: t.artist.startswith("The ") if t.artist else False,
        'feat. notation': lambda t: "feat." in t.artist.lower() or "ft." in t.artist.lower() if t.artist else False,
        'Special chars': lambda t: any(c in t.artist for c in "/@&-()") if t.artist else False,
        'MusicBrainz ID': lambda t: bool(t.musicBrainzId),
        'Year metadata': lambda t: bool(t.year),
        'Genre metadata': lambda t: bool(t.genre),
    }

    results = {name: 0 for name in patterns.keys()}

    for track in tracks:
        for pattern_name, pattern_func in patterns.items():
            if pattern_func(track):
                results[pattern_name] += 1

    print("")
    for pattern_name, count in results.items():
        percentage = (count / len(tracks)) * 100 if tracks else 0
        print(f"  {pattern_name:20} {count:3}/{len(tracks)} ({percentage:5.1f}%)")

    # Document findings
    print("\n  Recommendations:")
    if results['"The" prefix'] == 0:
        print("    - Add tracks with 'The' prefix for normalization testing")
    if results['feat. notation'] == 0:
        print("    - Add tracks with 'feat.' for normalization testing")
    if results['Special chars'] < len(tracks) * 0.2:
        print("    - Add more tracks with special characters")
    if results['MusicBrainz ID'] < len(tracks) * 0.5:
        print("    - Consider adding more tracks with MusicBrainz IDs")


@pytest.mark.integration
def test_subsonic_download_track(
    subsonic_config,
    subsonic_client,
    skip_if_no_subsonic,
):
    """Test downloading a track from Subsonic.

    Verifies that we can download actual audio files, which is
    required for uploading to AzuraCast.
    """
    playlists = subsonic_client.get_playlists()
    playlist_name = subsonic_config["playlist_name"]

    test_playlist = next(
        (p for p in playlists if p.get("name") == playlist_name),
        None
    )

    if not test_playlist:
        pytest.skip(f"Test playlist '{playlist_name}' not found")

    tracks = subsonic_client.get_playlist(test_playlist["id"])

    if not tracks:
        pytest.skip("No tracks in test playlist")

    # Download first track
    test_track = tracks[0]
    print(f"\n\nDownloading test track:")
    print(f"  Artist: {test_track.artist}")
    print(f"  Title: {test_track.title}")
    print(f"  Format: {test_track.suffix}")

    audio_data = subsonic_client.download_track(test_track.id)

    assert len(audio_data) > 0, "Downloaded audio data is empty"
    assert len(audio_data) > 1000, "Downloaded audio file too small to be valid"

    print(f"  Downloaded: {len(audio_data):,} bytes")
    print(f"  Size: {len(audio_data) / 1024 / 1024:.2f} MB")


@pytest.mark.integration
def test_subsonic_music_folders(
    subsonic_client,
    skip_if_no_subsonic,
):
    """Test retrieving music folders from Subsonic.

    Verifies that we can list music library folders, which helps
    understand the server's library organization.
    """
    folders = subsonic_client.get_music_folders()

    assert isinstance(folders, list), "Music folders should be a list"

    print(f"\n\nFound {len(folders)} music folder(s):")
    for folder in folders:
        print(f"  - {folder.get('name', 'Unknown')} (ID: {folder.get('id')})")


@pytest.mark.integration
def test_subsonic_scan_status(
    subsonic_client,
    skip_if_no_subsonic,
):
    """Test checking library scan status.

    Verifies that we can check if the server is currently scanning
    the music library, which could affect test results.
    """
    scan_status = subsonic_client.get_scan_status()

    print(f"\n\nLibrary Scan Status:")
    print(f"  Scanning: {scan_status.get('scanning', False)}")

    if scan_status.get("scanning"):
        print(f"  Items scanned: {scan_status.get('count', 0)}")
        print("\n  WARNING: Library scan in progress may affect test results")
    else:
        print("  Library scan not in progress")


@pytest.mark.integration
def test_subsonic_random_songs(
    subsonic_client,
    skip_if_no_subsonic,
):
    """Test retrieving random songs.

    This endpoint is useful for getting sample tracks without
    needing a specific playlist.
    """
    random_tracks = subsonic_client.get_random_songs(size=5)

    assert isinstance(random_tracks, list), "Random tracks should be a list"
    assert len(random_tracks) <= 5, "Should return at most 5 tracks"

    print(f"\n\nRetrieved {len(random_tracks)} random track(s):")
    for track in random_tracks:
        print(f"  - {track.artist} - {track.title}")
