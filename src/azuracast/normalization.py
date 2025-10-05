"""Normalization functions for AzuraCast duplicate detection.

This module provides string normalization utilities for consistent metadata
comparison across different sources (Emby, Subsonic, AzuraCast).

Functions:
    normalize_string: General-purpose text normalization
    normalize_artist: Artist-specific normalization with "The" prefix handling
    build_track_fingerprint: Create comparison key from normalized metadata
"""

import re
import unicodedata
from typing import Any, Dict


def normalize_string(text: str) -> str:
    """Normalize text for comparison: lowercase, strip, remove special chars.

    Normalization steps:
        1. Strip leading/trailing whitespace
        2. Convert to lowercase
        3. Normalize Unicode (NFKD decomposition)
        4. Remove diacritics (é → e, ñ → n)
        5. Remove special characters (keep alphanumeric + space)
        6. Collapse multiple spaces to single space

    Args:
        text: Raw string from metadata field (may contain extra whitespace,
              special characters, or mixed case)

    Returns:
        Normalized string suitable for case-insensitive comparison

    Examples:
        >>> normalize_string("  Hello World  ")
        'hello world'
        >>> normalize_string("Café")
        'cafe'
        >>> normalize_string("AC/DC")
        'ac dc'
        >>> normalize_string("   ")
        ''
    """
    # Step 1: Strip and lowercase
    normalized = text.strip().lower()

    # Step 2: Unicode normalization (NFKD decomposition)
    normalized = unicodedata.normalize('NFKD', normalized)

    # Step 3: Remove diacritics (keep only ASCII, excluding nonspacing marks)
    normalized = ''.join(
        char for char in normalized
        if unicodedata.category(char) != 'Mn'  # Mn = Nonspacing_Mark (diacritics)
    )

    # Step 4: Remove special characters (keep alphanumeric + space)
    # This also handles emoji and other non-alphanumeric characters
    normalized = re.sub(r'[^a-z0-9\s]', ' ', normalized)

    # Step 5: Collapse multiple spaces to single space
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    return normalized


def normalize_artist(artist: str) -> str:
    """Artist-specific normalization with 'The' prefix handling.

    Applies general normalization and then moves leading "The" to the end.
    This helps match artists like "The Beatles" and "Beatles" or handles
    different catalog conventions.

    Args:
        artist: Raw artist name from metadata

    Returns:
        Normalized artist name with "The" prefix moved to end if present

    Examples:
        >>> normalize_artist("The Beatles")
        'beatles the'
        >>> normalize_artist("Pink Floyd")
        'pink floyd'
        >>> normalize_artist("AC/DC")
        'ac dc'
        >>> normalize_artist("The The")
        'the the'

    Note:
        - Only leading "The" is moved (not mid-string occurrences)
        - Single word "The" is preserved as-is
        - Featuring artists notation (feat., ft.) is preserved
    """
    # First apply general normalization
    normalized = normalize_string(artist)

    # Move leading "The" to end (only if there are other words after it)
    if normalized.startswith("the "):
        # Remove "the " from start and append " the" to end
        normalized = normalized[4:] + " the"

    return normalized


def build_track_fingerprint(track: Dict[str, Any]) -> str:
    """Create comparison key from normalized artist+album+title.

    This fingerprint is the PRIMARY key for duplicate detection.
    It must be stable across different metadata sources.

    Field priority for robustness across different sources:
        - Artist: AlbumArtist > artist > Artist
        - Album: Album > album
        - Title: Name > title > Title

    Args:
        track: Raw track dictionary containing artist, album, and title fields

    Returns:
        Fingerprint string in format: "artist|album|title"

    Raises:
        ValueError: If required fields are missing or empty after normalization

    Examples:
        >>> track = {
        ...     "AlbumArtist": "The Beatles",
        ...     "Album": "Abbey Road",
        ...     "Name": "Come Together"
        ... }
        >>> build_track_fingerprint(track)
        'beatles the|abbey road|come together'

        >>> track = {
        ...     "artist": "Pink Floyd",
        ...     "album": "The Dark Side of the Moon",
        ...     "title": "Time"
        ... }
        >>> build_track_fingerprint(track)
        'pink floyd|dark side of the moon the|time'
    """
    # Field priority for artist (AlbumArtist preferred, fallback to artist/Artist)
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

    # Field priority for title/name
    title_raw = (
        track.get("Name") or
        track.get("title") or
        track.get("Title") or
        ""
    )

    # Check for missing fields BEFORE normalization
    missing = []
    if not artist_raw:
        missing.append("artist")
    if not album_raw:
        missing.append("album")
    if not title_raw:
        missing.append("title")

    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    # Normalize fields
    artist_norm = normalize_artist(artist_raw)
    # Albums also get "The" moved to end like artists
    album_norm = normalize_artist(album_raw)
    title_norm = normalize_string(title_raw)

    # Check for empty fields AFTER normalization
    # This catches cases like "   " or "!!!" that become empty after normalization
    empty = []
    if not artist_norm:
        empty.append("artist")
    if not album_norm:
        empty.append("album")
    if not title_norm:
        empty.append("title")

    if empty:
        raise ValueError(
            f"Empty fields after normalization: {', '.join(empty)}. "
            f"Original values: artist='{artist_raw}', album='{album_raw}', title='{title_raw}'"
        )

    # Build fingerprint with pipe separator
    # Pipe character is safe because normalize_string removes it
    return f"{artist_norm}|{album_norm}|{title_norm}"
