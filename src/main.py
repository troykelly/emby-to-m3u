#!/usr/bin/env python3
"""
Script to generate m3u playlists from Emby API based on music genres, artists, albums, and years.

This script connects to the Emby API, retrieves all music tracks,
and generates m3u playlist files for each genre, artist, album, and year.

Environment Variables:
- EMBY_API_KEY: The API key to authenticate with Emby.
- EMBY_SERVER_URL: The base URL of the Emby server. E.g., http://localhost:8096
- M3U_DESTINATION: The directory where m3u files will be created.
- M3U_CRON: Cron expression for running the script periodically (optional).

Author: Troy Kelly
Date: 22 May 2024

Usage:
Make sure to set the environment variables before running the script:
$ export EMBY_API_KEY='YOUR_API_KEY'
$ export EMBY_SERVER_URL='http://YOUR_EMBY_SERVER'
$ export M3U_DESTINATION='/path/to/m3u/destination'
$ export M3U_CRON='*/15 * * * *' # Optional cron expression

Then run the script:
$ python3 main.py
"""

import os
import shutil
import logging
import requests
import random
from datetime import datetime
from collections import defaultdict, Counter
from tqdm import tqdm
import tempfile
import re

from radioplaylist.main import RadioPlaylistGenerator
from lastfm.main import LastFM
from azuracast.main import AzuraCastSync
from dateutil.parser import parse
from croniter import croniter
from time import sleep

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_playlists():
    """Main function to generate m3u playlists for genres, artists, albums, and years."""
    destination = os.getenv('M3U_DESTINATION')
    if not destination:
        raise ValueError("Environment variable M3U_DESTINATION is not set.")

    logger.info("Generating playlists")

    genre_dir, artist_dir, album_dir = ensure_directories_exist(destination)

    # Initialize the PlaylistManager and fetch tracks from Emby
    playlist_manager = PlaylistManager()
    playlist_manager.fetch_tracks()  # Fetch and set tracks

    # Add tracks and genres to PlaylistManager
    for track in tqdm(playlist_manager.tracks, desc="Adding tracks and genres"):
        playlist_manager.add_track(track)
        for genre in track.get('Genres', []):
            playlist_manager.add_genre(genre, track['Id'])

    # Process tracks to categorize by genre, artist, and album
    playlist_manager.process_tracks()

    # Write out playlists to the filesystem
    playlist_manager.write_playlists(genre_dir, artist_dir, album_dir)

    min_radio_duration = 86400  # Example duration for radio playlist in seconds (24 hours)

    azuracast_sync = AzuraCastSync()
    lastfm = LastFM()
    radio_generator = RadioPlaylistGenerator(playlist_manager, lastfm, azuracast_sync)

    for time_segment, genres in tqdm(radio_generator.playlists.items(), desc="Generating radio playlists"):
        playlist = radio_generator.generate_playlist(genres, min_radio_duration, time_segment)
        if not playlist:
            logger.error(f"Generated {time_segment} radio playlist is empty. Nothing to upload.")
            continue

        playlist_name = f"General - {time_segment}"
        clear_playlist = True  # Clear the playlist initially

        if clear_playlist:
            azuracast_sync.clear_playlist_by_name(playlist_name)

        azuracast_sync.upload_playlist(playlist, playlist_name)

    logger.info("Playlists generated successfully")

def fetch_tracks_from_emby():
    """Fetch all audio items with basic metadata from Emby."""
    all_audio_items = get_emby_data(
        '/Items?Recursive=true&IncludeItemTypes=Audio&Fields='
        'Path,RunTimeTicks,Name,Album,AlbumArtist,Genres,IndexNumber,ProductionYear,PremiereDate,ExternalIds,MusicBrainzAlbumId,MusicBrainzArtistId,MusicBrainzReleaseGroupId,ParentIndexNumber,ProviderIds,TheAudioDbAlbumId,TheAudioDbArtistId&SortBy=SortName&SortOrder=Ascending'
    )
    return all_audio_items['Items']  # Ensure correct key for the return value

