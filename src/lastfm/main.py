import os
import pylast
import logging
import json
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
            with open(self.cache_file, 'r') as file:
                return json.load(file)
        return {}

    def save_cache(self):
        """Save the cache to a file."""
        with open(self.cache_file, 'w') as file:
            json.dump(self.cache_data, file)

    def get_cache_key(self, artist_name, track_name):
        """Generate a unique cache key for the given artist and track."""
        key = f"{artist_name}-{track_name}"
        return hashlib.md5(key.encode('utf-8')).hexdigest()

    def get(self, artist_name, track_name):
        """Retrieve cached data for a given artist and track."""
        key = self.get_cache_key(artist_name, track_name)
        return self.cache_data.get(key)

    def set(self, artist_name, track_name, similar_tracks, similar_artists):
        """Cache similar tracks and artists for a given artist and track."""
        key = self.get_cache_key(artist_name, track_name)
        self.cache_data[key] = {
            'similar_tracks': similar_tracks,
            'similar_artists': similar_artists
        }
        self.save_cache()

class LastFM:
    def __init__(self):
        """Initializes the LastFM client with environment variables."""
        if API_KEY and API_SECRET and username and password_hash:
            self.network = pylast.LastFMNetwork(api_key=API_KEY, api_secret=API_SECRET, username=username, password_hash=password_hash)
        else:
            self.network = None
        self.cache = LastFMCache()

    def get_similar_tracks(self, artist_name, track_name):
        """Get similar tracks from Last.fm based on a given track."""
        cached_result = self.cache.get(artist_name, track_name)
        if cached_result:
            logger.info(f"Cache hit for Artist: {artist_name}, Track: {track_name}")
            return cached_result['similar_tracks'], cached_result['similar_artists']
        
        try:
            artist = self.network.get_artist(artist_name)
            track = self.network.get_track(artist_name, track_name)

            similar_tracks = track.get_similar()
            similar_artists = artist.get_similar()

            self.cache.set(artist_name, track_name, similar_tracks, similar_artists)
            return similar_tracks, similar_artists

        except pylast.WSError as e:
            logger.error(f"Failed to retrieve similar tracks for {artist_name} - {track_name}: {e}")
            return [], []
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return [], []

# Example usage:
# similar_tracks, similar_artists = get_similar_tracks('Radiohead', 'Creep')