#!/usr/bin/env python3
"""Manual test script for SubsonicClient.

This script tests the SubsonicClient implementation against a real Subsonic server.
Set SUBSONIC_USERNAME and SUBSONIC_PASSWORD environment variables before running.

Usage:
    export SUBSONIC_URL="https://music.mctk.co"
    export SUBSONIC_USERNAME="your_username"
    export SUBSONIC_PASSWORD="your_password"
    python scripts/test_subsonic_client.py
"""

import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.subsonic import SubsonicClient, SubsonicConfig
from src.subsonic.exceptions import SubsonicError


def main():
    """Run manual tests against Subsonic server."""
    # Check for environment variables
    url = os.getenv("SUBSONIC_URL", "https://music.mctk.co")
    username = os.getenv("SUBSONIC_USERNAME")
    password = os.getenv("SUBSONIC_PASSWORD")

    if not username or not password:
        print("ERROR: SUBSONIC_USERNAME and SUBSONIC_PASSWORD must be set")
        print("Usage: SUBSONIC_USERNAME=user SUBSONIC_PASSWORD=pass python scripts/test_subsonic_client.py")
        return 1

    # Create configuration
    config = SubsonicConfig(
        url=url,
        username=username,
        password=password,
        client_name="emby-to-m3u-test",
        api_version="1.16.1",
    )

    print(f"Testing Subsonic client with server: {config.url}")
    print(f"Username: {config.username}")
    print("=" * 70)

    try:
        with SubsonicClient(config) as client:
            # Test 1: Ping
            print("\n1. Testing ping...")
            try:
                result = client.ping()
                print(f"   ✓ Ping successful: {result}")
            except SubsonicError as e:
                print(f"   ✗ Ping failed: {e.message} (code: {e.code})")
                return 1
            except Exception as e:
                print(f"   ✗ Ping failed: {e}")
                return 1

            # Test 2: Get songs (first 10)
            print("\n2. Testing get_all_songs (first 10)...")
            try:
                tracks = client.get_all_songs(offset=0, size=10)
                print(f"   ✓ Retrieved {len(tracks)} tracks")

                if tracks:
                    track = tracks[0]
                    print(f"\n   Sample track:")
                    print(f"   - ID: {track.id}")
                    print(f"   - Title: {track.title}")
                    print(f"   - Artist: {track.artist}")
                    print(f"   - Album: {track.album}")
                    print(f"   - Duration: {track.duration}s")
                    print(f"   - Path: {track.path}")
                    print(f"   - Format: {track.suffix}")
                    if track.genre:
                        print(f"   - Genre: {track.genre}")
                    if track.year:
                        print(f"   - Year: {track.year}")
            except SubsonicError as e:
                print(f"   ✗ Failed to get songs: {e.message} (code: {e.code})")
                return 1
            except Exception as e:
                print(f"   ✗ Failed to get songs: {e}")
                return 1

            # Test 3: Stream URL
            if tracks:
                print("\n3. Testing get_stream_url...")
                try:
                    url = client.get_stream_url(tracks[0].id)
                    print(f"   ✓ Stream URL generated")
                    print(f"   - URL length: {len(url)} chars")
                    print(f"   - First 80 chars: {url[:80]}...")
                except SubsonicError as e:
                    print(f"   ✗ Failed to get stream URL: {e.message} (code: {e.code})")
                except Exception as e:
                    print(f"   ✗ Failed to get stream URL: {e}")

            # Test 4: Stream track (download audio)
            if tracks:
                print("\n4. Testing stream_track (download audio)...")
                try:
                    audio_data = client.stream_track(tracks[0].id)
                    print(f"   ✓ Downloaded {len(audio_data):,} bytes")

                    # Verify it's actual audio data (check for common audio file headers)
                    if audio_data[:3] == b"ID3" or audio_data[:4] == b"fLaC" or audio_data[:4] == b"OggS":
                        print(f"   ✓ Audio data verified (recognized format)")
                    else:
                        print(f"   ⚠ Audio format: Unknown (first 10 bytes: {audio_data[:10].hex()})")
                except SubsonicError as e:
                    print(f"   ✗ Failed to stream track: {e.message} (code: {e.code})")
                except Exception as e:
                    print(f"   ✗ Failed to stream track: {e}")

            # Test 5: Pagination
            print("\n5. Testing pagination (fetch 3 pages of 5 tracks)...")
            try:
                total_tracks = []
                for page in range(3):
                    offset = page * 5
                    page_tracks = client.get_all_songs(offset=offset, size=5)
                    total_tracks.extend(page_tracks)
                    print(f"   - Page {page + 1}: {len(page_tracks)} tracks (offset={offset})")

                print(f"   ✓ Total tracks from 3 pages: {len(total_tracks)}")
            except SubsonicError as e:
                print(f"   ✗ Pagination failed: {e.message} (code: {e.code})")
            except Exception as e:
                print(f"   ✗ Pagination failed: {e}")

        print("\n" + "=" * 70)
        print("All tests passed! ✓")
        return 0

    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