def ensure_directories_exist(destination):
    """Ensure the required directories exist.

    Args:
        destination (str): Base directory to ensure exists.

    Returns:
        tuple: Directories for genre, artist, and album playlists.
    """
    genre_dir = os.path.join(destination, '_genre')
    artist_dir = os.path.join(destination, '_artist')
    album_dir = os.path.join(destination, '_album')
    os.makedirs(destination, exist_ok=True)
    os.makedirs(genre_dir, exist_ok=True)
    os.makedirs(artist_dir, exist_ok=True)
    os.makedirs(album_dir, exist_ok=True)
    return genre_dir, artist_dir, album_dir


class PlaylistManager:
    """Manages music tracks and playlist generation."""

    def __init__(self):
        """Initializes PlaylistManager with empty tracks and playlists."""
        self.tracks = []
        self.track_map = {}  # track_id -> track
        self.genres = defaultdict(list)  # genre -> list of track_ids
        self.playlists = {'genres': defaultdict(list), 'artists': defaultdict(list), 'albums': defaultdict(list)}
        self.artist_counter = Counter()
        self.album_counter = Counter()
        self.tracks_to_sync = []

    def add_track(self, track):
        """Adds a track to the PlaylistManager.

        Args:
            track (dict): Track metadata dictionary.

        Raises:
            ValueError: If the track does not have an 'Id' field.
        """
        if 'Id' not in track:
            raise ValueError("Track must have an 'Id' field.")
        self.track_map[track['Id']] = track
        self.tracks.append(track)  # Ensure tracks are stored for subsequent processing

    def add_genre(self, genre, track_id):
        """Associates a track ID with a genre.

        Args:
            genre (str): Genre name.
            track_id (str): Track ID.
        """
        self.genres[genre].append(track_id)

    def get_tracks_by_genre(self, genre):
        """Retrieves a list of tracks for a given genre.

        Args:
            genre (str): Genre name.

        Returns:
            list: List of track dictionaries.
        """
        return [self.track_map[track_id] for track_id in self.genres[genre]]

    def get_track_by_id(self, track_id):
        """Retrieves a track by its ID.

        Args:
            track_id (str): Track ID.

        Returns:
            dict: Track metadata dictionary.
        """
        return self.track_map.get(track_id)

    def get_all_genres(self):
        """Retrieves a list of all genres.

        Returns:
            list: List of genre names.
        """
        return list(self.genres.keys())

    def fetch_tracks(self):
        """Fetches all audio items with basic metadata from Emby."""
        all_audio_items = self._get_emby_data(
            '/Items?Recursive=true&IncludeItemTypes=Audio&Fields='
            'Path,RunTimeTicks,Name,Album,AlbumArtist,Genres,IndexNumber,ProductionYear,PremiereDate,ExternalIds,'
            'MusicBrainzAlbumId,MusicBrainzArtistId,MusicBrainzReleaseGroupId,ParentIndexNumber,ProviderIds,'
            'TheAudioDbAlbumId,TheAudioDbArtistId&SortBy=SortName&SortOrder=Ascending'
        )
        self.tracks = all_audio_items.get('Items', [])

    def _get_emby_data(self, endpoint):
        """Retrieves data from a given Emby API endpoint.

        Args:
            endpoint (str): The specific API endpoint to fetch data from.

        Returns:
            dict: The data retrieved from the Emby API.
        """
        emby_server_url = os.getenv('EMBY_SERVER_URL')
        emby_api_key = os.getenv('EMBY_API_KEY')
        url = f'{emby_server_url}{endpoint}&api_key={emby_api_key}'
        response = requests.get(url)
        response.raise_for_status()
        return response.json()

    def process_tracks(self):
        """Processes tracks to categorize them by genre, artist, and album."""
        azuracast_sync = AzuraCastSync()
        known_tracks = azuracast_sync.get_known_tracks()

        for track in tqdm(self.tracks, desc="Processing tracks"):
            self.add_track(track)

            artist_name = track.get('AlbumArtist', 'Unknown Artist')
            album_name = f"{track.get('Album', 'Unknown Album')} ({track.get('ProductionYear', 'Unknown Year')})"
            disk_number = track.get('ParentIndexNumber', 1)
            track_number = track.get('IndexNumber', 1)
            title = track.get('Name', 'Unknown Title')
            file_path = track.get('Path')
            file_extension = os.path.splitext(file_path)[1]
            azuracast_file_path = f"{artist_name}/{album_name}/{disk_number:02d} {track_number:02d} {title}{file_extension}"

            if not azuracast_sync.check_file_in_azuracast(known_tracks, azuracast_file_path):
                self.tracks_to_sync.append((track, azuracast_file_path))

            track_genres = track.get('Genres', [])
            if not track_genres:
                continue  # Skip tracks with no genre information

            for genre in track_genres:
                self.playlists['genres'][genre].append(track)
                self.add_genre(genre, track['Id'])

            artist_id = track.get('MusicBrainzArtistId') or track.get('AlbumArtistId') or track.get('AlbumArtist')
            if artist_id:
                artist_key = (artist_id, artist_name)
                self.playlists['artists'][artist_key].append(track)
                self.artist_counter[artist_name] += 1

            album_id = track.get('MusicBrainzAlbumId') or track.get('AlbumId') or track.get('Album')
            if album_id:
                album_key = (album_id, album_name)
                self.playlists['albums'][album_key].append(track)
                self.album_counter[album_name] += 1

    def disambiguate_names(self):
        """Disambiguates artist and album names if they have the same name."""
        disambiguated_artists = {}
        for (artist_id, artist_name), tracks in self.playlists['artists'].items():
            if self.artist_counter[artist_name] > 1:
                disambiguated_artist = f"{artist_name} ({artist_id})"
            else:
                disambiguated_artist = artist_name
            disambiguated_artists.setdefault(disambiguated_artist, []).extend(tracks)
        self.playlists['artists'] = disambiguated_artists

        disambiguated_albums = {}
        for (album_id, album_name), tracks in self.playlists['albums'].items():
            if self.album_counter[album_name] > 1:
                disambiguated_album = f"{album_name} ({album_id})"
            else:
                disambiguated_album = album_name
            disambiguated_albums.setdefault(disambiguated_album, []).extend(tracks)
        self.playlists['albums'] = disambiguated_albums

    def write_playlists(self, genre_dir, artist_dir, album_dir):
        """Writes the genre, artist, and album playlists to their respective directories.

        Args:
            genre_dir (str): Directory to save genre playlists.
            artist_dir (str): Directory to save artist playlists.
            album_dir (str): Directory to save album playlists.
        """
        default_date = datetime.min

        for genre, tracks in tqdm(self.playlists['genres'].items(), desc="Writing genre playlists"):
            genre_filename = os.path.join(genre_dir, f'{normalize_filename(genre)}.m3u')
            write_m3u_playlist(genre_filename, tracks, genre=genre)

        for disambiguated_artist, tracks in tqdm(self.playlists['artists'].items(), desc="Writing artist playlists"):
            if tracks:
                tracks.sort(key=lambda x: (
                    self._safe_date_parse(x.get('PremiereDate', ''), default_date),
                    x.get('ParentIndexNumber', 0),
                    x.get('IndexNumber', 0)
                ))
                artist_filename = os.path.join(artist_dir, f'{normalize_filename(disambiguated_artist)}.m3u')
                write_m3u_playlist(artist_filename, tracks, artist=disambiguated_artist)

        for disambiguated_album, tracks in tqdm(self.playlists['albums'].items(), desc="Writing album playlists"):
            if tracks:
                tracks.sort(key=lambda x: x.get('IndexNumber', 0))
                album_filename = os.path.join(album_dir, f'{normalize_filename(disambiguated_album)}.m3u')
                write_m3u_playlist(album_filename, tracks, album=disambiguated_album)

    def sync_tracks(self):
        """Syncs tracks to Azuracast if necessary."""
        if os.getenv('AZURACAST_HOST') and os.getenv('AZURACAST_API_KEY') and os.getenv('AZURACAST_STATIONID'):
            sync_tracks_in_batches(self.tracks_to_sync, batch_size=5)

    @staticmethod
    def _safe_date_parse(date_str, default):
        """Safely parses a date string (ISO 8601 format). Returns a default value if parsing fails.

        Args:
            date_str (str): The date string to parse.
            default (datetime): The default value to return if parsing fails.

        Returns:
            datetime: The parsed date or the default value if parsing fails.
        """
        try:
            return parse(date_str).replace(tzinfo=None)
        except (ValueError, TypeError):
            return default

