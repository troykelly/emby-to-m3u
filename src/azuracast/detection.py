"""Duplicate detection strategies for AzuraCast tracks.

This module implements multi-strategy duplicate detection with hierarchical fallback:
1. MusicBrainz ID (highest confidence)
2. Normalized metadata fingerprint (high confidence)
3. File path (fallback, medium confidence)

All functions are designed for O(1) lookup with pre-built indices.
"""

import logging
from typing import Any, Dict, List, Optional

from .models import DetectionStrategy, UploadDecision
from .normalization import build_track_fingerprint

logger = logging.getLogger(__name__)


def check_file_exists_by_musicbrainz(
    known_tracks: List[Dict[str, Any]], track: Dict[str, Any]
) -> Optional[str]:
    """Check for duplicate using MusicBrainz Track ID.

    Args:
        known_tracks: List of tracks already in AzuraCast library
        track: Source track to check for duplicates

    Returns:
        AzuraCast file ID (str) if MBID match found, None otherwise

    Example:
        >>> known_tracks = [
        ...     {"id": "12345", "custom_fields": {"musicbrainz_trackid": "abc-123"}}
        ... ]
        >>> track = {"ProviderIds": {"MusicBrainzTrack": "abc-123"}}
        >>> check_file_exists_by_musicbrainz(known_tracks, track)
        '12345'
    """
    # Extract source MBID
    source_mbid = track.get("ProviderIds", {}).get("MusicBrainzTrack")
    if not source_mbid:
        return None

    # Normalize MBID for comparison
    source_mbid_norm = source_mbid.strip().lower()

    # Build MBID index from known tracks for O(1) lookup
    mbid_index: Dict[str, List[str]] = {}
    for known_track in known_tracks:
        known_mbid = (
            known_track.get("custom_fields", {}).get("musicbrainz_trackid", "").strip().lower()
        )

        if known_mbid:
            if known_mbid not in mbid_index:
                mbid_index[known_mbid] = []
            mbid_index[known_mbid].append(known_track["id"])

    # Look up MBID in index
    if source_mbid_norm in mbid_index:
        file_ids = mbid_index[source_mbid_norm]

        # Log warning if multiple tracks have same MBID (data integrity issue)
        if len(file_ids) > 1:
            logger.warning(
                f"Multiple AzuraCast tracks found with same MBID '{source_mbid_norm}': "
                f"{file_ids}. Returning first match."
            )

        return file_ids[0]

    return None


def check_file_exists_by_metadata(
    known_tracks: List[Dict[str, Any]], track: Dict[str, Any], duration_tolerance_seconds: int = 5
) -> Optional[str]:
    """Check for duplicate using normalized metadata fingerprint.

    Args:
        known_tracks: List of tracks in AzuraCast library
        track: Source track to check
        duration_tolerance_seconds: Allowable difference in duration (default: ±5s)

    Returns:
        AzuraCast file ID (str) if metadata match found, None otherwise

    Example:
        >>> known_tracks = [
        ...     {"id": "1", "artist": "The Beatles", "album": "Abbey Road",
        ...      "title": "Come Together", "length": 259.5}
        ... ]
        >>> track = {
        ...     "AlbumArtist": "The Beatles", "Album": "Abbey Road",
        ...     "Name": "Come Together", "RunTimeTicks": 2590000000
        ... }
        >>> check_file_exists_by_metadata(known_tracks, track)
        '1'
    """
    # Build source fingerprint
    try:
        source_fingerprint = build_track_fingerprint(track)
    except ValueError as e:
        logger.warning(f"Cannot build fingerprint for source track: {e}")
        return None

    # Extract source duration (optional)
    source_duration = None
    if "RunTimeTicks" in track:
        source_duration = track["RunTimeTicks"] / 10_000_000  # Convert to seconds

    # Build fingerprint index from known tracks
    fingerprint_index: Dict[str, List[Dict[str, Any]]] = {}
    for known_track in known_tracks:
        try:
            known_fingerprint = build_track_fingerprint(
                {
                    "AlbumArtist": known_track.get("artist", ""),
                    "Album": known_track.get("album", ""),
                    "Name": known_track.get("title", ""),
                }
            )
            if known_fingerprint not in fingerprint_index:
                fingerprint_index[known_fingerprint] = []
            fingerprint_index[known_fingerprint].append(known_track)
        except ValueError:
            # Skip malformed known tracks
            continue

    # Look up fingerprint in index
    candidates = fingerprint_index.get(source_fingerprint, [])

    # Validate duration within tolerance
    for candidate in candidates:
        if source_duration is not None and "length" in candidate:
            known_duration = candidate["length"]
            duration_diff = abs(source_duration - known_duration)

            if duration_diff > duration_tolerance_seconds:
                # Log warning if duration difference >5s but <10s
                if duration_diff <= 10:
                    logger.warning(
                        f"Fingerprint match but duration difference: "
                        f"{source_duration:.1f}s vs {known_duration:.1f}s "
                        f"(diff: {duration_diff:.1f}s, tolerance: {duration_tolerance_seconds}s)"
                    )
                continue

        # Match found
        return candidate["id"]

    return None


