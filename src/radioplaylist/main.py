
import logging
import os
import random
from typing import Dict, List, Optional, Set, TYPE_CHECKING

from tqdm import tqdm

if TYPE_CHECKING:
    from playlist.main import PlaylistManager
    from lastfm.main import LastFM
    from azuracast.main import AzuraCastSync

logger = logging.getLogger(__name__)

class RadioPlaylistGenerator:
    def __init__(self, playlist_manager: 'PlaylistManager', lastfm_client: 'LastFM', azuracast_sync: 'AzuraCastSync') -> None:
        """
        Initializes the RadioPlaylistGenerator with PlaylistManager, LastFM client, and AzuraCast sync.

        Args:
            playlist_manager: An instance of PlaylistManager
            lastfm_client: An instance of LastFM
            azuracast_sync: An instance of AzuraCastSync
        """
        self.playlist_manager = playlist_manager
        self.lastfm = lastfm_client
        self.azuracast_sync = azuracast_sync
        self.playlists: Dict[str, List[str]] = self.load_playlists_from_env()
        self.general_rejects: Dict[str, List[str]] = self.load_general_rejects()
        self.specific_rejects: Dict[str, List[str]] = self.load_specific_rejects()

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
        """Convert environment variable key to a proper playlist name.

        Args:
            key: Environment variable key to convert.

        Returns:
            Converted playlist name.
        """
        name_parts = key[len("RADIO_PLAYLIST_"):].split('_')
        return ' '.join(word.capitalize() for word in name_parts)

    def _get_random_track_by_genre(self, genre: str) -> Optional[Dict[str, str]]:
        """Return a random track from the playlist manager that matches the specified genre.

        Args:
            genre: Genre to filter tracks.

        Returns:
            A random track dictionary or None if no tracks are found.
        """
        tracks_in_genre = self.playlist_manager.get_tracks_by_genre(genre)
        if not tracks_in_genre:
            return None
        return random.choice(tracks_in_genre)

    def _get_similar_tracks(self, track: Dict[str, str]) -> List[Dict[str, str]]:
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

    def _is_rejected(self, track: Dict[str, str], playlist_name: str) -> bool:
        """Check if a track should be rejected based on general and specific reject rules.

        Args:
            track: The track information dictionary.
            playlist_name: The name of the playlist.

        Returns:
            True if the track is rejected, False otherwise.
        """
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
            genres: List of genres with possible year/decade filters.

        Returns:
            List of genres with filters removed.
        """
        new_genres = []
        for genre in genres:
            parts = genre.split()
            if len(parts) > 1 and parts[-1].isdigit():
                new_genres.append(' '.join(parts[:-1]))
            else:
                new_genres.append(genre)
        return list(set(new_genres))

    def generate_playlist(self, genres: List[str], min_duration: int, playlist_name: str) -> List[Dict[str, str]]:
        """Generate a radio playlist based on input genres, minimum duration, and playlist name.

        Args:
            genres: List of genres to include in the playlist.
            min_duration: Minimum duration of the playlist in seconds.
            playlist_name: Name of the playlist.

        Returns:
            Generated playlist.
        """
        def track_already_added(track_id: str) -> bool:
            """Check if the track is already added to the playlist.

            Args:
                track_id: Track ID to check.

            Returns:
                True if track is already in playlist, False otherwise.
            """
            return track_id in {track['Id'] for track in playlist}
        
        def is_track_rejected(track: Dict[str, str]) -> bool:
            """Check if the track is rejected.

            Args:
                track: Track information dictionary.

            Returns:
                True if the track is rejected, False otherwise.
            """
            return self._is_rejected(track, playlist_name)
        
        def select_random_genre(genres: List[str], ignored_genres: Set[str]) -> Optional[str]:
            """Select a random genre from the list of genres excluding ignored genres.

            Args:
                genres: List of genres to select from.
                ignored_genres: Set of genres to ignore.

            Returns:
                A random genre or None if no genres are available.
            """
            available_genres = [genre for genre in genres if genre not in ignored_genres]
            return random.choice(available_genres) if available_genres else None

        def add_track_to_playlist(track: Dict[str, str], playlist: List[Dict[str, str]]) -> None:
            """Add a track to the playlist and update duration.

            Args:
                track: Track to add.
                playlist: Playlist to add track to.
            """
            playlist.append(track)
            seen_tracks.add(track['Id'])
            update_playlist_duration(track['RunTimeTicks'] // 10000000)  # Convert ticks to seconds

        def update_playlist_duration(duration: int) -> None:
            """Update the total playlist duration.

            Args:
                duration: Duration to add in seconds.
            """
            nonlocal playlist_duration
            playlist_duration += duration
        
        def refresh_genres(genres: List[str]) -> List[str]:
            """Refresh the list of genres removing year/decade filters.

            Args:
                genres: List of genres.

            Returns:
                Refreshed list of genres.
            """
            return self._remove_year_decade_filters(genres)

        playlist = []
        playlist_duration = 0
        seen_tracks: Set[str] = set()
        ignored_genres: Set[str] = set()
        retry_limit = 20
        retry_count = 0
        
        # Add event to report
        self.playlist_manager.report.add_event(
            playlist_name,
            'START_GENERATION',
            f"Starting playlist generation with: {genres}",
            '',
            '',
            '',
            '',
            '',
            '',
        )
        self.playlist_manager.report.add_event(
            playlist_name,
            'TARGET_LENGTH',
            f"Target lenght is {min_duration} seconds",
            '',
            '',
            '',
            '',
            '',
            '',
        )

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
            
            # Add event to report
            self.playlist_manager.report.add_event(
                playlist_name,
                'GENRE_SELECTED',
                '',
                '',
                '',
                genre,
                '',
                '',
                '',
            )

            initial_track = self._get_random_track_by_genre(genre)
            if not initial_track:
                ignored_genres.add(genre)
                # Add event to report
                self.playlist_manager.report.add_event(
                    playlist_name,
                    'NO_INITIAL_TRACK',
                    '',
                    '',
                    '',
                    genre,
                    '',
                    '',
                    '',
                )                
                retry_count += 1
                continue
            
            if track_already_added(initial_track['Id']):
                ignored_genres.add(genre)
                # Add event to report
                self.playlist_manager.report.add_event(
                    playlist_name,
                    'TRACK_ALREADY_ADDED',
                    '',
                    initial_track.get('AlbumArtist', ''),
                    initial_track.get('Name', ''),
                    genre,
                    '',
                    '',
                    '',
                )                
                retry_count += 1
                continue
            
            if is_track_rejected(initial_track):
                ignored_genres.add(genre)
                # Add event to report
                self.playlist_manager.report.add_event(
                    playlist_name,
                    'TRACK_REJECTED',
                    '',
                    initial_track.get('AlbumArtist', ''),
                    initial_track.get('Name', ''),
                    genre,
                    '',
                    '',
                    '',
                )                
                retry_count += 1
                continue

            retry_count = 0  # Reset retry count on successful track addition
            add_track_to_playlist(initial_track, playlist)
            # Add event to report
            self.playlist_manager.report.add_event(
                playlist_name,
                'TRACK_ADDED',
                '',
                initial_track.get('AlbumArtist', ''),
                initial_track.get('Name', ''),
                genre,
                '',
                '',
                '',
            )            

            candidate_tracks = self._get_similar_tracks(initial_track)
            self.playlist_manager.report.add_event(
                playlist_name,
                'SIMILAR_TRACKS_FETCHED',
                f"Found {len(candidate_tracks)} similar tracks",
                initial_track.get('AlbumArtist', ''),
                initial_track.get('Name', ''),
                genre,
                '',
                '',
                '',
            )                        
            for candidate in candidate_tracks:
                if random.random() < 0.3:
                    break

                similar_track = self.playlist_manager.get_track_by_title_and_artist(
                    candidate['title'], candidate['artist']
                )
                if similar_track and not track_already_added(similar_track['Id']) and not is_track_rejected(similar_track):
                    self.playlist_manager.report.add_event(
                        playlist_name,
                        'SIMILAR_TRACK_ADDED',
                        '',
                        similar_track.get('AlbumArtist', ''),
                        similar_track.get('Name', ''),
                        genre,
                        '',
                        '',
                        '',
                    )                    
                    add_track_to_playlist(similar_track, playlist)

            if not candidate_tracks:
                self.playlist_manager.report.add_event(
                    playlist_name,
                    'GENRES_EXHAUSTED',
                    '',
                    '',
                    '',
                    '',
                    '',
                    '',
                    '',
                )                
                genres = refresh_genres(genres)

        return playlist

if __name__ == "__main__":
    pass  # This is here to denote where any module-level code could be added, if necessary.