def get_emby_data(endpoint):
    """Retrieve data from given Emby API endpoint.

    Args:
        endpoint (str): The specific API endpoint to fetch data from.

    Returns:
        dict: The data retrieved from the Emby API.
    """
    emby_server_url = os.getenv('EMBY_SERVER_URL')
    emby_api_key = os.getenv('EMBY_API_KEY')
    url = f'{emby_server_url}{endpoint}&api_key={emby_api_key}'
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def get_emby_file_content(track):
    """Fetches the binary content of a track file from Emby.

    Args:
        track (dict): The track object with its detailed metadata.

    Returns:
        bytes: The binary content of the track's file.
    """
    emby_server_url = os.getenv('EMBY_SERVER_URL')
    emby_api_key = os.getenv('EMBY_API_KEY')

    file_id = track['Id']
    download_url = f"{emby_server_url}/Items/{file_id}/File?api_key={emby_api_key}"

    response = requests.get(download_url, stream=True)
    response.raise_for_status()

    return response.content

def extract_external_ids(track):
    """Extract external IDs from a track object.

    Args:
        track (dict): The track object.

    Returns:
        dict: A dictionary of external IDs.
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

def read_existing_m3u(filename):
    """Read an existing m3u file and return a set of its tracks.

    Args:
        filename (str): The full path to the m3u file.

    Returns:
        set: A set of track paths in the existing m3u file.
    """
    if not os.path.exists(filename):
        return set()

    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    tracks = set()
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#'):
            tracks.add(line)

    return tracks

def write_m3u_playlist(filename, tracks, genre=None, artist=None, album=None):
    """Write m3u playlist file.

    Args:
        filename (str): The full path to the m3u file to be created.
        tracks (list): List of dictionaries with track details to include in the m3u file.
        genre (str, optional): Genre to include in the extended attributes.
        artist (str, optional): Artist to include in the extended attributes.
        album (str, optional): Album to include in the extended attributes.
    """
    existing_tracks = read_existing_m3u(filename)
    new_tracks = []

    # Get the prefix to be stripped from the environment variable
    strip_prefix = os.getenv('M3U_STRIP_PREFIX', '')
    
    def strip_path_prefix(path):
        """Strip the defined prefix from the path if it exists."""
        if strip_prefix and path.startswith(strip_prefix):
            return path[len(strip_prefix):]
        return path

    for track in tracks:
        path = track.get('Path', '')
        if path:
            azuracast_file_path = generate_azuracast_file_path(track)  # Use the same path generation logic
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
                track_path = strip_path_prefix(track_path)
                f.write(f'{track_path}\n')

            # Write new tracks
            for track in new_tracks:
                duration = track.get('RunTimeTicks', 0) // 10000000  # Convert ticks to seconds
                title = track.get('Name', 'Unknown Title')
                path = track.get('Path', '')
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
                
                azuracast_file_path = generate_azuracast_file_path(track)
                f.write(f'{strip_path_prefix(azuracast_file_path)}\n')
        
        shutil.move(temp_file.name, filename)
    except Exception as e:
        os.remove(temp_file.name)
        raise e

def normalize_filename(name):
    """Normalize filename by removing invalid characters.

    Args:
        name (str): The original name.

    Returns:
        str: A filesystem-safe version of the name.
    """
    name = re.sub(r'[\\/:"*?<>|]+', '', name)  # Remove invalid characters
    name = re.sub(r'\s+', '_', name)  # Replace spaces with underscores
    return name

def safe_date_parse(date_str, default):
    """Safely parse a date string (ISO 8601 format). Return a default value if parsing fails.

    Args:
        date_str (str): The date string to parse.
        default (datetime): The default value to return if parsing fails.

    Returns:
        datetime: The parsed date or the default value if parsing fails.
    """
    try:
        return parse(date_str).replace(tzinfo=None)
    except (ValueError, TypeError):
        return default

def generate_year_playlists(tracks, destination):
    """Generate playlists based on the year and genre within that year.

    Args:
        tracks (list): List of track dictionaries.
        destination (str): The base directory to save the playlists.
    """
    year_dir = os.path.join(destination, '_year')
    os.makedirs(year_dir, exist_ok=True)

    year_genre_dir = os.path.join(destination, '_genre')
    os.makedirs(year_genre_dir, exist_ok=True)

    tracks_by_year = defaultdict(list)
    tracks_by_year_genre = defaultdict(lambda: defaultdict(list))

    for track in tqdm(tracks, desc="Categorising tracks by year and genre"):
        release_date = safe_date_parse(track.get('PremiereDate', '') or track.get('ProductionYear', ''), datetime.min)
        if release_date.year == datetime.min.year:
            continue
        year = release_date.year
        tracks_by_year[year].append(track)
        for genre in track.get('Genres', []):
            tracks_by_year_genre[year][genre].append(track)

    for year, tracks in tqdm(tracks_by_year.items(), desc="Writing year playlists"):
        year_filename = os.path.join(year_dir, f'{year}.m3u')
        sorted_tracks = sorted(tracks, key=lambda x: safe_date_parse(x.get('PremiereDate', ''), datetime.min))
        write_m3u_playlist(year_filename, sorted_tracks)

    for year, genres in tqdm(tracks_by_year_genre.items(), desc="Writing year-genre playlists"):
        for genre, tracks in genres.items():
            genre_year_filename = os.path.join(year_genre_dir, f'{normalize_filename(genre)}_{year}.m3u')
            sorted_tracks = sorted(tracks, key=lambda x: safe_date_parse(x.get('PremiereDate', ''), datetime.min))
            write_m3u_playlist(genre_year_filename, sorted_tracks, genre=genre)

def generate_decade_playlists(tracks, destination):
    """Generate playlists based on the decade and genre within that decade.

    Args:
        tracks (list): List of track dictionaries.
        destination (str): The base directory to save the playlists.
    """
    decade_dir = os.path.join(destination, '_decade')
    os.makedirs(decade_dir, exist_ok=True)

    decade_genre_dir = os.path.join(destination, '_genre')
    os.makedirs(decade_genre_dir, exist_ok=True)

    tracks_by_decade = defaultdict(list)
    tracks_by_decade_genre = defaultdict(lambda: defaultdict(list))

    for track in tqdm(tracks, desc="Categorising tracks by decade and genre"):
        release_date = safe_date_parse(track.get('PremiereDate', '') or track.get('ProductionYear', ''), datetime.min)
        if release_date.year == datetime.min.year:
            continue
        decade = (release_date.year // 10) * 10
        tracks_by_decade[decade].append(track)
        for genre in track.get('Genres', []):
            tracks_by_decade_genre[decade][genre].append(track)

    for decade, tracks in tqdm(tracks_by_decade.items(), desc="Writing decade playlists"):
        decade_filename = os.path.join(decade_dir, f'{decade}s.m3u')
        sorted_tracks = sorted(tracks, key=lambda x: safe_date_parse(x.get('PremiereDate', ''), datetime.min))
        write_m3u_playlist(decade_filename, sorted_tracks)

    for decade, genres in tqdm(tracks_by_decade_genre.items(), desc="Writing decade-genre playlists"):
        for genre, tracks in genres.items():
            genre_decade_filename = os.path.join(decade_genre_dir, f'{normalize_filename(genre)}_{decade}s.m3u')
            sorted_tracks = sorted(tracks, key=lambda x: safe_date_parse(x.get('PremiereDate', ''), datetime.min))
            write_m3u_playlist(genre_decade_filename, sorted_tracks, genre=genre)

def sizeof_fmt(num, suffix='B'):
    """Convert file size to a readable format."""
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Y{suffix}"

def sync_tracks_in_batches(tracks_to_sync, batch_size=1):
    """Sync tracks to Azuracast in batches.
       
    Args:
        tracks_to_sync (list): List of tracks to sync.
        batch_size (int): Number of tracks to upload per batch.
    """
    azuracast_sync = AzuraCastSync()

    total_batches = (len(tracks_to_sync) + batch_size - 1) // batch_size  # Calculate total number of batches

    with tqdm(total=total_batches, desc="Uploading batches", unit="batch") as batch_prog:
        for i in range(0, len(tracks_to_sync), batch_size):
            batch = tracks_to_sync[i:i + batch_size]

            with tqdm(total=len(batch), desc=f"Batch {i // batch_size + 1}", unit="file") as file_prog:
                for track, azuracast_file_path in batch:
                    try:
                        file_content = get_emby_file_content(track)
                        
                        # Log file size in a readable format before uploading
                        file_size = sizeof_fmt(len(file_content))
                        logger.debug(f"Uploading file: {azuracast_file_path}, Size: {file_size}")
                        
                        azuracast_sync.upload_file_to_azuracast(file_content, azuracast_file_path)
                        file_prog.update(1)  # Update progress for each file
                    except Exception as e:
                        logger.error(f"Failed to upload {file_size} {azuracast_file_path} to Azuracast: {e}")
                        # Continue to next file in case of failure

            batch_prog.update(1)  # Update progress for each batch

def generate_azuracast_file_path(track):
    """Generate file path used to store file in AzuraCast."""
    artist_name = track.get('AlbumArtist', 'Unknown Artist')
    album_name = f"{track.get('Album', 'Unknown Album')} ({track.get('ProductionYear', 'Unknown Year')})"
    disk_number = track.get('ParentIndexNumber', 1)
    track_number = track.get('IndexNumber', 1)
    title = track.get('Name', 'Unknown Title')
    file_path = track.get('Path')
    file_extension = os.path.splitext(file_path)[1]
    
    return f"{artist_name}/{album_name}/{disk_number:02d} {track_number:02d} {title}{file_extension}"

def initialize_playlist_manager():
    """Initialize PlaylistManager with tracks and genres from Emby data."""
    playlist_manager = PlaylistManager()
    emby_tracks = fetch_tracks_from_emby()
    
    # Add tracks to PlaylistManager
    for track in emby_tracks:
        playlist_manager.add_track(track)
    
    # Generate and add genres. This is where pre-generated genres come in.
    for track in emby_tracks:
        for genre in track.get('Genres', []):
            playlist_manager.add_genre(genre, track['Id'])
    
    return playlist_manager

def cron_schedule(cron_expression):
    """Schedule the job based on the cron expression.

    Args:
        cron_expression (str): The cron expression for scheduling.
    """
    logger.info(f"Scheduling job with cron expression: {cron_expression}")

    while True:
        now = datetime.now()
        iter = croniter(cron_expression, now)
        next_run = iter.get_next(datetime)
        delay = (next_run - now).total_seconds()

        logger.info(f"Next run scheduled at {next_run} (in {delay} seconds)")
        sleep(delay)

        logger.info("Running scheduled job")
        generate_playlists()
        logger.info("Job execution completed")

if __name__ == "__main__":
    cron_expression = os.getenv('M3U_CRON')

    if cron_expression:
        try:
            # Validate cron expression
            croniter(cron_expression)
            logging.info(f"Cron expression is valid.")
            cron_schedule(cron_expression)
        except (ValueError, TypeError):
            logging.error(f"Invalid cron expression: {cron_expression}")
            exit(1)
    else:
        generate_playlists()