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
import sys
import signal
import pytz
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
from reporting import PlaylistReport
from dateutil.parser import parse
from croniter import croniter
from time import sleep

from logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

VERSION = "__VERSION__"  # <-- This will be replaced during the release process

TIMEZONE = os.getenv('TZ', 'Etc/UTC')

DAY_NAMES = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        # Allow the default exception handler for KeyboardInterrupt
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

def handle_signal(signum, frame):
    logger.critical(f"Received signal {signum}. Exiting.")
    sys.exit(1)

def get_batch_size(default=1):
    batch_size_str = os.getenv('M3U_BATCH_SIZE', None)
    if batch_size_str is None:
        logger.warning(f"M3U_BATCH_SIZE not set, using default of {default}.")
        return default

    try:
        return int(batch_size_str)
    except ValueError:
        logger.warning(f"Invalid M3U_BATCH_SIZE '{batch_size_str}', using default of {default}.")
        return default

def get_day_order_reference(timezone_str: str = "Etc/UTC") -> List[str]:
    """Determine the day order reference based on the provided timezone.
    
    If the local time is after 6pm, use the next day,
    otherwise, use today.

    Args:
        timezone_str: A string representing the timezone (e.g., "Australia/Sydney").
                      Defaults to "Etc/UTC".

    Returns:
        A list of day names starting from the reference day.
    """
    try:
        timezone = pytz.timezone(timezone_str)
    except pytz.UnknownTimeZoneError:
        timezone = pytz.timezone("Etc/UTC")
    
    now = datetime.now(timezone)
    if now.hour >= 18:
        # After 6pm, use the next day
        current_day_index = (now.weekday() + 1) % 7
    else:
        # Before 6pm, use today
        current_day_index = now.weekday()
    
    return [DAY_NAMES[(current_day_index + i) % 7] for i in range(7)]

def order_radio_playlist_items(radio_playlist_items: List[Tuple[str, List[str]]]) -> List[Tuple[str, List[str]]]:
    """Order the radio playlist items based on the day name and other criteria."""
    day_order = get_day_order_reference()
    
    def playlist_order_key(item: Tuple[str, List[str]]) -> Tuple[int, int]:
        time_segment, _ = item
        time_segment_lower = time_segment.lower()
        
        # Determine day position
        day_position = next((idx for idx, day in enumerate(day_order) if day in time_segment_lower), 8)  # Default to 8 if no day name
        
        # Determine if there's no day name
        no_day_present = 1 if any(day in time_segment_lower for day in DAY_NAMES) else 0
        
        return (no_day_present, day_position)
    
    # Sort by the criteria: no day name first, then by the day order
    return sorted(radio_playlist_items, key=playlist_order_key)

def generate_playlists() -> None:
    """Main function to generate m3u playlists for genres, artists, albums, and years."""
    destination = os.getenv('M3U_DESTINATION')
    if not destination:
        raise ValueError("Environment variable M3U_DESTINATION is not set.")
    
    report = PlaylistReport()

    logger.debug("Generating playlists")

    genre_dir, artist_dir, album_dir, year_dir, decade_dir, radio_dir = ensure_directories_exist(destination)

    # Initialize the PlaylistManager and fetch tracks from Emby
    playlist_manager = PlaylistManager(report)
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

    # Unless env `M3U_DONT_WRITE_M3U` is set, write out playlists to the filesystem
    if not os.getenv('M3U_DONT_WRITE_M3U'):
        playlist_manager.write_playlists(genre_dir, artist_dir, album_dir, year_dir, decade_dir)
    playlist_manager.generate_genre_markdown(f"{destination}/genres.md")

    min_radio_duration = 14400  # Example duration for radio playlist in seconds (e.g., 86400 for 24 hours)

    azuracast_sync = AzuraCastSync()
    lastfm = LastFM()
    radio_generator = RadioPlaylistGenerator(playlist_manager, lastfm, azuracast_sync)

    # Generate radio playlists in batches
    radio_playlist_items = order_radio_playlist_items(list(radio_generator.playlists.items()))
    
    generate_playlists_in_batches(radio_generator, azuracast_sync, lastfm, radio_playlist_items, min_radio_duration, radio_dir, get_batch_size())

    logger.debug("Playlists generated successfully")
    
    report_content = report.generate_markdown()  # Generate the report
    report_pdf = report.generate_pdf()  # Generate the PDF report
        
    # Write report to the M3U directory
    report_filename = os.path.join(destination, 'report.md')
    report_pdf_filename = os.path.join(destination, 'report.pdf')
    with open(report_filename, 'w') as f:
        f.write(report_content)
    with open(report_pdf_filename, 'wb') as f:
        f.write(report_pdf)

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
    lastfm.cache.set_network(lastfm.network)
    
    total_available_tracks = 0
    available_genres = []
    for genre in genres:
        normalized_genre = radio_generator.playlist_manager._normalize_genre(genre)
        if normalized_genre is None:
            logger.warning(f"Skipping invalid genre: {genre}")
            continue        
        track_count = radio_generator.playlist_manager.get_track_count_for_genre(normalized_genre)
        total_available_tracks += track_count
        if track_count > 0:
            available_genres.append(normalized_genre)
            logger.debug(f"Genre: {normalized_genre} has {track_count} tracks available for playlist generation.")
        else:
            logger.warning(f"No tracks available for genre: {normalized_genre}. Not using for playlist generation.")
            
    if len(available_genres) == 0:
        logger.warning(f"No tracks available for genres: {genres}. Skipping generation.")
        return
    
    logger.debug(f"Generating playlist for genres: {available_genres} ({total_available_tracks} tracks) in time segment: {time_segment}")

    playlist = radio_generator.generate_playlist(available_genres, min_radio_duration, time_segment)
    if not playlist:
        logger.error(f"Generated {time_segment} radio playlist is empty. Nothing to upload.")
        return

    playlist_name = time_segment
    radio_playlist_filename = os.path.join(radio_dir, f'{normalize_filename(playlist_name)}.m3u')
    write_m3u_playlist(radio_playlist_filename, playlist)

    if not os.getenv('M3U_DONT_SYNC_AZURACAST'):
        if azuracast_sync.upload_playlist(playlist):
            azuracast_sync.sync_playlist(playlist_name, playlist)

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
    # Install exception handler for uncaught exceptions
    sys.excepthook = handle_exception

    # Register signal handlers
    signals_to_catch = [signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT]

    for sig in signals_to_catch:
        signal.signal(sig, handle_signal)

    try:
        if VERSION != "__VERSION__":
            logger.info(f"M3U to AzureCast Version {VERSION}")

        cron_expression = os.getenv('M3U_CRON')

        if cron_expression:
            try:
                # Validate cron expression
                croniter(cron_expression)
                logger.info("Cron expression is valid.")
                cron_schedule(cron_expression)
            except (ValueError, TypeError):
                logger.error(f"Invalid cron expression: {cron_expression}")
                sys.exit(1)
        else:
            generate_playlists()
    except Exception as e:
        logger.error("Exception in main execution block:", exc_info=True)
        sys.exit(1)
