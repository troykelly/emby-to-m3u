import os
import pylast
import logging
import json
import hashlib
import sqlite3
from typing import List, Dict, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# Set the logging level for pylast and httpx to WARN
logging.getLogger('pylast').setLevel(logging.WARN)
logging.getLogger('httpx').setLevel(logging.WARN)

# Environment variables for LastFM API
API_KEY = os.getenv('LAST_FM_API_KEY')
API_SECRET = os.getenv('LAST_FM_API_SECRET')
USERNAME = os.getenv('LAST_FM_USERNAME', '')
PASSWORD_HASH = pylast.md5(os.getenv('LAST_FM_PASSWORD', ''))

class LastFMCache:
    """Simple cache to store LastFM responses to minimize API traffic."""

    def __init__(self, cache_file: str = 'lastfm_cache.db') -> None:
        """Initializes the LastFMCache with a SQLite database.

        Args:
            cache_file: Path to the SQLite database file.
        """
        self.cache_file = cache_file
        self.connection = sqlite3.connect(self.cache_file, check_same_thread=False)
        self._init_db()

    def _init_db(self) -> None:
        """Initializes the database and creates tables if they don't exist."""
        with self.connection as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    similar_tracks TEXT,
                    similar_artists TEXT
                )
            ''')
            conn.commit()

    def get_cache_key(self, artist_name: str, track_name: str) -> str:
        """Generates a unique cache key for the given artist and track.

        Args:
            artist_name: Name of the artist.
            track_name: Name of the track.

        Returns:
            A unique cache key.
        """
        key = f"{artist_name}-{track_name}"
        return hashlib.md5(key.encode('utf-8')).hexdigest()

    def get(self, artist_name: str, track_name: str) -> Optional[Tuple[List[pylast.Track], List[pylast.Artist]]]:
        """Retrieves cached data for a given artist and track.

        Args:
            artist_name: Name of the artist.
            track_name: Name of the track.

        Returns:
            A tuple of lists containing similar tracks and similar artists, or None if not in cache.
        """
        key = self.get_cache_key(artist_name, track_name)
        with self.connection as conn:
            cursor = conn.execute('SELECT similar_tracks, similar_artists FROM cache WHERE key = ?', (key,))
            row = cursor.fetchone()
            if row:
                similar_tracks = json.loads(row[0])
                similar_artists = json.loads(row[1])
                similar_tracks = [self._deserialize_track(t) for t in similar_tracks if t]
                similar_artists = [self._deserialize_artist(a) for a in similar_artists if a]
                logger.debug(f"Deserialized tracks: {similar_tracks}")
                logger.debug(f"Deserialized artists: {similar_artists}")
                return similar_tracks, similar_artists
        return None

    def set(self, artist_name: str, track_name: str, similar_tracks: List[pylast.Track], similar_artists: List[pylast.Artist]) -> None:
        """Caches similar tracks and artists for a given artist and track.

        Args:
            artist_name: Name of the artist.
            track_name: Name of the track.
            similar_tracks: List of similar tracks.
            similar_artists: List of similar artists.
        """
        key = self.get_cache_key(artist_name, track_name)
        similar_tracks_json = [self._serialize_track(t) for t in similar_tracks if t]
        similar_artists_json = [self._serialize_artist(a) for a in similar_artists if a]
        with self.connection as conn:
            conn.execute('''
                INSERT OR REPLACE INTO cache (key, similar_tracks, similar_artists) 
                VALUES (?, ?, ?)
            ''', (key, json.dumps(similar_tracks_json), json.dumps(similar_artists_json)))
            conn.commit()

    def _serialize_track(self, track: pylast.Track) -> Optional[Dict[str, Any]]:
        """Serializes a pylast Track object into a JSON serializable dictionary.

        Args:
            track: The pylast Track object.

        Returns:
            A dictionary representing the serialized track, or None if serialization fails.
        """
        try:
            serialized = {
                'title': track.title,
                'artist': track.artist.name,
                'url': track.url
            }
            logger.debug(f"Serialized track: {serialized}")
            return serialized
        except AttributeError as e:
            logger.error(f"Failed to serialize track: {track}, error: {e}")
            return None

    def _deserialize_track(self, track_dict: Dict[str, Any]) -> Optional[pylast.Track]:
        """Deserializes a dictionary back into a pylast Track object.

        Args:
            track_dict: The dictionary representation of a track.

        Returns:
            A pylast Track object, or None if deserialization fails.
        """
        if not track_dict:
            return None
        try:
            track = pylast.Track(
                artist=track_dict['artist'],
                title=track_dict['title'],
                network=None  # 'network' will be set later in context
            )
            logger.debug(f"Deserialized track: {track}")
            return track
        except KeyError as e:
            logger.error(f"Failed to deserialize track dictionary: {track_dict}, error: {e}")
            return None

    def _serialize_artist(self, artist: pylast.Artist) -> Optional[Dict[str, Any]]:
        """Serializes a pylast Artist object into a JSON serializable dictionary.

        Args:
            artist: The pylast Artist object.

        Returns:
            A dictionary representing the serialized artist, or None if serialization fails.
        """
        try:
            serialized = {
                'name': artist.name,
                'url': artist.url
            }
            logger.debug(f"Serialized artist: {serialized}")
            return serialized
        except AttributeError as e:
            logger.error(f"Failed to serialize artist: {artist}, error: {e}")
            return None

    def _deserialize_artist(self, artist_dict: Dict[str, Any]) -> Optional[pylast.Artist]:
        """Deserializes a dictionary back into a pylast Artist object.

        Args:
            artist_dict: The dictionary representation of an artist.

        Returns:
            A pylast Artist object, or None if deserialization fails.
        """
        if not artist_dict:
            return None
        try:
            artist = pylast.Artist(
                name=artist_dict['name'],
                network=None  # 'network' will be set later in context
            )
            logger.debug(f"Deserialized artist: {artist}")
            return artist
        except KeyError as e:
            logger.error(f"Failed to deserialize artist dictionary: {artist_dict}, error: {e}")
            return None

class LastFM:
    """Client to interact with the LastFM API using pylast."""

    def __init__(self) -> None:
        """Initializes the LastFM client with environment variables."""
        self.network = None
        if API_KEY and API_SECRET and USERNAME and PASSWORD_HASH:
            self.network = pylast.LastFMNetwork(
                api_key=API_KEY, 
                api_secret=API_SECRET, 
                username=USERNAME, 
                password_hash=PASSWORD_HASH
            )
        self.cache = LastFMCache()

    def get_similar_tracks(self, artist_name: str, track_name: str) -> List[Dict[str, str]]:
        """Gets similar tracks from Last.fm based on a given track.

        Args:
            artist_name: The name of the artist.
            track_name: The name of the track.

        Returns:
            A list of dictionaries representing similar tracks.
        """
        cached_result = self.cache.get(artist_name, track_name)
        if cached_result:
            logger.debug(f"Cache hit for Artist: {artist_name}, Track: {track_name}")
            return cached_result

        try:
            track = self.network.get_track(artist_name, track_name)
            similar_tracks = track.get_similar()

            formatted_similar_tracks = []
            for similar_track in similar_tracks:
                if isinstance(similar_track.item, pylast.Track):
                    formatted_similar_tracks.append({
                        'artist': similar_track.item.artist.name,
                        'title': similar_track.item.title
                    })

            self.cache.set(artist_name, track_name, formatted_similar_tracks, [])
            return formatted_similar_tracks

        except pylast.WSError as e:
            if 'Track not found' in str(e):
                logger.debug(f"Failed to retrieve similar tracks for {artist_name} - {track_name}: {e}")
            else:
                logger.warning(f"Failed to retrieve similar tracks for {artist_name} - {track_name}: {e}")
            return []

        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return []

    def set_network(self, network: pylast.LastFMNetwork) -> None:
        """Sets the network context for cache deserialization.
        
        Args:
            network: The pylast LastFMNetwork instance to set.
        """
        self.cache.network = network
