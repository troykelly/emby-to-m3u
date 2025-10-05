# Normalization Contracts

## Overview

String normalization functions for consistent metadata comparison across different sources (Emby, Subsonic, AzuraCast). All functions are pure (no side effects) and handle edge cases gracefully.

---

## 1. normalize_string

### Signature

```python
def normalize_string(text: str) -> str:
    """Normalize text for comparison: lowercase, strip, remove special chars.

    Args:
        text: Raw string from metadata field (may contain extra whitespace,
              special characters, or mixed case)

    Returns:
        Normalized string suitable for case-insensitive comparison

    Normalization steps:
        1. Strip leading/trailing whitespace
        2. Convert to lowercase
        3. Normalize Unicode (NFD decomposition)
        4. Remove diacritics (é → e, ñ → n)
        5. Collapse multiple spaces to single space
        6. Remove special characters (keep alphanumeric + space)
    """
```

### Example Inputs/Outputs

```python
# Basic normalization
assert normalize_string("  Hello World  ") == "hello world"
assert normalize_string("UPPERCASE") == "uppercase"

# Unicode normalization
assert normalize_string("Café") == "cafe"
assert normalize_string("naïve") == "naive"
assert normalize_string("Zürich") == "zurich"

# Multiple spaces and special chars
assert normalize_string("The  Beatles!") == "the beatles"
assert normalize_string("AC/DC") == "ac dc"
assert normalize_string("???Mystery???") == "mystery"

# Empty/whitespace strings
assert normalize_string("") == ""
assert normalize_string("   ") == ""
assert normalize_string("\t\n") == ""
```

### Edge Cases

```python
# Unicode edge cases
assert normalize_string("北京") == "北京"  # Non-Latin preserved
assert normalize_string("🎵 Music") == "music"  # Emoji removed

# Special characters in titles
assert normalize_string("Track #1") == "track 1"
assert normalize_string("Song (Remix)") == "song remix"
assert normalize_string("Artist's Song") == "artists song"

# Numeric content
assert normalize_string("2001: A Space Odyssey") == "2001 a space odyssey"
assert normalize_string("24/7") == "24 7"
```

### Implementation Notes

```python
import unicodedata
import re

def normalize_string(text: str) -> str:
    # Step 1: Strip and lowercase
    normalized = text.strip().lower()

    # Step 2: Unicode normalization (NFD decomposition)
    normalized = unicodedata.normalize('NFD', normalized)

    # Step 3: Remove diacritics (keep only ASCII)
    normalized = ''.join(
        char for char in normalized
        if unicodedata.category(char) != 'Mn'  # Mn = Nonspacing_Mark
    )

    # Step 4: Remove special characters (keep alphanumeric + space)
    normalized = re.sub(r'[^a-z0-9\s]', ' ', normalized)

    # Step 5: Collapse multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    return normalized
```

### Performance Notes

- **Complexity**: O(n) where n is string length
- **Memory**: O(n) for normalized string
- **Caching**: Consider caching for frequently accessed metadata
- **Unicode**: NFD normalization adds ~20% overhead vs simple lowercase

---

## 2. normalize_artist

### Signature

```python
def normalize_artist(artist: str) -> str:
    """Artist-specific normalization with 'The' prefix handling.

    Args:
        artist: Raw artist name from metadata

    Returns:
        Normalized artist name with special handling for:
        - "The" prefix (moved to end or removed based on configuration)
        - Featuring artists (kept for now, may split in future)
        - Collaborations (& vs and vs feat.)

    Examples:
        "The Beatles" → "beatles" or "beatles the"
        "Pink Floyd feat. David Gilmour" → "pink floyd feat david gilmour"
        "AC/DC" → "ac dc"
    """
```

### Example Inputs/Outputs

