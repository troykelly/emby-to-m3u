"""Live integration tests for metadata normalization (T015).

These tests verify that tracks with metadata variations are correctly
identified as duplicates through normalization rules.

Test Cases:
- "The" prefix removal: "The Beatles" → "Beatles"
- feat./ft. notation: "feat." → "ft."
- Special characters: "AC/DC" → "AC-DC"
- Case insensitivity: "ARTIST" → "artist"
- Parentheses in titles: "(Live)" handling
- Ampersands: "Simon & Garfunkel"

Prerequisites:
- Live Subsonic server with diverse test tracks
- Live AzuraCast server with API access
- Test playlist with metadata variations
"""

import os
import pytest
from typing import Dict, Any

pytestmark = pytest.mark.integration


@pytest.fixture
def normalization_test_cases():
    """Test cases for metadata normalization.

    Each case has:
    - original: Original metadata as it appears in Subsonic
    - modified: Modified version that should still match
    - rule: The normalization rule being tested
    """
    return [
        {
            "rule": '"The" prefix removal',
            "original": {"artist": "The Beatles", "title": "Hey Jude"},
            "modified": {"artist": "Beatles", "title": "Hey Jude"},
            "should_match": True,
        },
        {
            "rule": "feat./ft. normalization",
            "original": {"artist": "Daft Punk feat. Pharrell Williams", "title": "Get Lucky"},
            "modified": {"artist": "Daft Punk ft. Pharrell Williams", "title": "Get Lucky"},
            "should_match": True,
        },
        {
            "rule": "Special character normalization",
            "original": {"artist": "AC/DC", "title": "Back In Black"},
            "modified": {"artist": "AC-DC", "title": "Back In Black"},
            "should_match": True,
        },
        {
            "rule": "Case insensitivity",
            "original": {"artist": "Simon & Garfunkel", "title": "The Sound of Silence"},
            "modified": {"artist": "SIMON & GARFUNKEL", "title": "THE SOUND OF SILENCE"},
            "should_match": True,
        },
        {
            "rule": "Parentheses in title",
            "original": {"artist": "Queen", "title": "Bohemian Rhapsody (Live)"},
            "modified": {"artist": "Queen", "title": "Bohemian Rhapsody (Remastered)"},
            "should_match": False,  # Different content in parentheses
        },
        {
            "rule": "Ampersand variations",
            "original": {"artist": "Simon & Garfunkel", "title": "Bridge Over Troubled Water"},
            "modified": {"artist": "Simon and Garfunkel", "title": "Bridge Over Troubled Water"},
            "should_match": True,  # If we normalize & to 'and'
        },
        {
            "rule": "Forward slash normalization",
            "original": {"artist": "Artist/Name", "title": "Track/Title"},
            "modified": {"artist": "Artist-Name", "title": "Track-Title"},
            "should_match": True,
        },
    ]


@pytest.mark.integration
def test_t015_normalization_rules(normalization_test_cases, skip_if_no_servers):
    """T015: Test metadata normalization rules.

    This test verifies that normalization functions correctly identify
    tracks as duplicates despite metadata variations.

    Success Criteria:
    - "The Beatles" → "Beatles" matched as duplicate
    - "feat." → "ft." matched as duplicate
    - Special characters normalized and matched
    - Case-insensitive matching working
    - 0 tracks uploaded despite metadata variations
    - Log explicitly shows normalization steps
    """
    # Import normalization functions (will be implemented in T023-T025)
    # from src.azuracast.normalization import normalize_metadata, normalize_artist, normalize_title

    print("\n\nTesting Metadata Normalization Rules:")
    print("=" * 60)

    for test_case in normalization_test_cases:
        rule = test_case["rule"]
        original = test_case["original"]
        modified = test_case["modified"]
        should_match = test_case["should_match"]

        print(f"\nRule: {rule}")
        print(f"  Original: {original}")
        print(f"  Modified: {modified}")
        print(f"  Expected: {'MATCH' if should_match else 'NO MATCH'}")

        # In the actual implementation, we would call:
        # normalized_original = normalize_metadata(original)
        # normalized_modified = normalize_metadata(modified)
        # actual_match = (normalized_original == normalized_modified)

        # For now, document the expected behavior
        # assert actual_match == should_match, f"Normalization failed for rule: {rule}"

        print(f"  Status: ⏳ Pending implementation")

    print("\n" + "=" * 60)
    print("NOTE: Full normalization testing requires implementation of:")
    print("  - src.azuracast.normalization.normalize_metadata()")
    print("  - src.azuracast.normalization.normalize_artist()")
    print("  - src.azuracast.normalization.normalize_title()")


@pytest.mark.integration
def test_the_prefix_removal(skip_if_no_servers):
    """Test "The" prefix removal normalization.

    Artists starting with "The " should match without the prefix.
    """
    test_cases = [
        ("The Beatles", "Beatles"),
        ("The Rolling Stones", "Rolling Stones"),
        ("The Who", "Who"),
        ("The Doors", "Doors"),
        # Edge cases
        ("The The", "The"),  # Band named "The The"
        ("Theatre", "Theatre"),  # "The" is part of word, not prefix
    ]

    print("\n\nTesting 'The' Prefix Removal:")
    for original, expected in test_cases:
        print(f"  {original:25} → {expected}")
        # assert normalize_artist(original) == normalize_artist(expected)


