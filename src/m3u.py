#!/usr/bin/env python3
"""
Script to generate m3u playlists from Emby API based on music genres, artists, and albums.

This script connects to the Emby API, retrieves all music tracks,
and generates m3u playlist files for each genre, artist, and album.

Environment Variables:
- EMBY_API_KEY: The API key to authenticate with Emby.
- EMBY_SERVER_URL: The base URL of the Emby server. E.g., http://localhost:8096
- M3U_DESTINATION: The directory where m3u files will be created.

Author: [Your Name]
Date: [Date]

Usage:
Make sure to set the environment variables before running the script:
$ export EMBY_API_KEY='YOUR_API_KEY'
$ export EMBY_SERVER_URL='http://YOUR_EMBY_SERVER'
$ export M3U_DESTINATION='/path/to/m3u/destination'

Then run the script:
$ python3 generate_m3u_playlists.py
"""

import os
import re
import requests
import tempfile
import shutil
import json
from tqdm import tqdm
from collections import defaultdict, Counter


def get_emby_data(endpoint):
    """Retrieve data from given Emby API endpoint.

    Args:
        endpoint (str): The specific API endpoint to fetch data from.

    Returns:
        dict: The data retrieved from the Emby API.
    """
    emby_server_url = os.getenv('EMBY_SERVER_URL')
    emby_api_key = os.getenv('EMBY_API_KEY')
    url = f'{emby_server_url}{endpoint}&api_key={emby_api_key}'
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def extract_external_ids(track):
    """Extract external IDs from a track object.

    Args:
        track (dict): The track object.

    Returns:
        dict: A dictionary of external IDs.
    """
    provider_ids = track.get('ProviderIds', {})
    external_ids = {
        'MusicBrainzTrackId': provider_ids.get('MusicBrainzTrack', ''),
        'MusicBrainzAlbumId': provider_ids.get('MusicBrainzAlbum', ''),
        'MusicBrainzArtistId': provider_ids.get('MusicBrainzArtist', ''),
        'MusicBrainzReleaseGroupId': provider_ids.get('MusicBrainzReleaseGroup', ''),
        'TheAudioDbAlbumId': provider_ids.get('TheAudioDbAlbumId', ''),
        'TheAudioDbArtistId': provider_ids.get('TheAudioDbArtistId', '')
    }
    return external_ids

def write_m3u_playlist(filename, tracks, genre=None, artist=None, album=None):
    """Write m3u playlist file.

    Args:
        filename (str): The full path to the m3u file to be created.
        tracks (list): List of dictionaries with track details to include in the m3u file.
        genre (str, optional): Genre to include in the extended attributes.
        artist (str, optional): Artist to include in the extended attributes.
        album (str, optional): Album to include in the extended attributes.
    """
    temp_file = tempfile.NamedTemporaryFile('w', delete=False)
    try:
        with temp_file as f:
            f.write('#EXTM3U\n')
            f.write('#EXTENC:UTF-8\n')
            if genre:
                f.write(f'#EXTGENRE:{genre}\n')
            if artist:
                f.write(f'#EXTART:{artist}\n')
            if album:
                f.write(f'#EXTALB:{album}\n')
            
            for track in tracks:
                duration = track.get('RunTimeTicks', 0) // 10000000  # Convert ticks to seconds
                title = track.get('Name', 'Unknown Title')
                path = track.get('Path', '')
                album = track.get('Album', '')
                album_artist = track.get('AlbumArtist', '')
                genre_name = track.get('Genres', [''])[0]

                # Extract external IDs during playlist writing
                external_ids = extract_external_ids(track)
                mb_track_id = external_ids['MusicBrainzTrackId']
                mb_album_id = external_ids['MusicBrainzAlbumId']
                mb_artist_id = external_ids['MusicBrainzArtistId']
                mb_release_group_id = external_ids['MusicBrainzReleaseGroupId']
                the_audio_db_album_id = external_ids['TheAudioDbAlbumId']
                the_audio_db_artist_id = external_ids['TheAudioDbArtistId']

                # Write extended information
                f.write(f'#EXTINF:{duration}, {title}\n')
                if album:
                    f.write(f'#EXTALB:{album}\n')
                if album_artist:
                    f.write(f'#EXTART:{album_artist}\n')
                if genre_name:
                    f.write(f'#EXTGENRE:{genre_name}\n')
                if mb_track_id:
                    f.write(f'#EXT-X-MUSICBRAINZ-TRACKID:{mb_track_id}\n')
                if mb_album_id:
                    f.write(f'#EXT-X-MUSICBRAINZ-ALBUMID:{mb_album_id}\n')
                if mb_artist_id:
                    f.write(f'#EXT-X-MUSICBRAINZ-ARTISTID:{mb_artist_id}\n')
                if mb_release_group_id:
                    f.write(f'#EXT-X-MUSICBRAINZ-RELEASEGROUPID:{mb_release_group_id}\n')
                if the_audio_db_album_id:
                    f.write(f'#EXT-X-THEAUDIODB-ALBUMID:{the_audio_db_album_id}\n')
                if the_audio_db_artist_id:
                    f.write(f'#EXT-X-THEAUDIODB-ARTISTID:{the_audio_db_artist_id}\n')
                f.write(f'{path}\n')
        
        shutil.move(temp_file.name, filename)
    except Exception as e:
        os.remove(temp_file.name)
        raise e

