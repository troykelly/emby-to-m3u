# Emby to M3U Playlist Generator

![GitHub license](https://img.shields.io/badge/license-Apache%202.0-blue.svg)
![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/troykelly/emby-to-m3u/build-and-publish.yml)

## Overview

The Emby to M3U Playlist Generator is a Python script that connects to the Emby API, retrieves all music tracks, and generates M3U playlist files for each genre, artist, and album. The generated playlists help in organizing your music library efficiently.

## Features

- Generates M3U playlists for:
  - Genres
  - Artists
  - Albums
- Fetches metadata from Emby, including external IDs.
- Supports customizations using environment variables.
- Dockerized for easy deployment.
- CI/CD pipeline for automated Docker image building and publishing.

## Requirements

- Python 3.6+
- Docker (for containerized deployment)
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

- **EMBY_API_KEY**: The API key to authenticate with Emby.
- **EMBY_SERVER_URL**: The base URL of the Emby server (e.g., `http://localhost:8096`).
- **M3U_DESTINATION**: The directory where M3U files will be created.

## Usage

Make sure to set the environment variables before running the script. You can set them in your shell session or in a `.env` file. Once set, you can run the Python script directly or use Docker to run the containerized version.

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
