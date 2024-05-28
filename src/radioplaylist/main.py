import random
import os
from tqdm import tqdm
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class RadioPlaylistGenerator:
    def __init__(self, playlist_manager: Any, lastfm_client: Any, azuracast_sync: Any) -> None:
        """Initializes the RadioPlaylistGenerator with PlaylistManager, LastFM client, and AzuraCast sync."""
        self.playlist_manager = playlist_manager
        self.lastfm = lastfm_client
        self.azuracast_sync = azuracast_sync
        self.playlists = self.load_playlists_from_env()
        self.general_rejects = self.load_general_rejects()
        self.specific_rejects = self.load_specific_rejects()

    def load_playlists_from_env(self) -> Dict[str, List[str]]:
        """Load playlists and their corresponding genres from environment variables."""
        playlists = {}
        for key, value in os.environ.items():
            if key.startswith("RADIO_PLAYLIST_"):
                playlist_name = self.convert_env_key_to_name(key)
                genres = value.split(',')
                playlists[playlist_name] = genres
        return playlists

    def load_general_rejects(self) -> Dict[str, List[str]]:
        """Load general reject patterns from environment variables."""
        return {
            'reject_playlist': [item.strip().lower() for item in os.getenv('RADIO_REJECT_PLAYLIST', "").split(',')],
            'reject_artist': [item.strip().lower() for item in os.getenv('RADIO_REJECT_ARTIST', "").split(',')]
        }

    def load_specific_rejects(self) -> Dict[str, List[str]]:
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

    @staticmethod
    def convert_env_key_to_name(key: str) -> str:
        """Convert environment variable key to a proper playlist name."""
        name_parts = key[len("RADIO_PLAYLIST_"):].split('_')
        return ' '.join(word.capitalize() for word in name_parts)

    def _get_random_track_by_genre(self, genre: str) -> Optional[Dict[str, Any]]:
        """Returns a random track from the playlist manager that matches the specified genre."""
        tracks_in_genre = self.playlist_manager.get_tracks_by_genre(genre)
        if not tracks_in_genre:
            return None
        return random.choice(tracks_in_genre)

    def _get_similar_tracks(self, track: Dict[str, Any]) -> List[Dict[str, str]]:
        """Retrieve similar tracks from LastFM."""
        artist = track.get('AlbumArtist')
        title = track.get('Name')
        if not artist or not title:
            return []
        return self.lastfm.get_similar_tracks(artist, title)[0]

    def _is_rejected(self, track: Dict[str, Any], playlist_name: str) -> bool:
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

    def _remove_year_decade_filters(self, genres: List[str]) -> List[str]:
        """Remove year or decade filters from genre names.
        
        Args:
            genres (list): List of genres with possible year/decade filters.

        Returns:
            list: List of genres with filters removed.
        """
        new_genres = []
        for genre in genres:
            parts = genre.split()
            if len(parts) > 1 and parts[-1].isdigit():
                new_genres.append(' '.join(parts[:-1]))
            else:
                new_genres.append(genre)
        return list(set(new_genres))

    def generate_playlist(self, genres: List[str], min_duration: int, playlist_name: str) -> List[Dict[str, Any]]:
        """Generates a radio playlist based on input genres, minimum duration, and playlist name.

        Args:
            genres (list): List of genres to include in the playlist.
            min_duration (int): Minimum duration of the playlist in seconds.
            playlist_name (str): Name of the playlist.
            
        Returns:
            list: Generated playlist.
        """
        playlist = []
        playlist_duration = 0
        seen_tracks = set()
        genre_rejects = set()

        with tqdm(total=min_duration, desc=f"Generating playlist '{playlist_name}'", unit="second") as pbar:
            while playlist_duration < min_duration:
                if len(genres) == len(genre_rejects):
                    genres = self._remove_year_decade_filters(genres)
                    genre_rejects.clear()
                    if not genres:
                        logger.warning(f"Could not generate full playlist '{playlist_name}'. Insufficient tracks.")
                        break

                genre = random.choice([g for g in genres if g not in genre_rejects])
                seed_track = self._get_random_track_by_genre(genre)

                if not seed_track or seed_track['Id'] in seen_tracks:
                    genre_rejects.add(genre)
                    continue

                if self._is_rejected(seed_track, playlist_name):
                    genre_rejects.add(genre)
                    continue

                playlist.append(seed_track)
                duration = seed_track['RunTimeTicks'] // 10000000  # Convert ticks to seconds
                playlist_duration += duration
                seen_tracks.add(seed_track['Id'])
                pbar.update(duration)

                similar_tracks = self._get_similar_tracks(seed_track)
                for similar_track in similar_tracks:
                    if playlist_duration >= min_duration:
                        break
                    track_artist = similar_track.get('artist')
                    track_title = similar_track.get('title')
                    track = self.playlist_manager.get_track_by_title_and_artist(track_title, track_artist)
                    if track and track['Id'] not in seen_tracks and not self._is_rejected(track, playlist_name):
                        playlist.append(track)
                        duration = track['RunTimeTicks'] // 10000000  # Convert ticks to seconds
                        playlist_duration += duration
                        seen_tracks.add(track['Id'])
                        pbar.update(duration)

                    if random.random() < 0.3:
                        break

        return playlist