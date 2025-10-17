"""
Playlist Exporters - T036

Export playlists to M3U format with support for Subsonic track IDs and AzuraCast.

Success Criteria (T030):
- Export to EXTM3U format
- Include #EXTM3U, #PLAYLIST, #EXTINF, track IDs
- Support Subsonic format: subsonic:track:<id>
"""

from pathlib import Path
from typing import Optional
import logging

from src.ai_playlist.models.core import Playlist

logger = logging.getLogger(__name__)


class M3UExporter:
    """Export playlists to M3U format."""

    def export_to_m3u(
        self,
        playlist: Playlist,
        output_path: Path,
        use_subsonic_format: bool = True
    ) -> None:
        """Export playlist to M3U file.

        Args:
            playlist: Playlist to export
            output_path: Path to output M3U file
            use_subsonic_format: Use subsonic:track:<id> format (default True)
        """
        lines = []

        # M3U header
        lines.append("#EXTM3U")
        lines.append(f"#PLAYLIST:{playlist.name}")
        lines.append("")

        # Add each track
        for track in playlist.tracks:
            # EXTINF line: #EXTINF:duration,artist - title
            duration = int(track.duration_seconds) if track.duration_seconds else -1
            lines.append(f"#EXTINF:{duration},{track.artist} - {track.title}")

            # Track reference
            if use_subsonic_format:
                lines.append(f"subsonic:track:{track.track_id}")
            else:
                lines.append(track.track_id)

            lines.append("")

        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        logger.info(
            f"Exported playlist '{playlist.name}' with {len(playlist.tracks)} "
            f"tracks to {output_path}"
        )

    def export_to_pls(
        self,
        playlist: Playlist,
        output_path: Path
    ) -> None:
        """Export playlist to PLS format (alternative format).

        Args:
            playlist: Playlist to export
            output_path: Path to output PLS file
        """
        lines = []

        # PLS header
        lines.append("[playlist]")
        lines.append("")

        # Add entries
        for i, track in enumerate(playlist.tracks, start=1):
            lines.append(f"File{i}={track.track_id}")
            lines.append(f"Title{i}={track.artist} - {track.title}")
            lines.append(f"Length{i}={int(track.duration_seconds) if track.duration_seconds else -1}")
            lines.append("")

        # Footer
        lines.append(f"NumberOfEntries={len(playlist.tracks)}")
        lines.append("Version=2")

        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        logger.info(
            f"Exported playlist '{playlist.name}' to PLS format at {output_path}"
        )


class AzuraCastExporter:
    """Export playlists in AzuraCast-compatible format."""

    def export_for_azuracast(
        self,
        playlist: Playlist,
        output_path: Path
    ) -> None:
        """Export playlist for AzuraCast import.

        AzuraCast accepts M3U format with file paths or URLs.

        Args:
            playlist: Playlist to export
            output_path: Path to output file
        """
        exporter = M3UExporter()
        exporter.export_to_m3u(playlist, output_path, use_subsonic_format=True)

        logger.info(
            f"Exported AzuraCast-compatible playlist to {output_path}"
        )