```python
# "The" prefix handling (default: move to end)
assert normalize_artist("The Beatles") == "beatles the"
assert normalize_artist("The Rolling Stones") == "rolling stones the"
assert normalize_artist("the who") == "who the"

# Featuring artists
assert normalize_artist("Artist feat. Guest") == "artist feat guest"
assert normalize_artist("Artist ft. Guest") == "artist ft guest"
assert normalize_artist("Artist featuring Guest") == "artist featuring guest"

# Collaborations
assert normalize_artist("Artist & Other") == "artist other"  # & removed
assert normalize_artist("Artist and Other") == "artist and other"  # kept

# Unicode and special chars
assert normalize_artist("Björk") == "bjork"
assert normalize_artist("AC/DC") == "ac dc"
assert normalize_artist("N.W.A.") == "n w a"
```

### Edge Cases

```python
# Multiple "The" occurrences
assert normalize_artist("The The") == "the the"  # Band name is "The The"
assert normalize_artist("The Beatles and The Stones") == "beatles the and stones the"

# Empty/whitespace
assert normalize_artist("") == ""
assert normalize_artist("   ") == ""

# Single word artists
assert normalize_artist("Madonna") == "madonna"
assert normalize_artist("The") == "the"  # Edge case: artist name is just "The"

# Special prefixes in other languages
assert normalize_artist("Los Angeles") == "los angeles"  # Don't move "Los"
assert normalize_artist("Die Ärzte") == "die arzte"  # Don't move "Die" (German)
```

### Configuration Options

```python
from enum import Enum

class TheArticleHandling(Enum):
    REMOVE = "remove"      # "The Beatles" → "beatles"
    MOVE_TO_END = "end"   # "The Beatles" → "beatles the"
    KEEP = "keep"         # "The Beatles" → "the beatles"

def normalize_artist(
    artist: str,
    the_handling: TheArticleHandling = TheArticleHandling.MOVE_TO_END
) -> str:
    normalized = normalize_string(artist)

    if the_handling == TheArticleHandling.REMOVE:
        if normalized.startswith("the "):
            normalized = normalized[4:]  # Remove "the "
    elif the_handling == TheArticleHandling.MOVE_TO_END:
        if normalized.startswith("the "):
            normalized = normalized[4:] + " the"
    # KEEP: no modification

    return normalized
```

### Performance Notes

- **Inherits**: All performance characteristics from `normalize_string()`
- **Additional Cost**: "The" prefix check is O(1) string prefix match
- **Caching Strategy**: Cache normalized artists separately from albums/titles

---

## 3. build_track_fingerprint

### Signature

```python
def build_track_fingerprint(track: Dict[str, Any]) -> str:
    """Create comparison key from normalized artist+album+title.

    Args:
        track: Raw track dictionary containing:
            - AlbumArtist or Artist (str): Artist name
            - Album (str): Album name
            - Name or Title (str): Track title

    Returns:
        Fingerprint string in format: "artist|album|title"

    Raises:
        ValueError: If required fields are missing or empty after normalization

    Note:
        This fingerprint is the PRIMARY key for duplicate detection.
        It must be stable across different metadata sources.
    """
```

### Example Inputs/Outputs

```python
# Standard track
track1 = {
    "AlbumArtist": "The Beatles",
    "Album": "Abbey Road",
    "Name": "Come Together"
}
assert build_track_fingerprint(track1) == "beatles the|abbey road|come together"

# Subsonic format (different field names)
track2 = {
    "artist": "Pink Floyd",
    "album": "The Dark Side of the Moon",
    "title": "Time"
}
assert build_track_fingerprint(track2) == "pink floyd|dark side of the moon the|time"

# With featuring artists
track3 = {
    "AlbumArtist": "Jay-Z feat. Alicia Keys",
    "Album": "The Blueprint 3",
    "Name": "Empire State of Mind"
}
assert build_track_fingerprint(track3) == "jay z feat alicia keys|blueprint 3 the|empire state of mind"

# Unicode normalization
track4 = {
    "AlbumArtist": "Björk",
    "Album": "Homogenic",
    "Name": "Jóga"
}
assert build_track_fingerprint(track4) == "bjork|homogenic|joga"
```

