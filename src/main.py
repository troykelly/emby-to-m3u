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
import logging
import requests
from typing import List, Dict, Tuple, Any
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from radioplaylist.main import RadioPlaylistGenerator
from lastfm.main import LastFM
from azuracast.main import AzuraCastSync
from playlist.main import PlaylistManager
from util.main import normalize_filename, safe_date_parse, write_m3u_playlist
from dateutil.parser import parse
from croniter import croniter
from time import sleep

# Get the logging level from the environment, default to 'INFO' if not set or invalid
log_level = os.getenv('M3U_LOGGING_LEVEL', 'INFO').upper()
numeric_level = getattr(logging, log_level, None)
if not isinstance(numeric_level, int):
    raise ValueError(f'Invalid log level: {log_level}')

# Configure the basic logging settings with the specified log level
logging.basicConfig(level=numeric_level, format='%(levelname)s:%(name)s:%(message)s')

# Get a logger
logger = logging.getLogger(__name__)

VERSION = "__VERSION__"  # <-- This will be replaced during the release process

BATCH_SIZE = os.getenv('M3U_BATCH_SIZE', 1)

def generate_playlists() -> None:
    """Main function to generate m3u playlists for genres, artists, albums, and years."""
    destination = os.getenv('M3U_DESTINATION')
    if not destination:
        raise ValueError("Environment variable M3U_DESTINATION is not set.")

    logger.debug("Generating playlists")

    genre_dir, artist_dir, album_dir, year_dir, decade_dir, radio_dir = ensure_directories_exist(destination)

    # Initialize the PlaylistManager and fetch tracks from Emby
    playlist_manager = PlaylistManager()
    playlist_manager.fetch_tracks()  # Fetch and set tracks

    # Add tracks and genres to the PlaylistManager
    with tqdm(total=len(playlist_manager.tracks), desc="Adding tracks and genres", unit="track") as pbar:
        for track in playlist_manager.tracks:
            playlist_manager.add_track(track)
            for genre in track.get('Genres', []):
                playlist_manager.add_genre(genre, track['Id'])
            pbar.update(1)

    # Process tracks to categorize by genre, artist, and album
    playlist_manager.categorize_tracks()

    # Write out playlists to the filesystem
    playlist_manager.write_playlists(genre_dir, artist_dir, album_dir, year_dir, decade_dir)
    playlist_manager.generate_genre_markdown(f"{destination}/genres.md")

    min_radio_duration = 14400  # Example duration for radio playlist in seconds (e.g., 86400 for 24 hours)

    azuracast_sync = AzuraCastSync()
    lastfm = LastFM()
    radio_generator = RadioPlaylistGenerator(playlist_manager, lastfm, azuracast_sync)

    # Generate radio playlists in batches
    radio_playlist_items = list(radio_generator.playlists.items())
    generate_playlists_in_batches(radio_generator, azuracast_sync, lastfm, radio_playlist_items, min_radio_duration, radio_dir, BATCH_SIZE)

    logger.debug("Playlists generated successfully")


def ensure_directories_exist(destination: str) -> Tuple[str, str, str, str, str, str]:
    """Ensure the required directories exist.

    Args:
        destination: Base directory to ensure exists.

    Returns:
        Directories for genre, artist, album, year, decade, and radio playlists.
    """
    genre_dir = os.path.join(destination, '_genre')
    artist_dir = os.path.join(destination, '_artist')
    album_dir = os.path.join(destination, '_album')
    year_dir = os.path.join(destination, '_year')
    decade_dir = os.path.join(destination, '_decade')
    radio_dir = os.path.join(destination, '_radio')
    os.makedirs(destination, exist_ok=True)
    os.makedirs(genre_dir, exist_ok=True)
    os.makedirs(artist_dir, exist_ok=True)
    os.makedirs(album_dir, exist_ok=True)
    os.makedirs(year_dir, exist_ok=True)
    os.makedirs(decade_dir, exist_ok=True)
    os.makedirs(radio_dir, exist_ok=True)
    return genre_dir, artist_dir, album_dir, year_dir, decade_dir, radio_dir


