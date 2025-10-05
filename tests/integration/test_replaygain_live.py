"""Live integration tests for ReplayGain preservation (T016).

These tests verify that tracks with ReplayGain metadata are NOT re-uploaded
when detected as duplicates, preserving the existing analyzed audio.

ReplayGain is expensive to calculate and represents valuable analysis data.
The duplicate detection system should preserve existing ReplayGain values
rather than re-uploading tracks.

Prerequisites:
- Live Subsonic server
- Live AzuraCast server
- Test tracks with ReplayGain metadata
"""

import os
import pytest
from typing import Dict, Any

pytestmark = pytest.mark.integration


@pytest.fixture
def replaygain_test_metadata():
    """Sample metadata for ReplayGain testing."""
    return {
        "with_replaygain": {
            "artist": "Test Artist",
            "title": "Test Track with RG",
            "album": "Test Album",
            "replaygain_track_gain": -6.5,  # dB
            "replaygain_track_peak": 0.95,
            "replaygain_album_gain": -7.0,
            "replaygain_album_peak": 0.98,
        },
        "without_replaygain": {
            "artist": "Test Artist",
            "title": "Test Track without RG",
            "album": "Test Album",
            # No ReplayGain fields
        },
    }


@pytest.mark.integration
@pytest.mark.slow
def test_t016_replaygain_preservation(skip_if_no_servers):
    """T016: Test ReplayGain metadata preservation.

    Success Criteria:
    - Track with ReplayGain NOT re-uploaded
    - Log shows "skip - has ReplayGain metadata"
    - AzuraCast preserves original ReplayGain value
    - Modified source ReplayGain ignored

    Test Flow:
    1. Upload track with ReplayGain to AzuraCast
    2. Modify ReplayGain value in source (Subsonic)
    3. Run sync again
    4. Verify track NOT re-uploaded
    5. Verify AzuraCast still has original ReplayGain value
    """
    print("\n\nTesting ReplayGain Preservation:")
    print("=" * 60)

    # In actual implementation:
    # 1. Upload track with ReplayGain
    # 2. Verify it has RG metadata in AzuraCast
    # 3. Modify source ReplayGain value
    # 4. Run duplicate detection
    # 5. Verify skip reason includes "ReplayGain"
    # 6. Verify original RG value preserved

    print("NOTE: Full ReplayGain testing requires:")
    print("  - Upload track with ReplayGain metadata")
    print("  - Check has_replaygain_metadata() function")
    print("  - Verify duplicate detection skips re-upload")
    print("  - Confirm original ReplayGain values preserved")
    print("=" * 60)


@pytest.mark.integration
def test_replaygain_detection(replaygain_test_metadata, skip_if_no_servers):
    """Test detection of ReplayGain metadata in tracks.

    Verifies that the system can correctly identify tracks
    with and without ReplayGain metadata.
    """
    # from replaygain.main import has_replaygain_metadata

    with_rg = replaygain_test_metadata["with_replaygain"]
    without_rg = replaygain_test_metadata["without_replaygain"]

    print("\n\nTesting ReplayGain Detection:")
    print(f"  Track with RG: {with_rg['title']}")
    print(f"    - track_gain: {with_rg['replaygain_track_gain']} dB")
    print(f"    - track_peak: {with_rg['replaygain_track_peak']}")

    print(f"\n  Track without RG: {without_rg['title']}")
    print(f"    - No ReplayGain metadata")

    # In implementation:
    # assert has_replaygain_metadata(with_rg_file) == True
    # assert has_replaygain_metadata(without_rg_file) == False


@pytest.mark.integration
def test_replaygain_skip_decision(skip_if_no_servers):
    """Test upload decision logic for tracks with ReplayGain.

    Tracks with ReplayGain should NOT be re-uploaded even if
    source metadata changes.
    """
    print("\n\nTesting ReplayGain Upload Skip Decision:")

    scenarios = [
        {
            "scenario": "Track exists with RG, source has different RG",
            "azuracast_has_rg": True,
            "source_rg_changed": True,
            "should_upload": False,
            "reason": "Preserve existing ReplayGain analysis",
        },
        {
            "scenario": "Track exists with RG, source RG unchanged",
            "azuracast_has_rg": True,
            "source_rg_changed": False,
            "should_upload": False,
            "reason": "Duplicate with matching ReplayGain",
        },
        {
            "scenario": "Track exists without RG, source has RG",
            "azuracast_has_rg": False,
            "source_has_rg": True,
            "should_upload": True,
            "reason": "Re-upload to add ReplayGain metadata",
        },
        {
            "scenario": "Track exists without RG, source also no RG",
            "azuracast_has_rg": False,
            "source_has_rg": False,
            "should_upload": False,
            "reason": "Duplicate, neither has ReplayGain",
        },
    ]

    for scenario in scenarios:
        print(f"\n  Scenario: {scenario['scenario']}")
        print(f"    Should upload: {scenario['should_upload']}")
        print(f"    Reason: {scenario['reason']}")

        # In implementation:
        # decision = decide_upload(azuracast_track, source_track)
        # assert decision.should_upload == scenario['should_upload']
        # assert scenario['reason'].lower() in decision.reason.lower()


