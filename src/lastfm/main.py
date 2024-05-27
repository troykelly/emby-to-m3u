import os
import pylast
import logging
import json
import hashlib

logger = logging.getLogger(__name__)

# Set the logging level for pylast and httpx to WARN
logging.getLogger('pylast').setLevel(logging.WARN)
logging.getLogger('httpx').setLevel(logging.WARN)

API_KEY = os.getenv('LAST_FM_API_KEY')
API_SECRET = os.getenv('LAST_FM_API_SECRET')
username = os.getenv('LAST_FM_USERNAME', '')
password_hash = pylast.md5(os.getenv('LAST_FM_PASSWORD', ''))

class LastFMCache:
    """Simple cache to store LastFM responses to minimize API traffic."""

    def __init__(self, cache_file='lastfm_cache.json'):
        self.cache_file = cache_file
        self.cache_data = self.load_cache()

    def load_cache(self):
        """Load the cache from a file."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as file:
                    return json.load(file)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode cache file: {e}")
        return {}

    def save_cache(self):
        """Save the cache to a file."""
        try:
            with open(self.cache_file, 'w') as file:
                json.dump(self.cache_data, file)
        except Exception as e:
            logger.error(f"Failed to save cache file: {e}")

    def get_cache_key(self, artist_name, track_name):
        """Generate a unique cache key for the given artist and track."""
        key = f"{artist_name}-{track_name}"
        return hashlib.md5(key.encode('utf-8')).hexdigest()

    def get(self, artist_name, track_name):
        """Retrieve cached data for a given artist and track."""
        key = self.get_cache_key(artist_name, track_name)
        cached_result = self.cache_data.get(key)
        if cached_result:
            similar_tracks = [self._deserialize_track(t) for t in cached_result['similar_tracks']]
            similar_artists = [self._deserialize_artist(a) for a in cached_result['similar_artists']]
            return similar_tracks, similar_artists
        return None

    def set(self, artist_name, track_name, similar_tracks, similar_artists):
        """Cache similar tracks and artists for a given artist and track."""
        key = self.get_cache_key(artist_name, track_name)
        self.cache_data[key] = {
            'similar_tracks': [self._serialize_track(t) for t in similar_tracks],
            'similar_artists': [self._serialize_artist(a) for a in similar_artists]
        }
        self.save_cache()

    def _serialize_track(self, track):
        """Serialize a pylast Track object into a JSON serializable dict."""
        try:
            return {
                'title': track.title,
                'artist': track.artist.name,
                'url': track.url
            }
        except AttributeError:
            return None

    def _deserialize_track(self, track_dict):
        """Deserialize a dict back into a pylast Track object."""
        if not track_dict:
            return None
        return pylast.Track(
            artist=track_dict['artist'],
            title=track_dict['title'],
            network=None  # 'network' will be set later in context
        )

    def _serialize_artist(self, artist):
        """Serialize a pylast Artist object into a JSON serializable dict."""
        try:
            return {
                'name': artist.name,
                'url': artist.url
            }
        except AttributeError:
            return None

    def _deserialize_artist(self, artist_dict):
        """Deserialize a dict back into a pylast Artist object."""
        if not artist_dict:
            return None
        return pylast.Artist(
            name=artist_dict['name'],
            network=None  # 'network' will be set later in context
        )

class LastFM:
    def __init__(self):
        """Initializes the LastFM client with environment variables."""
        self.network = None
        if API_KEY and API_SECRET and username and password_hash:
            self.network = pylast.LastFMNetwork(api_key=API_KEY, api_secret=API_SECRET, username=username, password_hash=password_hash)
        
        self.cache = LastFMCache()

    def get_similar_tracks(self, artist_name, track_name):
        """Get similar tracks from Last.fm based on a given track."""
        cached_result = self.cache.get(artist_name, track_name)
        if cached_result:
            logger.debug(f"Cache hit for Artist: {artist_name}, Track: {track_name}")
            return cached_result
        
        try:
            artist = self.network.get_artist(artist_name)
            track = self.network.get_track(artist_name, track_name)

            similar_tracks = track.get_similar()
            similar_artists = artist.get_similar()

            self.cache.set(artist_name, track_name, similar_tracks, similar_artists)
            return similar_tracks, similar_artists

        except pylast.WSError as e:
            # If error is "Track not found" output debug, otherwise output a warning
            if 'Track not found' in str(e):
                logger.debug(f"Failed to retrieve similar tracks for {artist_name} - {track_name}: {e}")
            else:
                logger.warn(f"Failed to retrieve similar tracks for {artist_name} - {track_name}: {e}")
            return [], []
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return [], []
    
    def set_network(self, network):
        """Set the network context for cache deserialization."""
        self.cache.network = network


# Example usage:
# similar_tracks, similar_artists = get_similar_tracks('Radiohead', 'Creep')