def generate_and_upload_radio_playlist(
    radio_generator: RadioPlaylistGenerator,
    azuracast_sync: AzuraCastSync,
    lastfm: LastFM,
    time_segment: str,
    genres: List[str],
    min_radio_duration: int,
    radio_dir: str
) -> None:
    """Generates and uploads a single radio playlist.

    Args:
        radio_generator: The playlist generator instance.
        azuracast_sync: The AzuraCast synchronization instance.
        lastfm: The LastFM instance.
        time_segment: The time segment for the playlist.
        genres: List of genres for the playlist.
        min_radio_duration: Minimum duration for the playlist.
        radio_dir: The directory to save the playlist.
    """
    # Ensure thread-local network context is set
    lastfm.cache.set_network(lastfm.network)

    playlist = radio_generator.generate_playlist(genres, min_radio_duration, time_segment)
    if not playlist:
        logger.error(f"Generated {time_segment} radio playlist is empty. Nothing to upload.")
        return

    playlist_name = time_segment
    radio_playlist_filename = os.path.join(radio_dir, f'{normalize_filename(playlist_name)}.m3u')
    write_m3u_playlist(radio_playlist_filename, playlist)

    if azuracast_sync.upload_playlist(playlist):
        azuracast_sync.sync_playlist(playlist_name, playlist)
    logger.debug(f"Successfully generated and uploaded playlist for {time_segment}")


def generate_playlists_in_batches(
    radio_generator: RadioPlaylistGenerator,
    azuracast_sync: AzuraCastSync,
    lastfm: LastFM,
    radio_playlist_items: List[Tuple[str, List[str]]],
    min_radio_duration: int,
    radio_dir: str,
    batch_size: int = 5
) -> None:
    """Generate playlists in parallel batches.

    Args:
        radio_generator: The playlist generator instance.
        azuracast_sync: The AzuraCast synchronization instance.
        lastfm: The LastFM instance.
        radio_playlist_items: List of time segments and their genres.
        min_radio_duration: Minimum duration for the playlists.
        radio_dir: Directory to save the playlists.
        batch_size: Number of parallel tasks to run.
    """
    with ThreadPoolExecutor(max_workers=batch_size) as executor:
        futures = [
            executor.submit(
                generate_and_upload_radio_playlist,
                radio_generator,
                azuracast_sync,
                lastfm,
                time_segment,
                genres,
                min_radio_duration,
                radio_dir
            )
            for time_segment, genres in radio_playlist_items
        ]

        with tqdm(total=len(futures), desc="Generating radio playlists", unit="playlist") as pbar:
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error generating playlist: {e}")
                finally:
                    pbar.update(1)


def get_emby_data(endpoint: str) -> Dict[str, Any]:
    """Retrieve data from a given Emby API endpoint.

    Args:
        endpoint: The specific API endpoint to fetch data from.

    Returns:
        The data retrieved from the Emby API.
    """
    emby_server_url = os.getenv('EMBY_SERVER_URL')
    emby_api_key = os.getenv('EMBY_API_KEY')
    url = f'{emby_server_url}{endpoint}&api_key={emby_api_key}'
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def generate_year_playlists(tracks: List[Dict[str, Any]], destination: str) -> None:
    """Generate playlists based on the year and genre within that year.

    Args:
        tracks: List of track dictionaries.
        destination: The base directory to save the playlists.
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


def generate_decade_playlists(tracks: List[Dict[str, Any]], destination: str) -> None:
    """Generate playlists based on the decade and genre within that decade.

    Args:
        tracks: List of track dictionaries.
        destination: The base directory to save the playlists.
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

def cron_schedule(cron_expression: str) -> None:
    """Schedule the job based on the cron expression.

    Args:
        cron_expression: The cron expression for scheduling.
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
    if VERSION != "__VERSION__":
        logging.info(f"M3U to AzureCast Version {VERSION}")
        
    cron_expression = os.getenv('M3U_CRON')

    if cron_expression:
        try:
            # Validate cron expression
            croniter(cron_expression)
            logging.info("Cron expression is valid.")
            cron_schedule(cron_expression)
        except (ValueError, TypeError):
            logging.error(f"Invalid cron expression: {cron_expression}")
            exit(1)
    else:
        generate_playlists()