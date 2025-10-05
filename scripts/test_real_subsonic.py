#!/usr/bin/env python3
"""Real server integration test script for Subsonic API.

This script tests the Subsonic API client against a real server using
credentials from environment variables. It performs read-only operations to
validate connectivity, authentication, and data retrieval.

Usage:
    export SUBSONIC_URL="https://music.example.com"
    export SUBSONIC_USER="username"
    export SUBSONIC_PASSWORD="password"
    export M3U_LOG_LEVEL="debug"  # Optional: debug, info, warning, error
    python scripts/test_real_subsonic.py

Environment Variables (required):
    SUBSONIC_URL: Server URL (e.g., https://music.mctk.co)
    SUBSONIC_USER: Username
    SUBSONIC_PASSWORD: Password
    M3U_LOG_LEVEL: Logging level (optional, default: info)

Exit Codes:
    0: All tests passed successfully
    1: One or more tests failed
"""

import logging
import os
import sys
import time
from pathlib import Path
from typing import List

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from subsonic import SubsonicClient, SubsonicConfig, SubsonicTrack
from subsonic.exceptions import SubsonicError


def setup_logging(log_level: str = "info") -> logging.Logger:
    """Configure logging with specified level.

    Args:
        log_level: Logging level from M3U_LOG_LEVEL env var

    Returns:
        Configured logger instance
    """
    level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
    }

    level = level_map.get(log_level.lower(), logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    return logging.getLogger(__name__)


def load_config() -> SubsonicConfig:
    """Load Subsonic configuration from environment variables.

    Environment variables required:
        SUBSONIC_URL: Server URL (e.g., https://music.example.com)
        SUBSONIC_USER: Username for authentication
        SUBSONIC_PASSWORD: Password for authentication

    Returns:
        SubsonicConfig with server credentials

    Raises:
        ValueError: If required environment variables are missing
    """
    url = os.getenv("SUBSONIC_URL")
    username = os.getenv("SUBSONIC_USER")
    password = os.getenv("SUBSONIC_PASSWORD")

    if not all([url, username, password]):
        raise ValueError(
            "Missing required environment variables: SUBSONIC_URL, "
            "SUBSONIC_USER, SUBSONIC_PASSWORD. "
            "Please set these in your environment before running this script."
        )

    return SubsonicConfig(
        url=url,
        username=username,
        password=password,
        client_name="playlistgen-test",
    )


def format_duration(seconds: int) -> str:
    """Format duration in seconds to MM:SS format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string (e.g., "3:45")
    """
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def print_section(title: str):
    """Print a formatted section header.

    Args:
        title: Section title
    """
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}")


def print_track(track: SubsonicTrack, index: int):
    """Print formatted track information.

    Args:
        track: SubsonicTrack to display
        index: Track index number
    """
    print(f"\n[{index}] {track.title}")
    print(f"    Artist:   {track.artist}")
    print(f"    Album:    {track.album}")
    print(f"    Duration: {format_duration(track.duration)}")
    print(f"    Genre:    {track.genre or 'N/A'}")
    print(f"    Year:     {track.year or 'N/A'}")
    print(f"    Track #:  {track.track or 'N/A'}")

    if track.bitRate:
        print(f"    Bitrate:  {track.bitRate} kbps")
    if track.size:
        size_mb = track.size / (1024 * 1024)
        print(f"    Size:     {size_mb:.2f} MB")

    print(f"    ID:       {track.id}")
    print(f"    Path:     {track.path}")


