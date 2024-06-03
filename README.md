# Emby to M3U Playlist Generator

![GitHub license](https://img.shields.io/badge/license-Apache%202.0-blue.svg)
![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/troykelly/emby-to-m3u/build-and-publish.yml)

## Overview

The Emby to M3U Playlist Generator is a Python tool that connects to the Emby API, retrieves all music tracks, and generates M3U playlist files for each genre, artist, and album. The script can then generate AzuraCast playlists if desired based on genre matching rules.

## Features

- Generates M3U playlists for:
  - Genres
  - Artists
  - Albums
  - Years
  - Decades
  - Customised radio playlists using Last.fm and AzuraCast sync
- Fetches metadata from Emby, including external IDs.
- Supports customisation through environment variables.
- Dockerised for straightforward deployment.
- CI/CD pipeline for automated Docker image building and publishing.
- Generates comprehensive Markdown and PDF reports for playlist generation.

## Requirements

- Python 3.6+
- Docker (for containerised deployment)
- Emby Server with an API Key

## Installation

### Local Setup

1. Clone the repository:
   ```sh
   git clone https://github.com/troykelly/emby-to-m3u.git
   cd emby-to-m3u
   ```

2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```

3. Export environment variables:
   ```sh
   export EMBY_API_KEY='YOUR_API_KEY'
   export EMBY_SERVER_URL='http://YOUR_EMBY_SERVER'
   export M3U_DESTINATION='/path/to/m3u/destination'
   ```

4. Run the script:
   ```sh
   python3 src/main.py
   ```

### Docker Setup

1. Build the Docker image:
   ```sh
   docker build -t emby-to-m3u .
   ```

2. Run the Docker container:
   ```sh
   docker run -e EMBY_API_KEY='YOUR_API_KEY' \
              -e EMBY_SERVER_URL='http://YOUR_EMBY_SERVER' \
              -e M3U_DESTINATION='/path/to/m3u/destination' \
              -v /path/on/host:/path/to/m3u/destination \
              emby-to-m3u
   ```

## Environment Variables

### Emby Settings

- **EMBY_API_KEY**: The API key to authenticate with Emby.
- **EMBY_SERVER_URL**: The base URL of the Emby server (e.g., `http://localhost:8096`).
- **M3U_DESTINATION**: The directory where M3U files will be created.

### AzuraCast Sync

- **AZURACAST_HOST**: The host URL of your AzuraCast instance.
- **AZURACAST_API_KEY**: The API key for AzuraCast.
- **AZURACAST_STATIONID**: The ID of the AzuraCast station.

### Replay Gain

- **M3U_STRIP_PREFIX**: Optional prefix to strip from file paths.

### Logs and CI/CD

- **M3U_LOG_LEVEL**: Set the log level (default: `INFO`).
- **M3U_LOG_FILE**: Path to the log file.
- **LOG_FILE_MAX_BYTES**: Max bytes for log file before rotating (default: 10 MB).
- **LOG_FILE_BACKUP_COUNT**: Number of backup log files to keep (default: 5).

### Email Alerts (Postmark)

- **POSTMARK_API_TOKEN**: Token for Postmark service.
- **POSTMARK_SENDER_EMAIL**: Sender email address.
- **POSTMARK_RECEIVER_EMAILS**: List of receiver email addresses.
- **POSTMARK_ALERT_SUBJECT**: Subject line for alert emails.

## Usage

Set the required environment variables before running the script. You can set them in your shell session or in a `.env` file. Once set, you can run the Python script directly or use Docker to run the containerised version.

## AzuraCast Sync

AzuraCast is an open-source self-hosted web radio management suite. The Emby to M3U Playlist Generator can synchronise playlists with AzuraCast, ensuring your web radio playlists are always up-to-date.

### What It Does

The AzuraCast sync feature allows the tool to:
- Upload new tracks from your Emby server to AzuraCast.
- Generate and update playlists on AzuraCast, based on the genres, artists, albums, years, and custom radio playlists.
- Ensure all tracks have appropriate metadata, including ReplayGain values for consistent audio levels.

### Environment Variables for AzuraCast Sync

To enable AzuraCast sync, set the following environment variables:

- **AZURACAST_HOST**: The base URL of your AzuraCast instance (e.g., `http://your-azuracast-instance.com`).
- **AZURACAST_API_KEY**: The API key for authenticating with AzuraCast.
- **AZURACAST_STATIONID**: The ID of the station you want to manage in AzuraCast.

Example:
```sh
export AZURACAST_HOST='http://your-azuracast-instance.com'
export AZURACAST_API_KEY='YOUR_AZURACAST_API_KEY'
export AZURACAST_STATIONID='YOUR_STATION_ID'
```

### Syncing Playlists

When these environment variables are set:
1. The script will authenticate with your AzuraCast instance using the provided API key and station ID.
2. It will upload any new tracks found in your Emby library to AzuraCast.
3. It will generate and sync playlists according to the specified configuration (genres, artists, albums, etc.).

### Disabling Sync

If you want to disable syncing temporarily without removing the environment variables, you can set the `M3U_DONT_SYNC_AZURACAST` variable:
```sh
export M3U_DONT_SYNC_AZURACAST=true
```

This will prevent AzuraCast sync from running, but leave the rest of the process untouched.

### Requirements

Ensure your AzuraCast instance is running and accessible, and that the API key has the necessary permissions to manage files and playlists.

### Troubleshooting

- If you encounter issues with syncing, check the logs for detailed error messages. Ensure your API key and station ID are correct.
- Verify that your AzuraCast instance is reachable from the machine running the script.
- Ensure there is sufficient storage on your AzuraCast server for new tracks.

## Custom Radio Playlists

The Emby to M3U Playlist Generator also supports creating custom radio playlists by leveraging Last.fm for finding similar tracks and organising them in AzuraCast.

### Setting Up Custom Radio Playlists

The radio playlists can be defined using environment variables starting with `RADIO_PLAYLIST_`. Each environment variable corresponds to a playlist, and its value should be a comma-separated list of genres to include in that playlist.

Example:
```sh
export RADIO_PLAYLIST_MORNING='jazz,soft rock'
export RADIO_PLAYLIST_AFTERNOON='pop,dance'
export RADIO_PLAYLIST_NIGHT='ambient,classical'
```

In this example:
1. **RADIO_PLAYLIST_MORNING**: This playlist will include tracks from genres `jazz` and `soft rock`.
2. **RADIO_PLAYLIST_AFTERNOON**: This playlist will include tracks from genres `pop` and `dance`.
3. **RADIO_PLAYLIST_NIGHT**: This playlist will include tracks from genres `ambient` and `classical`.

### Reject Patterns for Radio Playlists

You can optionally specify reject patterns to exclude specific tracks or artists from the radio playlists using the `RADIO_REJECT_PLAYLIST_` and `RADIO_REJECT_ARTIST_` environment variables.

Example:
```sh
export RADIO_REJECT_PLAYLIST_MORNING='news,sports'
export RADIO_REJECT_PLAYLIST_AFTERNOON='advertisements,interviews'
export RADIO_REJECT_ARTIST_NIGHT='unknown artist'
```

In this example:
1. **RADIO_REJECT_PLAYLIST_MORNING**: Excludes tracks from `news` and `sports` genres from the morning playlist.
2. **RADIO_REJECT_PLAYLIST_AFTERNOON**: Excludes `advertisements` and `interviews` from the afternoon playlist.
3. **RADIO_REJECT_ARTIST_NIGHT**: Excludes tracks by `unknown artist` from the night playlist.

### Environment Variables Summary

- **RADIO_PLAYLIST_{NAME}**: Defines a custom playlist consisting of a comma-separated list of genres.
- **RADIO_REJECT_PLAYLIST_{NAME}**: Lists genres to exclude from a specific playlist.
- **RADIO_REJECT_ARTIST_{NAME}**: Lists artists to exclude from a specific playlist.

### Examples

```sh
export RADIO_PLAYLIST_WEEKEND='disco,house'
export RADIO_REJECT_PLAYLIST_WEEKEND='talk shows,news'
export RADIO_REJECT_ARTIST_WEEKEND='dj_unknown'
```

In this example:
- The `WEEKEND` playlist will include tracks from `disco` and `house` genres but exclude those from `talk shows` and `news` genres and any tracks by `dj_unknown`.

These environment variables allow you to customise your radio playlists extensively, ensuring they match your desired listening experience.

## Report Generation

The Emby to M3U Playlist Generator includes functionality to generate comprehensive reports of the playlist generation process. This includes detailed logging of each step taken and the resulting playlists.

### Markdown and PDF Reports

The script generates both Markdown and PDF reports:

- **Markdown Report**: Provides a detailed, human-readable report of the playlist generation process.
- **PDF Report**: A PDF version of the Markdown report for easy sharing and archiving.

### Reports Generated Include

1. **Playlist Generation Details**: A detailed log of all actions taken during playlist generation.
2. **Event Tracking**: Documentation of key events such as track addition, rejection, and syncing steps.
3. **Summary Statistics**: Overview of the number of tracks and playlists generated.

### Accessing the Reports

Upon completion of the script, the reports will be saved in the directory specified by `M3U_DESTINATION`:

- **Markdown Report**: `report.md`
- **PDF Report**: `report.pdf`

These reports will help you understand the outcomes of each run, diagnose any issues, and provide documentation for future reference.

## CI/CD

This project includes a GitHub Actions workflow for building and publishing Docker images. The workflow triggers on:

- Push events to the `main` branch.
- Release events.

### Workflow File: `.github/workflows/build-and-publish.yml`

The workflow builds the Docker image, tags it appropriately, and pushes it to GitHub Container Registry.

## License

This project is licensed under the Apache License, Version 2.0. See the [LICENSE](LICENSE) file for details.

## Contributing

1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/your-feature`).
3. Commit your changes (`git commit -am 'Add your feature'`).
4. Push to the branch (`git push origin feature/your-feature`).
5. Create a new Pull Request.

## Author

- Troy Kelly

## Acknowledgements

- Python libraries: requests, tqdm, dateutil
- Docker and GitHub Actions for CI/CD

Feel free to contribute, open issues, or request features!