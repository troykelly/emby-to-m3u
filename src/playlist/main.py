# src/playlist/main.py

import os
import logging
import requests
from collections import defaultdict, Counter
from datetime import datetime
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from tqdm import tqdm
from dateutil.parser import parse
from util.main import normalize_filename, write_m3u_playlist
from reporting import PlaylistReport
from logger import setup_logging

if TYPE_CHECKING:
    from track.main import Track  # Avoids direct import at the module level
from azuracast.main import AzuraCastSync

setup_logging()
logger = logging.getLogger(__name__)

class PlaylistManager:
    """Manages music tracks and playlist generation."""

    def __init__(self, report: PlaylistReport) -> None:
        """Initializes PlaylistManager with empty tracks and playlists."""
        self.tracks: List['Track'] = []
        self.track_map: Dict[str, 'Track'] = {}
        self.genres: Dict[str, List[str]] = defaultdict(list)
        self.playlists: Dict[str, Dict[str, List['Track']]] = {
            'genres': defaultdict(list),
            'artists': defaultdict(list),
            'albums': defaultdict(list),
            'years': defaultdict(list),
            'decades': defaultdict(list)
        }
        self.artist_counter: Counter = Counter()
        self.album_counter: Counter = Counter()
        self.tracks_to_sync: List['Track'] = []
        self.ignored_genres: List[str] = [
            self._normalize_genre(genre.strip()) for genre in os.getenv('TRACK_IGNORE_GENRE', '').split(',')
        ]
        self.report = report

    def add_track(self, track: 'Track') -> None:
        """Adds a track to the PlaylistManager.

        Args:
            track: Track metadata dictionary.
        """
        if 'Id' not in track:
            raise ValueError("Track must have an 'Id' field.")
        self.track_map[track['Id']] = track
        if track not in self.tracks:
            self.tracks.append(track)

    def add_genre(self, genre: str, track_id: str) -> None:
        """Associates a track ID with a genre.

        Args:
            genre: Genre name.
            track_id: Track ID.
        """
        normalized_genre = self._normalize_genre(genre)
        if normalized_genre is None:
            logger.warning(f"Track ID {track_id} has an invalid genre: {genre}")
            return
        self.genres[normalized_genre].append(track_id)
        
    def get_track_count_for_genre(self, genre: str) -> int:
        """Retrieves the number of tracks for a given genre.

        Args:
            genre: Genre name.

        Returns:
            The number of tracks for the given genre.
        """
        normalized_genre = self._normalize_genre(genre)
        return len(self.genres[normalized_genre])

    def get_tracks_by_genre(self, genre: str) -> List['Track']:
        """Retrieves a list of tracks for a given genre.

        Args:
            genre: Genre name.

        Returns:
            List of track dictionaries.
        """
        normalized_genre = self._normalize_genre(genre)
        return [self.track_map[track_id] for track_id in self.genres[normalized_genre]]

    @staticmethod
    def _normalize_genre(genre: Optional[str]) -> Optional[str]:
        """Normalize genre name to ensure consistent format."""
        if not genre:
            return None
        return genre.strip().lower()

    def get_track_by_id(self, track_id: str) -> Optional['Track']:
        """Retrieves a track by its ID.

        Args:
            track_id: Track ID.

        Returns:
            Track metadata dictionary if found, None otherwise.
        """
        return self.track_map.get(track_id)
    
    def get_track_by_title_and_artist(self, title: str, artist: str) -> Optional[Dict[str, Any]]:
        """Retrieve a track by its title and artist name.

        Args:
            title: The title of the track.
            artist: The name of the artist.

        Returns:
            The track metadata dictionary if found, None otherwise.
        """
        for track in self.track_map.values():
            track_name = track.get('Name')
            album_artist = track.get('AlbumArtist')
            
            if isinstance(track_name, str) and isinstance(album_artist, str):
                if track_name.lower() == title.lower() and album_artist.lower() == artist.lower():
                    return track
        return None


    def fetch_tracks(self) -> None:
        """Fetches all audio items with basic metadata from Emby."""
        with tqdm(total=1, desc="Fetching all tracks from Emby", unit="list") as list_prog:
            all_audio_items = self._get_emby_data(
                '/Items?Recursive=true&IncludeItemTypes=Audio&Fields='
                'Path,RunTimeTicks,Name,Album,AlbumArtist,Genres,IndexNumber,ProductionYear,PremiereDate,ExternalIds,'
                'MusicBrainzAlbumId,MusicBrainzArtistId,MusicBrainzReleaseGroupId,ParentIndexNumber,ProviderIds,'
                'TheAudioDbAlbumId,TheAudioDbArtistId&SortBy=SortName&SortOrder=Ascending'
            )
            list_prog.update(1)
            from track.main import Track  # Local import to avoid circular dependency
            self.tracks = [Track(item, self) for item in all_audio_items.get('Items', [])]

    def _get_emby_data(self, endpoint: str) -> Dict[str, Any]:
        """Retrieves data from a given Emby API endpoint.

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

    def categorize_tracks(self) -> None:
        """Categorizes tracks by genre, artist, album, year, and decade."""
        tracks_by_year = defaultdict(list)
        tracks_by_decade = defaultdict(list)

        for track in tqdm(self.tracks, desc="Categorizing tracks"):
            artist_name = track.get('AlbumArtist', 'Unknown Artist')
            album_name = f"{track.get('Album', 'Unknown Album')} ({track.get('ProductionYear', 'Unknown Year')})"
            disk_number = track.get('ParentIndexNumber', 1)
            track_number = track.get('IndexNumber', 1)
            title = track.get('Name', 'Unknown Title')
            file_path = track.get('Path')
            file_extension = os.path.splitext(file_path)[1]

            track_genres = track.get('Genres', [])
            if not track_genres:
                continue  # Skip tracks with no genre information
            
            # Skip tracks with ignored genres (case insensitive)
            if any(genre.lower() in self.ignored_genres for genre in track_genres):
                continue

            release_date = self._safe_date_parse(
                track.get('PremiereDate', '') or track.get('ProductionYear', ''),
                datetime.min
            )

            for genre in track_genres:
                self.playlists['genres'][genre].append(track)
                self.add_genre(genre, track['Id'])
                if release_date.year != datetime.min.year:
                    year = release_date.year
                    decade = (year // 10) * 10
                    if year:
                        self.playlists['genres'][f"{genre} {year}"].append(track)
                        self.add_genre(f"{genre} {year}", track['Id'])
                    if decade:
                        self.playlists['genres'][f"{genre} {decade}s"].append(track)
                        self.add_genre(f"{genre} {decade}s", track['Id'])

            artist_id = track.get('MusicBrainzArtistId') or track.get('AlbumArtistId') or track.get('AlbumArtist')
            if artist_id:
                artist_key = f"{artist_id}_{artist_name}"
                self.playlists['artists'][artist_key].append(track)
                self.artist_counter[artist_name] += 1

            album_id = track.get('MusicBrainzAlbumId') or track.get('AlbumId') or track.get('Album')
            if album_id:
                album_key = f"{album_id}_{album_name}"
                self.playlists['albums'][album_key].append(track)
                self.album_counter[album_name] += 1

            if release_date.year != datetime.min.year:
                year = release_date.year
                decade = (year // 10) * 10
                tracks_by_year[year].append(track)
                tracks_by_decade[decade].append(track)

        self.playlists['years'] = tracks_by_year
        self.playlists['decades'] = tracks_by_decade

    def disambiguate_names(self) -> None:
        """Disambiguates artist and album names if they have the same name."""
        disambiguated_artists = {}
        for artist_key, tracks in self.playlists['artists'].items():
            artist_id, artist_name = artist_key.split('_', 1)
            if self.artist_counter[artist_name] > 1:
                disambiguated_artist = f"{artist_name} ({artist_id})"
            else:
                disambiguated_artist = artist_name
            disambiguated_artists.setdefault(disambiguated_artist, []).extend(tracks)
        self.playlists['artists'] = disambiguated_artists

        disambiguated_albums = {}
        for album_key, tracks in self.playlists['albums'].items():
            album_id, album_name = album_key.split('_', 1)
            if self.album_counter[album_name] > 1:
                disambiguated_album = f"{album_name} ({album_id})"
            else:
                disambiguated_album = album_name
            disambiguated_albums.setdefault(disambiguated_album, []).extend(tracks)
        self.playlists['albums'] = disambiguated_albums

    def write_playlists(
        self, genre_dir: str, artist_dir: str, album_dir: str, 
        year_dir: str, decade_dir: str
    ) -> None:
        """Writes the genre, artist, album, year, and decade playlists to their respective directories.

        Args:
            genre_dir: Directory to save genre playlists.
            artist_dir: Directory to save artist playlists.
            album_dir: Directory to save album playlists.
            year_dir: Directory to save year playlists.
            decade_dir: Directory to save decade playlists.
        """
        default_date = datetime.min
        os.makedirs(year_dir, exist_ok=True)
        os.makedirs(decade_dir, exist_ok=True)

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

        for year, tracks in tqdm(self.playlists['years'].items(), desc="Writing year playlists"):
            year_filename = os.path.join(year_dir, f'{year}.m3u')
            tracks.sort(key=lambda x: self._safe_date_parse(x.get('PremiereDate', ''), default_date))
            write_m3u_playlist(year_filename, tracks)

        for decade, tracks in tqdm(self.playlists['decades'].items(), desc="Writing decade playlists"):
            decade_filename = os.path.join(decade_dir, f'{decade}s.m3u')
            tracks.sort(key=lambda x: self._safe_date_parse(x.get('PremiereDate', ''), default_date))
            write_m3u_playlist(decade_filename, tracks)

    def sync_tracks(self, azuracast_sync: AzuraCastSync) -> None:
        """Sync tracks to Azuracast."""
        if not os.getenv('AZURACAST_HOST') or not os.getenv('AZURACAST_API_KEY') or not os.getenv('AZURACAST_STATIONID'):
            logger.warning("Azuracast environment variables not set. Skipping track sync.")
            return

        total_tracks = len(self.tracks_to_sync)
        with tqdm(total=total_tracks, desc="Uploading batches", unit="batch") as track_prog:
            for track in self.tracks_to_sync:
                try:
                    file_content = track.download()
                    azuracast_sync.upload_file_to_azuracast(file_content, track['Path'])
                    track_prog.update(1)
                except Exception as e:
                    logger.error(f"Failed to upload file to Azuracast: {e}")

    def generate_genre_markdown(self, file_path: str) -> None:
        """Generates a markdown file with genres and track counts.

        Args:
            file_path: The path to the output markdown file.
        """
        genre_counts = {genre: len(tracks) for genre, tracks in self.playlists['genres'].items()}
        md_content = ["| Genre      | Tracks |", "| ---------- | ------ |"]
        for genre, count in genre_counts.items():
            md_content.append(f"| {genre} | {count} |")
        with open(file_path, 'w', encoding='utf-8') as md_file:
            md_file.write('\n'.join(md_content))

    @staticmethod
    def _safe_date_parse(date_str: str, default: datetime) -> datetime:
        """Safely parses a date string (ISO 8601 format). Returns a default value if parsing fails.

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
        
    def __enter__(self) -> 'PlaylistManager':
        """Enter the runtime context for this object."""
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Exit the runtime context, clean up resources."""
        self.tracks.clear()
        self.track_map.clear()
        self.genres.clear()
        self.playlists.clear()
        self.artist_counter.clear()
        self.album_counter.clear()
        self.tracks_to_sync.clear()
