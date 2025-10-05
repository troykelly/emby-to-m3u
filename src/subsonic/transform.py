"""Transform Subsonic tracks to Emby-compatible format."""

import logging
from typing import Dict, List, Optional, Set
from .models import SubsonicTrack

logger = logging.getLogger(__name__)

# Constants for Emby format
TICKS_PER_SECOND = 10_000_000  # 10 million ticks = 1 second in Emby


def transform_genre(genre: Optional[str]) -> List[str]:
    """Transform genre from string to array format.

    Emby expects genres as an array of strings, while Subsonic provides a single string.

    Args:
        genre: Genre string from Subsonic (may be None or empty)

    Returns:
        List of genre strings (empty list if genre is None/empty)

    Examples:
        >>> transform_genre("Rock")
        ['Rock']
        >>> transform_genre(" Jazz ")
        ['Jazz']
        >>> transform_genre(None)
        []
        >>> transform_genre("")
        []
    """
    if not genre:
        return []

    # Strip whitespace and return as single-element list
    cleaned_genre = genre.strip()
    return [cleaned_genre] if cleaned_genre else []


def transform_duration(duration_seconds: int) -> int:
    """Transform duration from seconds to Emby ticks.

    Emby uses ticks (100-nanosecond intervals) for duration.
    1 second = 10,000,000 ticks.

    Args:
        duration_seconds: Duration in seconds from Subsonic

    Returns:
        Duration in ticks for Emby format

    Examples:
        >>> transform_duration(180)
        1800000000
        >>> transform_duration(0)
        0
        >>> transform_duration(3600)
        36000000000
    """
    return duration_seconds * TICKS_PER_SECOND


def transform_musicbrainz_id(musicbrainz_id: Optional[str]) -> Dict[str, str]:
    """Transform MusicBrainz ID to Emby ProviderIds format.

    Args:
        musicbrainz_id: MusicBrainz track ID from Subsonic (may be None)

    Returns:
        Dictionary with MusicBrainzTrack key if ID exists, empty dict otherwise

    Examples:
        >>> transform_musicbrainz_id("f3f72a0e-a554-4c8a-9c52-94e1d11b84b0")
        {'MusicBrainzTrack': 'f3f72a0e-a554-4c8a-9c52-94e1d11b84b0'}
        >>> transform_musicbrainz_id(None)
        {}
        >>> transform_musicbrainz_id("")
        {}
    """
    if not musicbrainz_id:
        return {}

    return {"MusicBrainzTrack": musicbrainz_id}


def is_duplicate(track1: Dict, track2: Dict) -> bool:
    """Check if two tracks are duplicates based on metadata.

    Tracks are considered duplicates if they have the same:
    - Title (case-insensitive)
    - Artist (case-insensitive)
    - Album (case-insensitive)

    Args:
        track1: First track dictionary
        track2: Second track dictionary

    Returns:
        True if tracks are duplicates, False otherwise

    Examples:
        >>> t1 = {"Name": "Song", "Artists": ["Artist"], "Album": "Album"}
        >>> t2 = {"Name": "Song", "Artists": ["Artist"], "Album": "Album"}
        >>> is_duplicate(t1, t2)
        True
        >>> t3 = {"Name": "Song", "Artists": ["Artist"], "Album": "Different"}
        >>> is_duplicate(t1, t3)
        False
        >>> t4 = {"Name": "song", "Artists": ["ARTIST"], "Album": "album"}
        >>> is_duplicate(t1, t4)
        True
    """
    # Extract and normalize metadata for comparison
    title1 = track1.get("Name", "").lower().strip()
    title2 = track2.get("Name", "").lower().strip()

    # Get first artist or empty string
    artists1 = track1.get("Artists", [""])
    artists2 = track2.get("Artists", [""])
    artist1 = (artists1[0] if artists1 else "").lower().strip()
    artist2 = (artists2[0] if artists2 else "").lower().strip()

    album1 = track1.get("Album", "").lower().strip()
    album2 = track2.get("Album", "").lower().strip()

    # Compare all three fields
    return (title1 == title2 and
            artist1 == artist2 and
            album1 == album2)