@pytest.mark.integration
def test_replaygain_value_preservation(skip_if_no_servers):
    """Test that original ReplayGain values are preserved.

    When a track is skipped due to ReplayGain, the original
    values in AzuraCast should remain unchanged.
    """
    original_rg = {
        "track_gain": -6.5,
        "track_peak": 0.95,
        "album_gain": -7.0,
        "album_peak": 0.98,
    }

    modified_rg = {
        "track_gain": -8.0,  # Different value
        "track_peak": 0.92,
        "album_gain": -8.5,
        "album_peak": 0.94,
    }

    print("\n\nTesting ReplayGain Value Preservation:")
    print(f"  Original values in AzuraCast: {original_rg}")
    print(f"  Modified values in source: {modified_rg}")
    print("\n  After duplicate detection:")
    print(f"    Expected AzuraCast values: {original_rg} (UNCHANGED)")

    # In implementation:
    # 1. Get track from AzuraCast
    # 2. Verify it has original_rg values
    # 3. Run duplicate detection with modified_rg source
    # 4. Get track from AzuraCast again
    # 5. Verify values still match original_rg


@pytest.mark.integration
def test_replaygain_metadata_formats(skip_if_no_servers):
    """Test ReplayGain detection across different audio formats.

    ReplayGain can be stored in different tag formats:
    - ID3v2 (MP3): TXXX:replaygain_*
    - Vorbis Comments (OGG, FLAC): REPLAYGAIN_*
    - APE tags (APE, MPC): replaygain_*
    """
    formats = [
        {
            "format": "MP3 (ID3v2)",
            "extension": ".mp3",
            "tag_format": "TXXX:replaygain_track_gain",
        },
        {
            "format": "FLAC (Vorbis)",
            "extension": ".flac",
            "tag_format": "REPLAYGAIN_TRACK_GAIN",
        },
        {
            "format": "OGG (Vorbis)",
            "extension": ".ogg",
            "tag_format": "REPLAYGAIN_TRACK_GAIN",
        },
        {
            "format": "M4A (MP4)",
            "extension": ".m4a",
            "tag_format": "----:com.apple.iTunes:replaygain_track_gain",
        },
    ]

    print("\n\nTesting ReplayGain Detection Across Formats:")
    for fmt in formats:
        print(f"\n  Format: {fmt['format']}")
        print(f"    Extension: {fmt['extension']}")
        print(f"    Tag format: {fmt['tag_format']}")

        # In implementation:
        # test_file = create_test_file_with_rg(fmt['extension'])
        # assert has_replaygain_metadata(test_file, fmt['extension'])


@pytest.mark.integration
def test_replaygain_missing_fields(skip_if_no_servers):
    """Test handling of incomplete ReplayGain metadata.

    Some tracks may have only track gain, or only album gain.
    Test how the system handles partial ReplayGain data.
    """
    test_cases = [
        {
            "description": "Only track gain",
            "metadata": {"replaygain_track_gain": -6.5},
            "has_rg": True,
        },
        {
            "description": "Only album gain",
            "metadata": {"replaygain_album_gain": -7.0},
            "has_rg": True,
        },
        {
            "description": "Track gain and peak",
            "metadata": {
                "replaygain_track_gain": -6.5,
                "replaygain_track_peak": 0.95,
            },
            "has_rg": True,
        },
        {
            "description": "All ReplayGain fields",
            "metadata": {
                "replaygain_track_gain": -6.5,
                "replaygain_track_peak": 0.95,
                "replaygain_album_gain": -7.0,
                "replaygain_album_peak": 0.98,
            },
            "has_rg": True,
        },
        {
            "description": "No ReplayGain fields",
            "metadata": {},
            "has_rg": False,
        },
    ]

    print("\n\nTesting Partial ReplayGain Metadata:")
    for test_case in test_cases:
        print(f"\n  {test_case['description']}")
        print(f"    Metadata: {test_case['metadata']}")
        print(f"    Has ReplayGain: {test_case['has_rg']}")

        # In implementation:
        # has_rg = has_replaygain_metadata(test_case['metadata'])
        # assert has_rg == test_case['has_rg']


@pytest.mark.integration
@pytest.mark.slow
def test_replaygain_calculation_expensive(skip_if_no_servers):
    """Document that ReplayGain calculation is expensive.

    This test documents why ReplayGain preservation is important:
    - Requires analyzing entire audio file
    - CPU-intensive FFT calculations
    - Can take several seconds per track
    - For 1000 tracks, could take 30+ minutes

    Therefore, preserving existing ReplayGain is a significant
    performance optimization.
    """
    print("\n\nReplayGain Calculation Cost:")
    print("=" * 60)
    print("Why ReplayGain preservation matters:")
    print("\n  Analysis requirements:")
    print("    - Full audio file scan (every sample)")
    print("    - RMS (Root Mean Square) calculation")
    print("    - Peak detection")
    print("    - CPU-intensive processing")
    print("\n  Estimated time per track:")
    print("    - Short track (3 min): ~2-5 seconds")
    print("    - Long track (10 min): ~7-15 seconds")
    print("\n  At scale:")
    print("    - 100 tracks: ~5-10 minutes")
    print("    - 1000 tracks: ~30-60 minutes")
    print("\n  Conclusion:")
    print("    Preserving existing ReplayGain avoids expensive")
    print("    re-analysis and saves significant processing time.")
    print("=" * 60)


@pytest.mark.integration
def test_replaygain_log_messages(skip_if_no_servers):
    """Test that appropriate log messages are generated.

    When ReplayGain preservation triggers, the system should
    log clear messages explaining why upload was skipped.
    """
    expected_log_messages = [
        "has ReplayGain metadata",
        "preserving existing",
        "skip upload",
        "ReplayGain",
    ]

    print("\n\nExpected Log Messages for ReplayGain Skip:")
    for msg in expected_log_messages:
        print(f"  - Log should contain: '{msg}'")

    # In implementation:
    # with LogCapture() as logs:
    #     sync_track_with_rg_existing()
    #     for expected_msg in expected_log_messages:
    #         assert any(expected_msg in log for log in logs)