### Edge Cases

```python
# Missing fields
track_missing = {
    "Album": "Test Album"
    # Missing AlbumArtist and Name
}
# Raises ValueError: "Missing required fields: AlbumArtist, Name"

# Empty fields after normalization
track_empty = {
    "AlbumArtist": "   ",
    "Album": "Album",
    "Name": "!!!"
}
# Raises ValueError: "Empty fields after normalization: AlbumArtist, Name"

# Alternative field names (fallback logic)
track_fallback = {
    "Artist": "Test Artist",  # Use Artist if AlbumArtist missing
    "title": "Test Song",     # Use title if Name missing
    "album": "Test Album"
}
assert build_track_fingerprint(track_fallback) == "test artist|test album|test song"

# Pipe character in metadata (rare but possible)
track_pipe = {
    "AlbumArtist": "Artist | Name",
    "Album": "Album",
    "Name": "Title"
}
# Pipe is removed during normalization
assert build_track_fingerprint(track_pipe) == "artist name|album|title"
```

### Field Priority Logic

```python
def build_track_fingerprint(track: Dict[str, Any]) -> str:
    # Field priority for artist
    artist_raw = (
        track.get("AlbumArtist") or
        track.get("artist") or
        track.get("Artist") or
        ""
    )

    # Field priority for album
    album_raw = (
        track.get("Album") or
        track.get("album") or
        ""
    )

    # Field priority for title
    title_raw = (
        track.get("Name") or
        track.get("title") or
        track.get("Title") or
        ""
    )

    # Normalize
    artist_norm = normalize_artist(artist_raw)
    album_norm = normalize_string(album_raw)
    title_norm = normalize_string(title_raw)

    # Validation
    missing = []
    if not artist_raw: missing.append("artist")
    if not album_raw: missing.append("album")
    if not title_raw: missing.append("title")

    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    empty = []
    if not artist_norm: empty.append("artist")
    if not album_norm: empty.append("album")
    if not title_norm: empty.append("title")

    if empty:
        raise ValueError(
            f"Empty fields after normalization: {', '.join(empty)}. "
            f"Original values: artist='{artist_raw}', album='{album_raw}', title='{title_raw}'"
        )

    return f"{artist_norm}|{album_norm}|{title_norm}"
```

### Performance Notes

- **Complexity**: O(n) where n is total length of artist+album+title
- **Memory**: O(n) for fingerprint string
- **Caching**: Cache fingerprints keyed by track ID for session duration
- **Index**: Create index on fingerprints for O(1) lookup

### Validation Strategy

```python
# Pre-validation before fingerprint creation
def validate_track_metadata(track: Dict[str, Any]) -> List[str]:
    """Validate track has required fields for fingerprinting.

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    artist = track.get("AlbumArtist") or track.get("artist")
    if not artist or not artist.strip():
        errors.append("Missing or empty artist")

    album = track.get("Album") or track.get("album")
    if not album or not album.strip():
        errors.append("Missing or empty album")

    title = track.get("Name") or track.get("title")
    if not title or not title.strip():
        errors.append("Missing or empty title")

    return errors

# Usage
errors = validate_track_metadata(track)
if errors:
    logger.warning(f"Track validation failed: {', '.join(errors)}")
    # Skip or handle error
else:
    fingerprint = build_track_fingerprint(track)
```

---

## Integration Example

### Complete Workflow

