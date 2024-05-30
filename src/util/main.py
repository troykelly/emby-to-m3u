# src/track/main.py
import re
import datetime
import os
import tempfile
import shutil

from typing import List, Dict, Optional, Tuple, Any
from dateutil.parser import parse
from azuracast.main import AzuraCastSync

def normalize_filename(name: str) -> str:
    """Normalize a filename by removing invalid characters.

    Args:
        name: The original name.

    Returns:
        A filesystem-safe version of the name.
    """
    name = re.sub(r'[\\/:"*?<>|]+', '', name)  # Remove invalid characters
    name = re.sub(r'\s+', '_', name)  # Replace spaces with underscores
    return name

def safe_date_parse(date_str: str, default: datetime) -> datetime:
    """Safely parse a date string (ISO 8601 format). Return a default value if parsing fails.

    Args:
        date_str: The date string to parse.
        default: The default value to return if parsing fails.

    Returns:
        The parsed date or the default value if parsing fails.
    """
    try:
        return parse(date_str).replace(tzinfo=None)
    except (ValueError, TypeError):
        return default

def read_existing_m3u(filename: str) -> set:
    """Read an existing m3u file and return a set of its tracks.

    Args:
        filename: The full path to the m3u file.

    Returns:
        A set of track paths in the existing m3u file.
    """
    if not os.path.exists(filename):
        return set()

    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    tracks = {line.strip() for line in lines if line.strip() and not line.startswith('#')}
    return tracks

def write_m3u_playlist(
    filename: str,
    tracks: List[Dict[str, Any]],
    genre: Optional[str] = None,
    artist: Optional[str] = None,
    album: Optional[str] = None
) -> None:
    """Write m3u playlist file.

    Args:
        filename: The full path to the m3u file to be created.
        tracks: List of dictionaries with track details to include in the m3u file.
        genre: Genre to include in the extended attributes.
        artist: Artist to include in the extended attributes.
        album: Album to include in the extended attributes.
    """
    azuracast_sync = AzuraCastSync()
    existing_tracks = read_existing_m3u(filename)
    new_tracks = []

    # Get the prefix to be stripped from the environment variable
    strip_prefix = os.getenv('M3U_STRIP_PREFIX', '')

    def strip_path_prefix(path: str) -> str:
        """Strip the defined prefix from the path if it exists."""
        if strip_prefix and path.startswith(strip_prefix):
            return path[len(strip_prefix):]
        return path

    for track in tracks:
        path = track.get('Path', '')
        if path:
            azuracast_file_path = azuracast_sync.generate_file_path(track)  # Use the same path generation logic
            path = strip_path_prefix(azuracast_file_path)
            if path not in existing_tracks:
                new_tracks.append(track)

    if not new_tracks:
        return  # No new tracks to add

    temp_file = tempfile.NamedTemporaryFile('w', delete=False, encoding='utf-8')
    try:
        with temp_file as f:
            f.write('#EXTM3U\n')
            f.write('#EXTENC:UTF-8\n')
            if genre:
                f.write(f'#EXTGENRE:{genre}\n')
            if artist:
                f.write(f'#EXTART:{artist}\n')
            if album:
                f.write(f'#EXTALB:{album}\n')

            # Re-write existing tracks
            for track_path in existing_tracks:
                f.write(f'{strip_path_prefix(track_path)}\n')

            # Write new tracks
            for track in new_tracks:
                duration = track.get('RunTimeTicks', 0) // 10000000  # Convert ticks to seconds
                title = track.get('Name', 'Unknown Title')
                album = track.get('Album', '')
                album_artist = track.get('AlbumArtist', '')
                genre_name = track.get('Genres', [''])[0] if track.get('Genres') else ''

                # Extract external IDs during playlist writing
                external_ids = extract_external_ids(track)
                mb_track_id = external_ids['MusicBrainzTrackId']
                mb_album_id = external_ids['MusicBrainzAlbumId']
                mb_artist_id = external_ids['MusicBrainzArtistId']
                mb_release_group_id = external_ids['MusicBrainzReleaseGroupId']
                the_audio_db_album_id = external_ids['TheAudioDbAlbumId']
                the_audio_db_artist_id = external_ids['TheAudioDbArtistId']

                # Write extended information
                f.write(f'#EXTINF:{duration}, {title}\n')
                if album:
                    f.write(f'#EXTALB:{album}\n')
                if album_artist:
                    f.write(f'#EXTART:{album_artist}\n')
                if genre_name:
                    f.write(f'#EXTGENRE:{genre_name}\n')
                if mb_track_id:
                    f.write(f'#EXT-X-MUSICBRAINZ-TRACKID:{mb_track_id}\n')
                if mb_album_id:
                    f.write(f'#EXT-X-MUSICBRAINZ-ALBUMID:{mb_album_id}\n')
                if mb_artist_id:
                    f.write(f'#EXT-X-MUSICBRAINZ-ARTISTID:{mb_artist_id}\n')
                if mb_release_group_id:
                    f.write(f'#EXT-X-MUSICBRAINZ-RELEASEGROUPID:{mb_release_group_id}\n')
                if the_audio_db_album_id:
                    f.write(f'#EXT-X-THEAUDIODB-ALBUMID:{the_audio_db_album_id}\n')
                if the_audio_db_artist_id:
                    f.write(f'#EXT-X-THEAUDIODB-ARTISTID:{the_audio_db_artist_id}\n')

                f.write(f'{strip_path_prefix(azuracast_file_path)}\n')

        shutil.move(temp_file.name, filename)
    except Exception as e:
        os.remove(temp_file.name)
        raise e
    
def extract_external_ids(track: Dict[str, Any]) -> Dict[str, str]:
    """Extract external IDs from a track object.

    Args:
        track: The track object.

    Returns:
        A dictionary of external IDs.
    """
    provider_ids = track.get('ProviderIds', {})
    external_ids = {
        'MusicBrainzTrackId': provider_ids.get('MusicBrainzTrack', ''),
        'MusicBrainzAlbumId': provider_ids.get('MusicBrainzAlbum', ''),
        'MusicBrainzArtistId': provider_ids.get('MusicBrainzArtist', ''),
        'MusicBrainzReleaseGroupId': provider_ids.get('MusicBrainzReleaseGroup', ''),
        'TheAudioDbAlbumId': provider_ids.get('TheAudioDbAlbumId', ''),
        'TheAudioDbArtistId': provider_ids.get('TheAudioDbArtistId', '')
    }
    return external_ids

def sizeof_fmt(num: float, suffix: str = 'B') -> str:
    """Convert file size to a readable format.

    Args:
        num: File size in bytes.
        suffix: Suffix for the unit of file size.

    Returns:
        Readable file size format.
    """
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Y{suffix}"