def detect_duplicates(tracks: List[Dict]) -> Set[str]:
    """Detect duplicate tracks in a list.

    Args:
        tracks: List of track dictionaries

    Returns:
        Set of track IDs that are duplicates

    Examples:
        >>> tracks = [
        ...     {"Id": "1", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},
        ...     {"Id": "2", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},
        ...     {"Id": "3", "Name": "Different", "Artists": ["Artist"], "Album": "Album"}
        ... ]
        >>> sorted(detect_duplicates(tracks))
        ['2']
    """
    duplicates = set()
    seen = []

    for track in tracks:
        for existing in seen:
            if is_duplicate(track, existing):
                # Mark the current track as duplicate (keep first occurrence)
                duplicates.add(track["Id"])
                logger.debug(f"Duplicate found: {track.get('Name')} (ID: {track['Id']})")
                break
        else:
            # No duplicate found, add to seen list
            seen.append(track)

    return duplicates


def transform_subsonic_track(track: SubsonicTrack, playlist_manager) -> Dict:
    """Transform a Subsonic track to Emby-compatible format.

    This function converts the Subsonic API track format to match the Emby Track
    dictionary format expected by the PlaylistManager and other components.

    Args:
        track: SubsonicTrack object from Subsonic API
        playlist_manager: PlaylistManager instance (for reference, not modified)

    Returns:
        Dictionary in Emby Track format with:
        - Id: Track identifier
        - Name: Track title
        - Artists: List of artist names
        - Album: Album name
        - RunTimeTicks: Duration in ticks
        - Path: File path
        - Genres: List of genres
        - IndexNumber: Track number
        - ParentIndexNumber: Disc number
        - ProductionYear: Release year
        - ProviderIds: External IDs (MusicBrainz, etc.)
        - _subsonic_*: Original Subsonic metadata for reference

    Example:
        >>> from subsonic.models import SubsonicTrack
        >>> subsonic_track = SubsonicTrack(
        ...     id="123",
        ...     title="Stairway to Heaven",
        ...     artist="Led Zeppelin",
        ...     album="Led Zeppelin IV",
        ...     duration=482,
        ...     path="Led Zeppelin/Led Zeppelin IV/04 Stairway to Heaven.mp3",
        ...     suffix="mp3",
        ...     created="2024-01-01T00:00:00.000Z",
        ...     genre="Rock",
        ...     track=4,
        ...     year=1971
        ... )
        >>> emby_track = transform_subsonic_track(subsonic_track, None)
        >>> emby_track["Name"]
        'Stairway to Heaven'
        >>> emby_track["Artists"]
        ['Led Zeppelin']
        >>> emby_track["Genres"]
        ['Rock']
    """
    # Build Emby-compatible track dictionary
    emby_track = {
        # Core metadata
        "Id": track.id,
        "Name": track.title,
        "Artists": [track.artist],  # Subsonic single artist -> Emby array
        "Album": track.album,
        "RunTimeTicks": transform_duration(track.duration),
        "Path": track.path,

        # Optional metadata
        "Genres": transform_genre(track.genre),
        "IndexNumber": track.track,  # Track number
        "ParentIndexNumber": track.discNumber,  # Disc number
        "ProductionYear": track.year,

        # External provider IDs
        "ProviderIds": transform_musicbrainz_id(track.musicBrainzId),

        # Preserve original Subsonic metadata for reference
        "_subsonic_id": track.id,
        "_subsonic_suffix": track.suffix,
        "_subsonic_created": track.created,
        "_subsonic_cover_art": track.coverArt,
        "_subsonic_size": track.size,
        "_subsonic_bit_rate": track.bitRate,
        "_subsonic_content_type": track.contentType,
    }

    logger.debug(f"Transformed Subsonic track: {track.title} (ID: {track.id})")

    return emby_track
