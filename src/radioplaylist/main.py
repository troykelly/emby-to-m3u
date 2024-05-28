import os
import random
from tqdm import tqdm
import logging

logger = logging.getLogger(__name__)

class RadioPlaylistGenerator:
    def __init__(self, playlist_manager, lastfm_client, azuracast_sync):
        """Initializes the RadioPlaylistGenerator with PlaylistManager, LastFM client, and AzuraCast sync."""
        self.playlist_manager = playlist_manager
        self.lastfm = lastfm_client
        self.azuracast_sync = azuracast_sync
        self.playlists = self.load_playlists_from_env()  # Now will use updated manager
        self.general_rejects = self.load_general_rejects()
        self.specific_rejects = self.load_specific_rejects()

    def load_general_rejects(self):
        """Load general reject patterns from environment variables."""
        general_rejects = {
            'reject_playlist': [item.strip().lower() for item in os.getenv('RADIO_REJECT_PLAYLIST', "").split(',')],
            'reject_artist': [item.strip().lower() for item in os.getenv('RADIO_REJECT_ARTIST', "").split(',')]
        }
        return general_rejects

    def load_specific_rejects(self):
        """Load specific reject patterns for each playlist from environment variables."""
        specific_rejects = {}
        for key, value in os.environ.items():
            if key.startswith("RADIO_REJECT_PLAYLIST_"):
                playlist_name = self.convert_env_key_to_name(key)
                specific_rejects[f'{playlist_name}_playlist'] = [item.strip().lower() for item in value.split(',')]
            
            if key.startswith("RADIO_REJECT_ARTIST_"):
                playlist_name = self.convert_env_key_to_name(key)
                specific_rejects[f'{playlist_name}_artist'] = [item.strip().lower() for item in value.split(',')]
                
        return specific_rejects

    def load_playlists_from_env(self):
        """Load playlists and their corresponding genres from environment variables."""
        playlists = {}
        for key, value in os.environ.items():
            if key.startswith("RADIO_PLAYLIST_"):
                playlist_name = self.convert_env_key_to_name(key)
                genres = value.split(',')
                playlists[playlist_name] = genres
        return playlists

    @staticmethod
    def convert_env_key_to_name(key):
        """Convert environment variable key to a proper playlist name."""
        name_parts = key[len("RADIO_PLAYLIST_"):].split('_')
        return ' '.join(word.capitalize() for word in name_parts)

    def generate_playlist(self, genres, min_duration, playlist_name):
        """Generates a radio playlist based on input genres, minimum duration, and playlist name.

        Args:
            genres (list): List of genres to include in the playlist.
            min_duration (int): Minimum duration of the playlist in seconds.
            playlist_name (str): Name of the playlist.
            
        Returns:
            list: Generated playlist.
        """
        playlist = []
        playlist_duration = 0  # Keep track of the total playlist duration
        seen_tracks = set()

        # Initialize the progress bar
        with tqdm(total=min_duration, desc=f"Generating playlist '{playlist_name}'", unit="second") as pbar:
            # Make sure we don't end up in a failure loop
            failures = 0
            while playlist_duration < min_duration:
                if failures >= 20:
                    logger.error(f"Failed to generate playlist '{playlist_name}' after 10 attempts.")
                    break
                genre = random.choice(genres)
                seed_track = self._get_random_track_by_genre(genre)

                if not seed_track or seed_track['Id'] in seen_tracks:
                    failures += 1
                    continue

                if self._is_rejected(seed_track, playlist_name):
                    failures += 1
                    continue

                failures = 0
                playlist.append(seed_track)
                duration = seed_track['RunTimeTicks'] // 10000000  # Convert ticks to seconds
                playlist_duration += duration
                seen_tracks.add(seed_track['Id'])

                # Update the progress bar
                pbar.update(duration)
                
                similar_tracks = self._get_similar_tracks(seed_track)
                for similar_track in similar_tracks:
                    if playlist_duration >= min_duration:
                        break

                    if similar_track and similar_track.item:
                        track = self.playlist_manager.get_track_by_id(similar_track.item.title)
                        if track and track['Id'] not in seen_tracks and not self._is_rejected(track, playlist_name):
                            playlist.append(track)
                            duration = track['RunTimeTicks'] // 10000000  # Convert ticks to seconds
                            playlist_duration += duration
                            seen_tracks.add(track['Id'])

                            # Update the progress bar
                            pbar.update(duration)

        return playlist


    def _get_random_track_by_genre(self, genre):
        """Returns a random track from the playlist manager that matches the specified genre."""
        tracks_in_genre = self.playlist_manager.get_tracks_by_genre(genre)
        if not tracks_in_genre:
            return None
        return random.choice(tracks_in_genre)

    def _get_similar_tracks(self, track):
        """Retrieve similar tracks from LastFM."""
        artist = track.get('AlbumArtist')
        title = track.get('Name')
        if not artist or not title:
            return []

        return self.lastfm.get_similar_tracks(artist, title)[0]

    def _is_rejected(self, track, playlist_name):
        """Check if a track should be rejected based on general and specific reject rules."""
        track_title = track.get('Name', '').lower()
        album_title = track.get('Album', '').lower()
        artist_name = track.get('AlbumArtist', '').lower()

        # General rejections
        if any(reject in track_title for reject in self.general_rejects['reject_playlist']) or \
           any(reject in album_title for reject in self.general_rejects['reject_playlist']) or \
           any(reject in artist_name for reject in self.general_rejects['reject_artist']):
            return True

        # Specific playlist rejections
        specific_playlist_rejects = self.specific_rejects.get(f'{playlist_name}_playlist', [])
        specific_artist_rejects = self.specific_rejects.get(f'{playlist_name}_artist', [])

        if any(reject in track_title for reject in specific_playlist_rejects) or \
           any(reject in album_title for reject in specific_playlist_rejects) or \
           any(reject in artist_name for reject in specific_artist_rejects):
            return True

        return False
