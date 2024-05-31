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
        """Retrieve similar tracks using the LastFM client.

        Args:
            track: The track information dictionary.

        Returns:
            A list of dictionaries containing similar track information.
        """
        artist: Optional[str] = track.get('AlbumArtist')
        title: Optional[str] = track.get('Name')
        if not artist or not title:
            return []

        similar_tracks: List[Dict[str, str]] = self.lastfm.get_similar_tracks(artist, title)
        
        # Validate the format of the returned similar tracks
        if not isinstance(similar_tracks, list) or not all(isinstance(t, dict) for t in similar_tracks):
            logger.warning(f"Unexpected format for similar tracks for {artist} - {title}")
            logger.warning(similar_tracks)
            return []
        
        return similar_tracks

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
            genres: List of genres to include in the playlist.
            min_duration: Minimum duration of the playlist in seconds.
            playlist_name: Name of the playlist.

        Returns:
            Generated playlist.
        """
        def track_already_added(track_id: str) -> bool:
            return track_id in [track['Id'] for track in playlist]
        
        def is_track_rejected(track: Dict[str, Any]) -> bool:
            return self._is_rejected(track, playlist_name)
        
        def select_random_genre(genres: List[str], ignored_genres: set) -> Optional[str]:
            available_genres = [genre for genre in genres if genre not in ignored_genres]
            return random.choice(available_genres) if available_genres else None

        def add_track_to_playlist(track: Dict[str, Any], playlist: List[Dict[str, Any]]) -> None:
            playlist.append(track)
            seen_tracks.add(track['Id'])
            update_playlist_duration(track['RunTimeTicks'] // 10000000)  # Convert ticks to seconds

        def update_playlist_duration(duration: int) -> None:
            nonlocal playlist_duration
            playlist_duration += duration
        
        def refresh_genres(genres: List[str]) -> List[str]:
            return self._remove_year_decade_filters(genres)

        playlist = []
        playlist_duration = 0
        seen_tracks = set()
        ignored_genres = set()
        retry_limit = 20
        retry_count = 0

        while playlist_duration < min_duration:
            if retry_count >= retry_limit:
                break

            genre = select_random_genre(genres, ignored_genres)
            if not genre:
                genres = refresh_genres(genres)
                if not genres:
                    logger.warning(f"Cannot generate full playlist '{playlist_name}': insufficient tracks.")
                    break
                ignored_genres.clear()
                continue

            initial_track = self._get_random_track_by_genre(genre)
            if not initial_track or track_already_added(initial_track['Id']) or is_track_rejected(initial_track):
                ignored_genres.add(genre)
                retry_count += 1
                continue

            retry_count = 0  # Reset retry count on successful track addition
            add_track_to_playlist(initial_track, playlist)

            candidate_tracks = self._get_similar_tracks(initial_track)
            for candidate in candidate_tracks:
                if random.random() < 0.3:
                    break

                similar_track = self.playlist_manager.get_track_by_title_and_artist(candidate['title'], candidate['artist'])
                if similar_track and not track_already_added(similar_track['Id']) and not is_track_rejected(similar_track):
                    add_track_to_playlist(similar_track, playlist)

                if not candidate_tracks:
                    genres = refresh_genres(genres)

        return playlist