def should_skip_replaygain_conflict(
    azuracast_track: Optional[Dict[str, Any]], source_track: Dict[str, Any]
) -> bool:
    """Check if upload should be skipped due to ReplayGain conflict.

    Args:
        azuracast_track: Track from AzuraCast library (may be None)
        source_track: Track from source (Emby/Subsonic)

    Returns:
        True if AzuraCast has ReplayGain AND source does not
        (indicating we should preserve AzuraCast's metadata)

    Example:
        >>> azuracast = {"id": "1", "replaygain_track_gain": -3.5}
        >>> source = {"Name": "Song"}
        >>> should_skip_replaygain_conflict(azuracast, source)
        True
    """
    if not azuracast_track:
        return False

    # Check if AzuraCast has ReplayGain
    azuracast_has_rg = (
        "replaygain_track_gain" in azuracast_track or "replaygain_album_gain" in azuracast_track
    )

    # Check if source has ReplayGain (supports multiple formats)
    source_has_rg = (
        "ReplayGainTrackGain" in source_track
        or "ReplayGainAlbumGain" in source_track
        or "replaygain_track_gain" in source_track
        or "replaygain_album_gain" in source_track
    )

    # Return True if AzuraCast has RG but source doesn't (preserve existing)
    return azuracast_has_rg and not source_has_rg


def check_file_in_azuracast(
    known_tracks: List[Dict[str, Any]], track: Dict[str, Any]
) -> UploadDecision:
    """Multi-strategy duplicate detection with fallback logic.

    Strategy order:
    1. MusicBrainz ID match (highest confidence)
    2. Normalized metadata match (high confidence)
    3. File path match (fallback - not yet implemented)
    4. No match (upload allowed)

    Args:
        known_tracks: List of tracks already in AzuraCast library
        track: Source track to check for duplicates

    Returns:
        UploadDecision with should_upload, reason, strategy_used, and azuracast_file_id

    Example:
        >>> known_tracks = [
        ...     {"id": "1", "custom_fields": {"musicbrainz_trackid": "abc"},
        ...      "artist": "Artist", "title": "Song"}
        ... ]
        >>> track = {"ProviderIds": {"MusicBrainzTrack": "abc"}}
        >>> decision = check_file_in_azuracast(known_tracks, track)
        >>> decision.should_upload
        False
        >>> decision.strategy_used
        <DetectionStrategy.MUSICBRAINZ_ID: 'musicbrainz_id'>
    """
    # Strategy 1: MusicBrainz ID match (highest priority)
    mbid_match = check_file_exists_by_musicbrainz(known_tracks, track)
    if mbid_match:
        return UploadDecision(
            should_upload=False,
            reason="Duplicate found by MusicBrainz ID match",
            strategy_used=DetectionStrategy.MUSICBRAINZ_ID,
            azuracast_file_id=mbid_match,
        )

    # Strategy 2: Normalized metadata match
    metadata_match = check_file_exists_by_metadata(known_tracks, track)
    if metadata_match:
        # Detect source duplicates (multiple source tracks → same AzuraCast track)
        # Find the AzuraCast track
        azuracast_track = next((t for t in known_tracks if t["id"] == metadata_match), None)

        # Check ReplayGain conflict
        if should_skip_replaygain_conflict(azuracast_track, track):
            return UploadDecision(
                should_upload=True,
                reason=(
                    f"AzuraCast track (ID: {metadata_match}) has ReplayGain metadata, "
                    "source does not - preferring existing metadata"
                ),
                strategy_used=DetectionStrategy.NORMALIZED_METADATA,
                azuracast_file_id=metadata_match,
            )

        # No ReplayGain conflict, skip upload
        try:
            fingerprint = build_track_fingerprint(track)
            reason = f"Duplicate found: {fingerprint}"
        except ValueError:
            reason = "Duplicate found by metadata match"

        return UploadDecision(
            should_upload=False,
            reason=reason,
            strategy_used=DetectionStrategy.NORMALIZED_METADATA,
            azuracast_file_id=metadata_match,
        )

    # Strategy 3: File path match (not yet implemented)
    # This would be added here when needed

    # No match found - allow upload
    return UploadDecision(
        should_upload=True,
        reason="No duplicate found in AzuraCast library",
        strategy_used=DetectionStrategy.NONE,
        azuracast_file_id=None,
    )
