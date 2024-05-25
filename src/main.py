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
import re
import requests
import tempfile
import shutil
import schedule
import time
import logging
import random
from datetime import datetime
from dateutil.parser import parse
from collections import defaultdict, Counter
from tqdm import tqdm
from croniter import croniter
from azuracast.main import AzuraCastSync
from lastfm.main import LastFM

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PlaylistManager:
    """Manages music tracks and playlist generation."""

    def __init__(self):
        """Initializes PlaylistManager with empty tracks and playlists."""
        self.tracks = []
        self.playlists = {'genres': defaultdict(list), 'artists': defaultdict(list), 'albums': defaultdict(list)}
        self.artist_counter = Counter()
        self.album_counter = Counter()
        self.tracks_to_sync = []

    def fetch_tracks(self):
        """Fetch all audio items with basic metadata from Emby."""
        all_audio_items = get_emby_data(
            '/Items?Recursive=true&IncludeItemTypes=Audio&Fields='
            'Path,RunTimeTicks,Name,Album,AlbumArtist,Genres,IndexNumber,ProductionYear,PremiereDate,ExternalIds,MusicBrainzAlbumId,MusicBrainzArtistId,MusicBrainzReleaseGroupId,ParentIndexNumber,ProviderIds,TheAudioDbAlbumId,TheAudioDbArtistId&SortBy=SortName&SortOrder=Ascending'
        )
        self.tracks = all_audio_items['Items']

    def process_tracks(self):
        """Process tracks to categorize them by genre, artist, and album."""
        azuracast_sync = AzuraCastSync()
        known_tracks = azuracast_sync.get_known_tracks()

        for track in tqdm(self.tracks, desc="Processing tracks"):
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
        """Disambiguate artist and album names if they have the same name."""
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
        """Write the genre, artist, and album playlists to their respective directories."""
        default_date = datetime.min

        for genre, tracks in tqdm(self.playlists['genres'].items(), desc="Writing genre playlists"):
            genre_filename = os.path.join(genre_dir, f'{normalize_filename(genre)}.m3u')
            write_m3u_playlist(genre_filename, tracks, genre=genre)

        for disambiguated_artist, tracks in tqdm(self.playlists['artists'].items(), desc="Writing artist playlists"):
            if tracks:
                tracks.sort(key=lambda x: (
                    safe_date_parse(x.get('PremiereDate', ''), default_date),
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
        """Sync tracks to Azuracast if necessary."""
        if os.getenv('AZURACAST_HOST') and os.getenv('AZURACAST_API_KEY') and os.getenv('AZURACAST_STATIONID'):
            sync_tracks_in_batches(self.tracks_to_sync, batch_size=5)

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
            path = strip_path_prefix(path)
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
                
                # Write the final path without prefix
                f.write(f'{strip_path_prefix(path)}\n')
        
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
    for unit in ['','K','M','G','T','P','E','Z']:
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
        time.sleep(delay)

        logger.info("Running scheduled job")
        generate_playlists()
        logger.info("Job execution completed")

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

def create_dynamic_radio_playlist(tracks, time_of_day, lastfm, target_duration=28800):
    """Create dynamic radio playlists based on time of day using LastFM recommendations.

    Args:
        tracks (list): List of track dictionaries.
        time_of_day (str): Time of day ('morning', 'afternoon', 'evening').
        lastfm (LastFM): LastFM client for fetching recommendations.
        target_duration (int, optional): Target duration for the playlist in seconds. Default is 28800 seconds (8 hours).

    Returns:
        list: List of selected tracks for the radio playlist.
    """
    seed_genres = {
        'morning': ['Rock', 'Pop'],
        'afternoon': ['Hip-Hop', 'Dance'],
        'evening': ['Jazz', 'Blues']
    }
    
    selected_genres = seed_genres.get(time_of_day, [])
    selected_tracks = []
    seen_track_ids = set()
    playlist_duration = 0

    while playlist_duration < target_duration:
        for genre in selected_genres:
            genre_tracks = [track for track in tracks if genre in track.get('Genres', [])]
            
            if genre_tracks:
                seed_track = random.choice(genre_tracks)  # Pick a random track from the genre
                seed_artist = seed_track.get('AlbumArtist')
                seed_title = seed_track.get('Name')
                
                similar_tracks, _ = lastfm.get_similar_tracks(seed_artist, seed_title)

                # Add the seed track to the playlist if it's not already in the set
                if seed_track['Id'] not in seen_track_ids:
                    selected_tracks.append(seed_track)
                    seen_track_ids.add(seed_track['Id'])
                    playlist_duration += seed_track.get('RunTimeTicks', 0) // 10000000  # Convert ticks to seconds

                # Add similar tracks from Emby library by cross-referencing with similar tracks obtained from Last.fm
                similar_track_titles = [similar_track.item.title for similar_track in similar_tracks]
                
                for track in tracks:
                    if track.get('Name') in similar_track_titles and track['Id'] not in seen_track_ids:
                        selected_tracks.append(track)
                        seen_track_ids.add(track['Id'])
                        playlist_duration += track.get('RunTimeTicks', 0) // 10000000  # Convert ticks to seconds
                        
                        # Break early if target duration is reached
                        if playlist_duration >= target_duration:
                            break
            # Break early if target duration is reached
            if playlist_duration >= target_duration:
                break
    
    return selected_tracks  # Return the list of unique selected tracks up to the target duration

def generate_radio_playlists(tracks):
    """Generate dynamic radio playlists based on different times of the day.

    Args:
        tracks (list): List of track dictionaries.
    """
    destination = os.getenv('M3U_DESTINATION')
    if not destination:
        raise ValueError("Environment variable M3U_DESTINATION is not set.")

    radio_dir = os.path.join(destination, '_radio')
    os.makedirs(radio_dir, exist_ok=True)

    time_segments = ['morning', 'afternoon', 'evening']
    
    lastfm = LastFM()  # Initialize LastFM client

    for time_segment in time_segments:
        if lastfm.network:  # Proceed if LastFM network is initialized
            radio_playlist = create_dynamic_radio_playlist(tracks, time_segment, lastfm)
            if radio_playlist:
                radio_filename = os.path.join(radio_dir, f'radio_{time_segment}.m3u')
                write_m3u_playlist(radio_filename, radio_playlist)
        else:
            logger.error("LastFM network is not initialized. Skipping dynamic playlist generation.")

def generate_playlists():
    """Main function to generate m3u playlists for genres, artists, albums, and years."""
    destination = os.getenv('M3U_DESTINATION')
    if not destination:
        raise ValueError("Environment variable M3U_DESTINATION is not set.")

    logger.info("Generating playlists")
    
    genre_dir, artist_dir, album_dir = ensure_directories_exist(destination)

    manager = PlaylistManager()
    manager.fetch_tracks()
    manager.process_tracks()
    manager.disambiguate_names()
    manager.write_playlists(genre_dir, artist_dir, album_dir)
    generate_year_playlists(manager.tracks, destination)
    generate_decade_playlists(manager.tracks, destination)
    # manager.sync_tracks()

    generate_radio_playlists(manager.tracks)  # Generate dynamic radio playlists after generating other playlists

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