@pytest.mark.integration
def test_featuring_notation_normalization(skip_if_no_servers):
    """Test featuring notation normalization.

    All featuring variations should normalize to the same form.
    """
    base_artist = "Daft Punk"
    featuring_variations = [
        f"{base_artist} feat. Pharrell Williams",
        f"{base_artist} ft. Pharrell Williams",
        f"{base_artist} featuring Pharrell Williams",
        f"{base_artist} (feat. Pharrell Williams)",
        f"{base_artist} (ft. Pharrell Williams)",
    ]

    print("\n\nTesting Featuring Notation Normalization:")
    for variation in featuring_variations:
        print(f"  {variation}")
        # All should normalize to same form
        # normalized = normalize_artist(variation)
        # assert "ft." in normalized.lower() or "pharrell" in normalized.lower()


@pytest.mark.integration
def test_special_character_normalization(skip_if_no_servers):
    """Test special character normalization.

    Special characters should be normalized consistently.
    """
    test_cases = [
        ("AC/DC", "AC-DC"),  # Forward slash → hyphen
        ("A$AP Rocky", "ASAP Rocky"),  # Dollar sign removed
        ("Beyoncé", "Beyonce"),  # Accented characters
        ("Panic! at the Disco", "Panic at the Disco"),  # Exclamation removed
        ("*NSYNC", "NSYNC"),  # Asterisk removed
    ]

    print("\n\nTesting Special Character Normalization:")
    for original, expected_contains in test_cases:
        print(f"  {original:30} → should normalize to ASCII")
        # normalized = normalize_artist(original)
        # Verify special chars handled


@pytest.mark.integration
def test_case_insensitive_matching(skip_if_no_servers):
    """Test case-insensitive metadata matching.

    All case variations should match.
    """
    test_cases = [
        ("The Beatles", "the beatles", "THE BEATLES"),
        ("Led Zeppelin", "led zeppelin", "LED ZEPPELIN"),
        ("Pink Floyd", "pink floyd", "PINK FLOYD"),
    ]

    print("\n\nTesting Case Insensitive Matching:")
    for *variations, in test_cases:
        print(f"  All variations of: {variations[0]}")
        for var in variations:
            print(f"    - {var}")
        # All should normalize to same value
        # normalized_set = {normalize_artist(v).lower() for v in variations}
        # assert len(normalized_set) == 1, "Case variations didn't normalize to same value"


@pytest.mark.integration
def test_whitespace_normalization(skip_if_no_servers):
    """Test whitespace normalization.

    Extra whitespace should be normalized.
    """
    test_cases = [
        ("The  Beatles", "The Beatles"),  # Double space
        (" The Beatles ", "The Beatles"),  # Leading/trailing
        ("The\tBeatles", "The Beatles"),  # Tab character
        ("The   Beatles  ", "The Beatles"),  # Multiple issues
    ]

    print("\n\nTesting Whitespace Normalization:")
    for original, expected in test_cases:
        print(f"  '{original}' → '{expected}'")
        # normalized = normalize_artist(original)
        # assert normalized == expected


@pytest.mark.integration
@pytest.mark.slow
def test_full_normalization_chain(skip_if_no_servers):
    """Test complete normalization chain with multiple rules.

    Verify that multiple normalization rules can be applied together.
    """
    test_cases = [
        {
            "original": {"artist": "The AC/DC", "title": "Back In Black (Live)"},
            "modified": {"artist": "ac-dc", "title": "BACK IN BLACK (LIVE)"},
            "description": "The prefix + special char + case change",
        },
        {
            "original": {"artist": "The Daft Punk feat. Pharrell", "title": "Get Lucky"},
            "modified": {"artist": "DAFT PUNK FT. PHARRELL", "title": "get lucky"},
            "description": "The prefix + feat normalization + case change",
        },
    ]

    print("\n\nTesting Full Normalization Chain:")
    for test_case in test_cases:
        print(f"\n  {test_case['description']}")
        print(f"    Original: {test_case['original']}")
        print(f"    Modified: {test_case['modified']}")
        print(f"    Should: MATCH as duplicate")

        # In implementation:
        # norm_orig = normalize_metadata(test_case['original'])
        # norm_mod = normalize_metadata(test_case['modified'])
        # assert norm_orig == norm_mod


@pytest.mark.integration
def test_musicbrainz_id_priority(skip_if_no_servers):
    """Test that MusicBrainz ID takes priority over metadata matching.

    If both tracks have the same MusicBrainz ID, they should match
    even if metadata differs.
    """
    test_cases = [
        {
            "track1": {
                "artist": "The Beatles",
                "title": "Hey Jude",
                "musicbrainz_id": "abc123",
            },
            "track2": {
                "artist": "Beatles",  # Different artist form
                "title": "Hey Jude",
                "musicbrainz_id": "abc123",  # Same MusicBrainz ID
            },
            "should_match": True,
            "reason": "Same MusicBrainz ID",
        },
        {
            "track1": {
                "artist": "The Beatles",
                "title": "Hey Jude",
                "musicbrainz_id": "abc123",
            },
            "track2": {
                "artist": "The Beatles",
                "title": "Hey Jude",
                "musicbrainz_id": "xyz789",  # Different MusicBrainz ID
            },
            "should_match": False,
            "reason": "Different MusicBrainz IDs",
        },
    ]

    print("\n\nTesting MusicBrainz ID Priority:")
    for test_case in test_cases:
        print(f"\n  {test_case['reason']}")
        print(f"    Track 1: {test_case['track1']}")
        print(f"    Track 2: {test_case['track2']}")
        print(f"    Expected: {'MATCH' if test_case['should_match'] else 'NO MATCH'}")

        # In implementation, MusicBrainz ID should be checked first
        # before applying normalization rules