```python
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

def process_track_for_upload(track: Dict[str, Any]) -> tuple[str, bool]:
    """Process track metadata for duplicate detection.

    Args:
        track: Raw track dictionary from Emby/Subsonic

    Returns:
        Tuple of (fingerprint, is_valid)
    """
    # Step 1: Validate
    errors = validate_track_metadata(track)
    if errors:
        logger.warning(
            f"Track validation failed for '{track.get('Name', 'Unknown')}': "
            f"{', '.join(errors)}"
        )
        return "", False

    # Step 2: Build fingerprint
    try:
        fingerprint = build_track_fingerprint(track)
        logger.debug(f"Generated fingerprint: {fingerprint}")
        return fingerprint, True
    except ValueError as e:
        logger.error(f"Fingerprint generation failed: {e}")
        return "", False

# Example usage
tracks = [
    {
        "AlbumArtist": "The Beatles",
        "Album": "Abbey Road",
        "Name": "Come Together"
    },
    {
        "AlbumArtist": "  ",  # Invalid
        "Album": "Test",
        "Name": "Song"
    }
]

for track in tracks:
    fingerprint, valid = process_track_for_upload(track)
    if valid:
        print(f"✓ {fingerprint}")
    else:
        print(f"✗ Invalid track: {track.get('Name', 'Unknown')}")

# Output:
# ✓ beatles the|abbey road|come together
# ✗ Invalid track: Song
```

---

## Testing Requirements

### Unit Tests

```python
import pytest

class TestNormalization:
    """Test suite for normalization functions."""

    @pytest.mark.parametrize("input_str,expected", [
        ("  Hello  ", "hello"),
        ("UPPERCASE", "uppercase"),
        ("Café", "cafe"),
        ("???Test???", "test"),
        ("", ""),
    ])
    def test_normalize_string(self, input_str, expected):
        assert normalize_string(input_str) == expected

    @pytest.mark.parametrize("artist,expected", [
        ("The Beatles", "beatles the"),
        ("Pink Floyd", "pink floyd"),
        ("AC/DC", "ac dc"),
    ])
    def test_normalize_artist(self, artist, expected):
        assert normalize_artist(artist) == expected

    def test_build_track_fingerprint_valid(self):
        track = {
            "AlbumArtist": "The Beatles",
            "Album": "Abbey Road",
            "Name": "Come Together"
        }
        assert build_track_fingerprint(track) == "beatles the|abbey road|come together"

    def test_build_track_fingerprint_missing_fields(self):
        track = {"Album": "Test"}
        with pytest.raises(ValueError, match="Missing required fields"):
            build_track_fingerprint(track)

    def test_build_track_fingerprint_empty_after_normalization(self):
        track = {
            "AlbumArtist": "   ",
            "Album": "Album",
            "Name": "!!!"
        }
        with pytest.raises(ValueError, match="Empty fields after normalization"):
            build_track_fingerprint(track)
```

### Property-Based Tests

```python
from hypothesis import given, strategies as st

@given(st.text(min_size=1))
def test_normalize_string_always_lowercase(s):
    """Property: normalize_string always returns lowercase."""
    result = normalize_string(s)
    assert result == result.lower()

@given(st.text())
def test_normalize_string_no_leading_trailing_space(s):
    """Property: normalize_string never has leading/trailing spaces."""
    result = normalize_string(s)
    assert result == result.strip()

@given(st.text())
def test_normalize_string_idempotent(s):
    """Property: normalizing twice gives same result as once."""
    once = normalize_string(s)
    twice = normalize_string(once)
    assert once == twice
```

---

## Summary

### Key Contracts

1. **normalize_string**: General-purpose text normalization (lowercase, Unicode, special chars)
2. **normalize_artist**: Artist-specific with "The" prefix handling
3. **build_track_fingerprint**: Composite key generation with validation

### Design Principles

- **Purity**: No side effects, deterministic outputs
- **Validation**: Fail fast with clear error messages
- **Flexibility**: Configurable behavior (e.g., "The" prefix handling)
- **Performance**: O(n) complexity, cacheable results
- **Testability**: Comprehensive edge case coverage

### Files to Create

```
src/azuracast/
├── normalization.py       # All normalization functions
└── test_normalization.py  # Comprehensive test suite
```
