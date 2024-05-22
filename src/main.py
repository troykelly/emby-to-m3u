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
from datetime import datetime
from dateutil.parser import parse
from collections import defaultdict, Counter
from tqdm import tqdm
from croniter import croniter

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

    for track in tracks:
        path = track.get('Path', '')
        if path and path not in existing_tracks:
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
            for track in existing_tracks:
                f.write(f'{track}\n')

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
                f.write(f'{path}\n')
        
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

def generate_playlists():
    """Main function to generate m3u playlists for genres, artists, albums, and years."""
    destination = os.getenv('M3U_DESTINATION')
    if not destination:
        raise ValueError("Environment variable M3U_DESTINATION is not set.")

    logger.info("Generating playlists")

    # Ensure base destination directory exists
    os.makedirs(destination, exist_ok=True)

    # Ensure subdirectories exist
    genre_dir = os.path.join(destination, '_genre')
    artist_dir = os.path.join(destination, '_artist')
    album_dir = os.path.join(destination, '_album')
    os.makedirs(genre_dir, exist_ok=True)
    os.makedirs(artist_dir, exist_ok=True)
    os.makedirs(album_dir, exist_ok=True)

    # Get all audio items with basic metadata
    all_audio_items = get_emby_data(
        '/Items?Recursive=true&IncludeItemTypes=Audio&Fields='
        'Path,RunTimeTicks,Name,Album,AlbumArtist,Genres,IndexNumber,ProductionYear,PremiereDate,ExternalIds,MusicBrainzAlbumId,MusicBrainzArtistId,MusicBrainzReleaseGroupId,ParentIndexNumber,ProviderIds,TheAudioDbAlbumId,TheAudioDbArtistId&SortBy=SortName&SortOrder=Ascending'
    )

    genres = defaultdict(list)
    artists = defaultdict(list)
    albums = defaultdict(list)
    artist_counter = Counter()
    album_counter = Counter()

    for track in tqdm(all_audio_items['Items'], desc="Processing tracks"):

        track_genres = track.get('Genres', [])
        if not track_genres:
            continue  # Skip tracks with no genre information

        # Add track to genre playlists
        for genre in track_genres:
            genres[genre].append(track)

        # Add track to artist playlists, use artist ID or album artist as a fallback
        artist_id = track.get('MusicBrainzArtistId') or track.get('AlbumArtistId') or track.get('AlbumArtist')
        artist_name = track.get('AlbumArtist', 'Unknown Artist')
        if artist_id:
            artist_key = (artist_id, artist_name)
            artists[artist_key].append(track)
            artist_counter[artist_name] += 1

        # Add track to album playlists, use album ID or album name as a fallback
        album_id = track.get('MusicBrainzAlbumId') or track.get('AlbumId') or track.get('Album')
        album_name = track.get('Album', 'Unknown Album')
        if album_id:
            album_key = (album_id, album_name)
            albums[album_key].append(track)
            album_counter[album_name] += 1

    # Disambiguate artist names only if they have the same name
    disambiguated_artists = {}
    for (artist_id, artist_name), tracks in artists.items():
        if artist_counter[artist_name] > 1:
            disambiguated_artist = f"{artist_name} ({artist_id})"
        else:
            disambiguated_artist = artist_name
        disambiguated_artists.setdefault(disambiguated_artist, []).extend(tracks)

    # Disambiguate album names only if they have the same name
    disambiguated_albums = {}
    for (album_id, album_name), tracks in albums.items():
        if album_counter[album_name] > 1:
            disambiguated_album = f"{album_name} ({album_id})"
        else:
            disambiguated_album = album_name
        disambiguated_albums.setdefault(disambiguated_album, []).extend(tracks)

    # Default date for unmatched PremiereDate or ProductionYear
    default_date = datetime.min

    # Write genre playlists
    for genre, tracks in tqdm(genres.items(), desc="Writing genre playlists"):
        genre_filename = os.path.join(genre_dir, f'{normalize_filename(genre)}.m3u')
        write_m3u_playlist(genre_filename, tracks, genre=genre)

    # Write artist playlists
    for disambiguated_artist, tracks in tqdm(disambiguated_artists.items(), desc="Writing artist playlists"):
        if tracks:
            # Sort tracks by release date, then by disc number and track number
            tracks.sort(key=lambda x: (
                safe_date_parse(x.get('PremiereDate', ''), default_date),
                x.get('ParentIndexNumber', 0),
                x.get('IndexNumber', 0)
            ))
            artist_filename = os.path.join(artist_dir, f'{normalize_filename(disambiguated_artist)}.m3u')
            write_m3u_playlist(artist_filename, tracks, artist=disambiguated_artist)

    # Write album playlists
    for disambiguated_album, tracks in tqdm(disambiguated_albums.items(), desc="Writing album playlists"):
        if tracks:
            # Sort tracks by their index number or track number
            tracks.sort(key=lambda x: x.get('IndexNumber', 0))
            album_filename = os.path.join(album_dir, f'{normalize_filename(disambiguated_album)}.m3u')
            write_m3u_playlist(album_filename, tracks, album=disambiguated_album)

    # Generate and write year-based playlists
    generate_year_playlists(all_audio_items['Items'], destination)

    # Generate and write decade-based playlists
    generate_decade_playlists(all_audio_items['Items'], destination)

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