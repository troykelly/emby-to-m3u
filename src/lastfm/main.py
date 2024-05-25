import os
import pylast
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = os.getenv('LAST_FM_API_KEY')
API_SECRET = os.getenv('LAST_FM_API_SECRET')
username = os.getenv('LAST_FM_USERNAME', '')
password_hash = pylast.md5(os.getenv('LAST_FM_PASSWORD', ''))

class LastFM:
    def __init__(self):
        """Initializes the LastFM client with environment variables."""
        # Initialize the LastFM network with the API key, API secret, username, and password hash if they exist, ignore otherwise
        if API_KEY and API_SECRET and username and password_hash:
            self.network = pylast.LastFMNetwork(api_key=API_KEY, api_secret=API_SECRET, username=username, password_hash=password_hash)
        else:
            self.network = None

    def get_similar_tracks(self, artist_name, track_name):
        """Get similar tracks from Last.fm based on a given track."""
        try:
            artist = self.network.get_artist(artist_name)
            track = self.network.get_track(artist_name, track_name)
        
            similar_tracks = track.get_similar()
            similar_artists = artist.get_similar()

            return similar_tracks, similar_artists  # Return both similar tracks and artists

        except pylast.WSError as e:
            logger.error(f"Failed to retrieve similar tracks for {artist_name} - {track_name}: {e}")
            return [], []

# Example usage:
# similar_tracks, similar_artists = get_similar_tracks('Radiohead', 'Creep')