import random

class RadioPlaylistGenerator:
    def __init__(self, emby_tracks, lastfm_client, azuracast_sync):
        """Initializes the RadioPlaylistGenerator with given Emby tracks and LastFM client."""
        self.emby_tracks = [track for track in emby_tracks if track.get('Genres')]  # Filter tracks with genres
        self.lastfm = lastfm_client
        self.azuracast_sync = azuracast_sync
        self.track_map = {track['Name']: track for track in self.emby_tracks}

    def generate_playlist(self, genres, min_duration):
        """Generates a radio playlist based on input genres and requested minimum duration."""
        playlist = []
        playlist_duration = 0  # Keep track of the total playlist duration
        seen_tracks = set()

        while playlist_duration < min_duration:
            genre = random.choice(genres)
            seed_track = self._get_random_track_by_genre(genre)

            if not seed_track or seed_track['Id'] in seen_tracks:
                continue

            playlist.append(seed_track)
            playlist_duration += seed_track['RunTimeTicks'] // 10000000  # Convert ticks to seconds
            seen_tracks.add(seed_track['Id'])

            similar_tracks = self._get_similar_tracks(seed_track)
            for similar_track in similar_tracks:
                if playlist_duration >= min_duration:
                    break

                track = self.track_map.get(similar_track.title)
                if track and track['Id'] not in seen_tracks:
                    playlist.append(track)
                    playlist_duration += track['RunTimeTicks'] // 10000000  # Convert ticks to seconds
                    seen_tracks.add(track['Id'])

        return playlist

    def _get_random_track_by_genre(self, genre):
        """Returns a random track from the emby_tracks list that matches the specified genre."""
        tracks_in_genre = [track for track in self.emby_tracks if genre in track.get('Genres', [])]
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