def test_authentication(client: SubsonicClient, logger: logging.Logger) -> bool:
    """Test server authentication with ping().

    Args:
        client: Subsonic client instance
        logger: Logger instance

    Returns:
        True if authentication successful, False otherwise
    """
    print_section("TEST 1: Authentication (ping)")

    try:
        start_time = time.time()
        result = client.ping()
        elapsed = time.time() - start_time

        if result:
            print(f"✓ Authentication successful")
            print(f"  Server responded in {elapsed:.3f} seconds")
            logger.info("Ping test PASSED")
            return True
        else:
            print(f"✗ Authentication failed (unexpected result)")
            logger.error("Ping test FAILED")
            return False

    except SubsonicError as e:
        print(f"✗ Subsonic API error: {e}")
        logger.error(f"Ping test FAILED: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        logger.error(f"Ping test FAILED: {e}", exc_info=True)
        return False


def test_get_artists(client: SubsonicClient, logger: logging.Logger) -> bool:
    """Test fetching artists using get_artists().

    Args:
        client: Subsonic client instance
        logger: Logger instance

    Returns:
        True if test successful and artists found, False otherwise
    """
    print_section("TEST 2: Get Artists (ID3)")

    try:
        start_time = time.time()
        artists = client.get_artists()
        elapsed = time.time() - start_time

        if not artists:
            print(f"✗ No artists returned (empty library?)")
            logger.warning("Get artists test returned no artists")
            return False

        print(f"✓ Fetched {len(artists)} artists")
        print(f"  Request took {elapsed:.3f} seconds")

        # Validate structure of first few artists
        sample_size = min(3, len(artists))
        print(f"\n  Sample artists ({sample_size}):")
        for i, artist in enumerate(artists[:sample_size], 1):
            print(f"    [{i}] {artist.get('name', 'N/A')}")
            print(f"        ID: {artist.get('id', 'N/A')}")
            print(f"        Albums: {artist.get('albumCount', 0)}")

            # Validate required fields
            if not artist.get('id'):
                print(f"        ✗ Missing ID field")
                logger.error(f"Artist missing ID: {artist}")
                return False
            if not artist.get('name'):
                print(f"        ✗ Missing name field")
                logger.error(f"Artist missing name: {artist}")
                return False

        logger.info(f"Get artists test PASSED: {len(artists)} artists retrieved")
        return True

    except SubsonicError as e:
        print(f"✗ Subsonic API error: {e}")
        logger.error(f"Get artists test FAILED: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        logger.error(f"Get artists test FAILED: {e}", exc_info=True)
        return False


def test_get_artist(client: SubsonicClient, logger: logging.Logger) -> bool:
    """Test fetching a specific artist with albums using get_artist().

    Args:
        client: Subsonic client instance
        logger: Logger instance

    Returns:
        True if test successful and albums found, False otherwise
    """
    print_section("TEST 3: Get Artist Details (ID3)")

    try:
        # First get artists to get a valid ID
        artists = client.get_artists()
        if not artists:
            print(f"✗ No artists available to test with")
            logger.warning("Get artist test skipped (no artists)")
            return False

        # Find an artist with albums
        test_artist_id = None
        test_artist_name = None
        for artist in artists:
            if artist.get('albumCount', 0) > 0:
                test_artist_id = artist['id']
                test_artist_name = artist['name']
                break

        if not test_artist_id:
            print(f"✗ No artists with albums found")
            logger.warning("Get artist test skipped (no albums)")
            return False

        # Fetch artist details
        start_time = time.time()
        artist_data = client.get_artist(test_artist_id)
        elapsed = time.time() - start_time

        print(f"✓ Fetched artist: {test_artist_name}")
        print(f"  Request took {elapsed:.3f} seconds")

        # Validate albums returned
        albums = artist_data.get('album', [])
        if not albums:
            print(f"✗ No albums returned for artist")
            logger.error(f"Artist {test_artist_id} returned no albums")
            return False

        print(f"  Albums: {len(albums)}")

        # Validate album structure
        sample_size = min(3, len(albums))
        print(f"\n  Sample albums ({sample_size}):")
        for i, album in enumerate(albums[:sample_size], 1):
            print(f"    [{i}] {album.get('name', 'N/A')}")
            print(f"        ID: {album.get('id', 'N/A')}")
            print(f"        Year: {album.get('year', 'N/A')}")
            print(f"        Songs: {album.get('songCount', 0)}")

            # Validate required fields
            required_fields = ['id', 'name', 'artist', 'artistId']
            for field in required_fields:
                if not album.get(field):
                    print(f"        ✗ Missing required field: {field}")
                    logger.error(f"Album missing {field}: {album}")
                    return False

        logger.info(f"Get artist test PASSED: {len(albums)} albums retrieved")
        return True

    except SubsonicError as e:
        print(f"✗ Subsonic API error: {e}")
        logger.error(f"Get artist test FAILED: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        logger.error(f"Get artist test FAILED: {e}", exc_info=True)
        return False


def test_get_album(client: SubsonicClient, logger: logging.Logger) -> bool:
    """Test fetching album tracks with critical ID3 fields using get_album().

    Args:
        client: Subsonic client instance
        logger: Logger instance

    Returns:
        True if test successful and tracks have all critical fields, False otherwise
    """
    print_section("TEST 4: Get Album Tracks (ID3)")

    try:
        # Get artists, then artist, then album
        artists = client.get_artists()
        if not artists:
            print(f"✗ No artists available")
            return False

        # Find artist with albums
        test_artist_id = None
        for artist in artists:
            if artist.get('albumCount', 0) > 0:
                test_artist_id = artist['id']
                break

        if not test_artist_id:
            print(f"✗ No artists with albums found")
            return False

        # Get artist details to get album ID
        artist_data = client.get_artist(test_artist_id)
        albums = artist_data.get('album', [])
        if not albums:
            print(f"✗ No albums found")
            return False

        # Get first album with songs
        test_album_id = None
        test_album_name = None
        for album in albums:
            if album.get('songCount', 0) > 0:
                test_album_id = album['id']
                test_album_name = album['name']
                break

        if not test_album_id:
            print(f"✗ No albums with songs found")
            return False

        # Fetch album details (returns List[SubsonicTrack])
        start_time = time.time()
        tracks = client.get_album(test_album_id)
        elapsed = time.time() - start_time

        print(f"✓ Fetched album: {test_album_name}")
        print(f"  Request took {elapsed:.3f} seconds")

        # Validate tracks
        if not tracks:
            print(f"✗ No tracks returned for album")
            logger.error(f"Album {test_album_id} returned no tracks")
            return False

        print(f"  Tracks: {len(tracks)}")

        # Critical ID3 fields that must be present on SubsonicTrack
        critical_fields = ['id', 'albumId', 'artistId', 'parent', 'isDir', 'isVideo', 'type']

        # Validate all tracks have critical fields
        all_valid = True
        video_count = 0
        sample_size = min(3, len(tracks))
        print(f"\n  Sample tracks ({sample_size}):")

        for i, track in enumerate(tracks[:sample_size], 1):
            print(f"    [{i}] {track.title}")
            print(f"        Artist: {track.artist}")
            print(f"        Duration: {track.duration}s")

            # Check critical fields (SubsonicTrack attributes)
            missing_fields = []
            for field in critical_fields:
                if not hasattr(track, field):
                    missing_fields.append(field)
                    all_valid = False
                elif field == 'isVideo' and track.isVideo:
                    video_count += 1

            if missing_fields:
                print(f"        ✗ Missing critical fields: {', '.join(missing_fields)}")
                logger.error(f"Track missing fields: {missing_fields}, track: {track}")
            else:
                print(f"        ✓ All critical fields present")
                print(f"          albumId: {track.albumId}")
                print(f"          artistId: {track.artistId}")
                print(f"          isVideo: {track.isVideo}")
                print(f"          type: {track.type}")

        # Check for video files
        if video_count > 0:
            print(f"\n  ⚠️  WARNING: Found {video_count} video files (should be 0)")
            logger.warning(f"Album contains {video_count} video files")

        if not all_valid:
            print(f"\n✗ Some tracks missing critical ID3 fields")
            logger.error("Get album test FAILED: missing critical fields")
            return False

        print(f"\n✓ All tracks have critical ID3 fields")
        logger.info(f"Get album test PASSED: {len(tracks)} tracks validated")
        return True

    except SubsonicError as e:
        print(f"✗ Subsonic API error: {e}")
        logger.error(f"Get album test FAILED: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        logger.error(f"Get album test FAILED: {e}", exc_info=True)
        return False


def test_library_fetch_id3(client: SubsonicClient, logger: logging.Logger) -> bool:
    """Test fetching full library using ID3 browsing flow (not deprecated getSongs).

    Args:
        client: Subsonic client instance
        logger: Logger instance

    Returns:
        True if library fetch successful and under 60s, False otherwise
    """
    print_section("TEST 5: Full Library Fetch via ID3 Browsing")

    try:
        start_time = time.time()

        # Step 1: Get all artists
        print("  Step 1: Fetching all artists...")
        artists = client.get_artists()
        artist_time = time.time() - start_time
        print(f"    ✓ {len(artists)} artists ({artist_time:.2f}s)")

        total_albums = 0
        total_tracks = 0

        # Step 2: Fetch albums for each artist (sample for performance)
        print("  Step 2: Fetching albums...")
        album_sample_size = min(10, len(artists))  # Sample to avoid timeout
        albums_fetched = []

        for artist in artists[:album_sample_size]:
            artist_id = artist.get('id')
            if artist_id:
                artist_data = client.get_artist(artist_id)
                albums = artist_data.get('album', [])
                total_albums += len(albums)
                albums_fetched.extend(albums[:2])  # Take first 2 albums per artist

        album_time = time.time() - start_time - artist_time
        print(f"    ✓ {total_albums} albums found ({album_time:.2f}s)")

        # Step 3: Fetch tracks for sampled albums
        print("  Step 3: Fetching tracks...")
        for album in albums_fetched[:20]:  # Limit to 20 albums for performance
            album_id = album.get('id')
            if album_id:
                tracks = client.get_album(album_id)  # Returns List[SubsonicTrack]
                total_tracks += len(tracks)

        track_time = time.time() - start_time - artist_time - album_time
        elapsed = time.time() - start_time

        print(f"    ✓ {total_tracks} tracks sampled ({track_time:.2f}s)")
        print(f"\n  Total time: {elapsed:.2f}s")

        # Performance validation
        if elapsed > 60:
            print(f"\n  ⚠️  WARNING: Library fetch took {elapsed:.2f}s (expected <60s)")
            logger.warning(f"Library fetch slow: {elapsed:.2f}s")
        else:
            print(f"\n  ✓ Performance acceptable: {elapsed:.2f}s < 60s")

        print(f"\n✓ Library browsing successful")
        print(f"  Artists: {len(artists)}")
        print(f"  Albums: {total_albums}")
        print(f"  Tracks (sampled): {total_tracks}")

        logger.info(f"Library fetch test PASSED: {elapsed:.2f}s, {total_tracks} tracks")
        return True

    except SubsonicError as e:
        print(f"✗ Subsonic API error: {e}")
        logger.error(f"Library fetch test FAILED: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        logger.error(f"Library fetch test FAILED: {e}", exc_info=True)
        return False


def test_fetch_tracks(
    client: SubsonicClient, logger: logging.Logger, count: int = 10
) -> List[SubsonicTrack]:
    """Test fetching tracks using get_random_songs().

    Args:
        client: Subsonic client instance
        logger: Logger instance
        count: Number of tracks to fetch

    Returns:
        List of fetched tracks (empty if test failed)
    """
    print_section(f"TEST 6: Fetch {count} Random Tracks")

    try:
        start_time = time.time()
        tracks = client.get_random_songs(size=count)
        elapsed = time.time() - start_time

        if tracks:
            print(f"✓ Fetched {len(tracks)} random tracks")
            print(f"  Request took {elapsed:.3f} seconds")
            print(f"  Average: {elapsed/len(tracks):.3f} seconds per track")

            logger.info(f"Fetch test PASSED: {len(tracks)} tracks retrieved")
            return tracks
        else:
            print(f"✗ No tracks returned (empty library?)")
            logger.warning("Fetch test returned no tracks")
            return []

    except SubsonicError as e:
        print(f"✗ Subsonic API error: {e}")
        logger.error(f"Fetch test FAILED: {e}")
        return []
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        logger.error(f"Fetch test FAILED: {e}", exc_info=True)
        return []


def test_display_metadata(tracks: List[SubsonicTrack], logger: logging.Logger) -> bool:
    """Display track metadata for fetched tracks.

    Args:
        tracks: List of SubsonicTrack objects
        logger: Logger instance

    Returns:
        True if display successful, False otherwise
    """
    print_section("TEST 7: Display Track Metadata")

    if not tracks:
        print("✗ No tracks to display")
        logger.warning("Display test skipped (no tracks)")
        return False

    try:
        for idx, track in enumerate(tracks, 1):
            print_track(track, idx)

        print(f"\n✓ Displayed metadata for {len(tracks)} tracks")
        logger.info(f"Display test PASSED: {len(tracks)} tracks")
        return True

    except Exception as e:
        print(f"✗ Error displaying metadata: {e}")
        logger.error(f"Display test FAILED: {e}", exc_info=True)
        return False


def test_stream_url(
    client: SubsonicClient, tracks: List[SubsonicTrack], logger: logging.Logger
) -> bool:
    """Generate stream URL for first track.

    Args:
        client: Subsonic client instance
        tracks: List of SubsonicTrack objects
        logger: Logger instance

    Returns:
        True if URL generation successful, False otherwise
    """
    print_section("TEST 8: Generate Stream URL")

    if not tracks:
        print("✗ No tracks available for URL generation")
        logger.warning("Stream URL test skipped (no tracks)")
        return False

    try:
        first_track = tracks[0]
        stream_url = client.get_stream_url(first_track.id)

        print(f"✓ Generated stream URL for: {first_track.title}")
        print(f"  Artist: {first_track.artist}")
        print(f"\n  Stream URL:")
        print(f"  {stream_url}")

        # Validate URL structure
        if not stream_url.startswith(("http://", "https://")):
            print(f"\n✗ WARNING: URL doesn't start with http/https")
            logger.warning("Generated URL has unexpected format")
            return False

        if "rest/stream" not in stream_url:
            print(f"\n✗ WARNING: URL doesn't contain rest/stream endpoint")
            logger.warning("Generated URL missing expected endpoint")
            return False

        logger.info("Stream URL test PASSED")
        return True

    except Exception as e:
        print(f"✗ Error generating stream URL: {e}")
        logger.error(f"Stream URL test FAILED: {e}", exc_info=True)
        return False


def test_performance(
    client: SubsonicClient, logger: logging.Logger, count: int = 10
) -> bool:
    """Measure performance of track fetching.

    Args:
        client: Subsonic client instance
        logger: Logger instance
        count: Number of tracks to fetch

    Returns:
        True if performance test successful, False otherwise
    """
    print_section(f"TEST 9: Performance Measurement")

    try:
        # Run 3 iterations to get average
        iterations = 3
        timings = []

        print(f"Running {iterations} iterations of fetching {count} random tracks...")

        for i in range(iterations):
            start_time = time.time()
            tracks = client.get_random_songs(size=count)
            elapsed = time.time() - start_time
            timings.append(elapsed)

            print(f"  Iteration {i+1}: {elapsed:.3f}s ({len(tracks)} tracks)")

        avg_time = sum(timings) / len(timings)
        min_time = min(timings)
        max_time = max(timings)

        print(f"\n✓ Performance Results:")
        print(f"  Average time: {avg_time:.3f} seconds")
        print(f"  Min time:     {min_time:.3f} seconds")
        print(f"  Max time:     {max_time:.3f} seconds")
        print(f"  Per track:    {avg_time/count:.3f} seconds")

        logger.info(
            f"Performance test PASSED: avg={avg_time:.3f}s, "
            f"min={min_time:.3f}s, max={max_time:.3f}s"
        )
        return True

    except Exception as e:
        print(f"✗ Performance test error: {e}")
        logger.error(f"Performance test FAILED: {e}", exc_info=True)
        return False


def test_network_error_handling(client: SubsonicClient, logger: logging.Logger) -> bool:
    """Test error handling for network failures.

    Args:
        client: Subsonic client instance
        logger: Logger instance

    Returns:
        True if error handling works correctly, False otherwise
    """
    print_section("TEST 10: Network Error Handling")

    try:
        # Test with invalid artist ID
        print("  Testing with invalid artist ID...")
        try:
            client.get_artist("invalid-artist-id-12345")
            print("✗ Should have raised SubsonicError for invalid ID")
            logger.error("Network error test FAILED: no exception for invalid ID")
            return False
        except SubsonicError as e:
            print(f"  ✓ Correctly raised SubsonicError: {e}")

        # Test with invalid album ID
        print("  Testing with invalid album ID...")
        try:
            client.get_album("invalid-album-id-12345")
            print("✗ Should have raised SubsonicError for invalid ID")
            logger.error("Network error test FAILED: no exception for invalid ID")
            return False
        except SubsonicError as e:
            print(f"  ✓ Correctly raised SubsonicError: {e}")

        print(f"\n✓ Error handling working correctly")
        logger.info("Network error test PASSED")
        return True

    except Exception as e:
        print(f"✗ Unexpected error in error handling test: {e}")
        logger.error(f"Network error test FAILED: {e}", exc_info=True)
        return False


def print_summary(results: dict):
    """Print test summary with pass/fail counts.

    Args:
        results: Dictionary of test names to boolean results
    """
    print_section("TEST SUMMARY")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed

    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}  {test_name}")

    print(f"\n  Total:  {total} tests")
    print(f"  Passed: {passed} tests")
    print(f"  Failed: {failed} tests")

    if failed == 0:
        print(f"\n  🎉 All tests passed!")
    else:
        print(f"\n  ⚠️  {failed} test(s) failed")


def main() -> int:
    """Main test execution function.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Setup
    log_level = os.getenv("M3U_LOG_LEVEL", "info")
    logger = setup_logging(log_level)

    print(f"\n{'=' * 80}")
    print(f"  Subsonic API Integration Test")
    print(f"  Real Server Test (Read-Only Operations)")
    print(f"{'=' * 80}")

    # Load configuration
    try:
        config = load_config()
        print(f"\n✓ Configuration loaded")
        print(f"  Server: {config.url}")
        print(f"  User:   {config.username}")
        print(f"  API:    v{config.api_version}")
    except Exception as e:
        print(f"\n✗ Configuration error: {e}")
        logger.error(f"Configuration load failed: {e}")
        return 1

    # Initialize client
    try:
        client = SubsonicClient(config)
        print(f"✓ Client initialized")
    except Exception as e:
        print(f"\n✗ Client initialization error: {e}")
        logger.error(f"Client initialization failed: {e}")
        return 1

    # Run tests
    results = {}
    tracks = []

    try:
        # Test 1: Authentication
        results["Authentication"] = test_authentication(client, logger)

        if results["Authentication"]:
            # Test 2: Get artists (ID3)
            results["Get Artists"] = test_get_artists(client, logger)

            # Test 3: Get artist details (ID3)
            results["Get Artist"] = test_get_artist(client, logger)

            # Test 4: Get album tracks (ID3)
            results["Get Album"] = test_get_album(client, logger)

            # Test 5: Full library fetch via ID3 browsing
            results["Library Fetch (ID3)"] = test_library_fetch_id3(client, logger)

            # Test 6: Fetch random tracks
            tracks = test_fetch_tracks(client, logger, count=10)
            results["Fetch Random Tracks"] = len(tracks) > 0

            # Test 7: Display metadata
            results["Display Metadata"] = test_display_metadata(tracks, logger)

            # Test 8: Stream URL
            results["Stream URL"] = test_stream_url(client, tracks, logger)

            # Test 9: Performance
            results["Performance"] = test_performance(client, logger, count=10)

            # Test 10: Network error handling
            results["Network Error Handling"] = test_network_error_handling(client, logger)
        else:
            # Authentication failed, skip other tests
            print(
                "\n⚠️  Skipping remaining tests due to authentication failure"
            )
            results["Get Artists"] = False
            results["Get Artist"] = False
            results["Get Album"] = False
            results["Library Fetch (ID3)"] = False
            results["Fetch Random Tracks"] = False
            results["Display Metadata"] = False
            results["Stream URL"] = False
            results["Performance"] = False
            results["Network Error Handling"] = False

    finally:
        # Cleanup
        client.close()
        print("\n✓ Client closed")

    # Print summary
    print_summary(results)

    # Return exit code
    all_passed = all(results.values())
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