def normalize_filename(name):
    """Normalize filename by removing invalid characters.

    Args:
        name (str): The original name.

    Returns:
        str: A filesystem-safe version of the name.
    """
    name = re.sub(r'[\\/:"*?<>|]+', '', name)  # Remove invalid characters
    name = re.sub(r'\s+', '_', name)  # Replace spaces with underscores
    return name

def generate_playlists():
    """Main function to generate m3u playlists for genres, artists, and albums."""
    destination = os.getenv('M3U_DESTINATION')
    if not destination:
        raise ValueError("Environment variable M3U_DESTINATION is not set.")
    
    # Ensure base destination directory exists
    os.makedirs(destination, exist_ok=True)
    
    # Ensure subdirectories exist
    genre_dir = os.path.join(destination, '_genre')
    artist_dir = os.path.join(destination, '_artist')
    album_dir = os.path.join(destination, '_album')
    os.makedirs(genre_dir, exist_ok=True)
    os.makedirs(artist_dir, exist_ok=True)
    os.makedirs(album_dir, exist_ok=True)

    # Get all audio items with basic metadata
    all_audio_items = get_emby_data(
        '/Items?Recursive=true&IncludeItemTypes=Audio&Fields='
        'Path,RunTimeTicks,Name,Album,AlbumArtist,Genres,IndexNumber,ProductionYear,ExternalIds,MusicBrainzAlbumId,MusicBrainzArtistId,MusicBrainzReleaseGroupId,ParentIndexNumber,ProviderIds,TheAudioDbAlbumId,TheAudioDbArtistId&SortBy=SortName&SortOrder=Ascending'
    )
    
    genres = defaultdict(list)
    artists = defaultdict(list)
    albums = defaultdict(list)
    artist_counter = Counter()
    album_counter = Counter()

    for track in tqdm(all_audio_items['Items'], desc="Processing tracks"):
        
        # Pretty print the track for debugging
        print(json.dumps(track, indent=2))
        
        track_genres = track.get('Genres', [])
        if not track_genres:
            continue  # Skip tracks with no genre information
        
        # Add track to genre playlists
        for genre in track_genres:
            genres[genre].append(track)

        # Add track to artist playlists, use artist ID or album artist as a fallback
        artist_id = track.get('MusicBrainzArtistId', track.get('AlbumArtist'))
        artist_name = track.get('AlbumArtist', 'Unknown Artist')
        production_year = track.get('ProductionYear', '')
        if artist_id:
            artist_key = (artist_id, artist_name, production_year)
            artists[artist_key].append(track)
            artist_counter[artist_name] += 1

        # Add track to album playlists, use album ID or album name as a fallback
        album_id = track.get('MusicBrainzAlbumId', track.get('Album'))
        album_name = track.get('Album', 'Unknown Album')
        if album_id:
            album_key = (album_id, album_name, production_year)
            albums[album_key].append(track)
            album_counter[album_name] += 1

    # Disambiguate artist names
    disambiguated_artists = {}
    for (artist_id, artist_name, production_year), tracks in artists.items():
        if artist_counter[artist_name] > 1:
            disambiguated_artist = f"{artist_name} ({production_year})" if production_year else artist_name
        else:
            disambiguated_artist = artist_name
        disambiguated_artists.setdefault(disambiguated_artist, []).extend(tracks)

    # Disambiguate album names
    disambiguated_albums = {}
    for (album_id, album_name, production_year), tracks in albums.items():
        if album_counter[album_name] > 1:
            disambiguated_album = f"{album_name} ({production_year})" if production_year else album_name
        else:
            disambiguated_album = album_name
        disambiguated_albums.setdefault(disambiguated_album, []).extend(tracks)

    # Write genre playlists
    for genre, tracks in tqdm(genres.items(), desc="Writing genre playlists"):
        genre_filename = os.path.join(genre_dir, f'{normalize_filename(genre)}.m3u')
        write_m3u_playlist(genre_filename, tracks, genre=genre)

    # Write artist playlists
    for disambiguated_artist, tracks in tqdm(disambiguated_artists.items(), desc="Writing artist playlists"):
        artist_filename = os.path.join(artist_dir, f'{normalize_filename(disambiguated_artist)}.m3u')
        write_m3u_playlist(artist_filename, tracks, artist=disambiguated_artist)

    # Write album playlists
    for disambiguated_album, tracks in tqdm(disambiguated_albums.items(), desc="Writing album playlists"):
        if tracks:
            # Sort tracks by their index number or track number
            tracks.sort(key=lambda x: x.get('IndexNumber', 0))
            album_filename = os.path.join(album_dir, f'{normalize_filename(disambiguated_album)}.m3u')
            write_m3u_playlist(album_filename, tracks, album=disambiguated_album)

if __name__ == "__main__":
    generate_playlists()