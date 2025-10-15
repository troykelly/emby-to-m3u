# src/reporting/reporting.py

import datetime
import logging
from typing import Dict, List, Optional

import markdown
import pdfkit
from logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


class Event:
    """Class representing an event in the playlist report."""

    def __init__(
        self,
        event_type: str,
        notes: str,
        artist_name: Optional[str] = "",
        track_name: Optional[str] = "",
        genre: Optional[str] = "",
        length_seconds: Optional[int] = 0,
        gain: Optional[str] = "",
        peak: Optional[str] = "",
    ) -> None:
        """Initializes an Event with provided details."""
        self.event_type = event_type
        self.notes = notes
        self.artist_name = artist_name
        self.track_name = track_name
        self.genre = genre
        self.length_seconds = length_seconds
        self.gain = gain
        self.peak = peak


class PlaylistReport:
    """Class to generate a Markdown report for M3U playlist generation."""

    def __init__(self) -> None:
        """Initializes a PlaylistReport with an empty dictionary of events."""
        self.playlists: Dict[str, List[Event]] = {}

    def add_event(
        self,
        playlist_name: str,
        event_type: str,
        notes: str,
        artist_name: Optional[str] = "",
        track_name: Optional[str] = "",
        genre: Optional[str] = "",
        length_seconds: Optional[int] = 0,
        gain: Optional[str] = "",
        peak: Optional[str] = "",
    ) -> None:
        """Adds an event to the specified playlist.

        Args:
            playlist_name: The name of the playlist.
            event_type: The type of event.
            notes: Additional notes about the event.
            artist_name: The name of the artist.
            track_name: The name of the track.
            genre: The genre of the track.
            length_seconds: The length of the track in seconds.
            gain: The replay gain of the track.
            peak: The peak gain of the track.
        """
        event = Event(event_type, notes, artist_name, track_name, genre, length_seconds, gain, peak)
        logger.debug(f"Adding event to playlist '{playlist_name}': {event.__dict__}")
        if playlist_name not in self.playlists:
            self.playlists[playlist_name] = []
        self.playlists[playlist_name].append(event)

    def _calculate_column_widths(self, events: List[Event]) -> Dict[str, int]:
        """Calculates the maximum width for each column based on the events.

        Args:
            events: A list of events.

        Returns:
            A dictionary with column names as keys and their respective max widths as values.
        """
        columns = [
            "event_type",
            "notes",
            "artist_name",
            "track_name",
            "genre",
            "length_seconds",
            "gain",
            "peak",
        ]

        max_widths = {column: len(column.replace("_", " ").title()) for column in columns}

        for event in events:
            max_widths["event_type"] = max(max_widths["event_type"], len(event.event_type))
            max_widths["notes"] = max(max_widths["notes"], len(event.notes))
            max_widths["artist_name"] = max(max_widths["artist_name"], len(event.artist_name))
            max_widths["track_name"] = max(max_widths["track_name"], len(event.track_name))
            max_widths["genre"] = max(max_widths["genre"], len(event.genre))
            max_widths["length_seconds"] = max(
                max_widths["length_seconds"], len(str(event.length_seconds))
            )
            max_widths["gain"] = max(max_widths["gain"], len(event.gain))
            max_widths["peak"] = max(max_widths["peak"], len(event.peak))

        return max_widths

    def generate_markdown(self) -> str:
        """Generates a Markdown report for the playlist events.

        Returns:
            A string containing the Markdown report.
        """
        report_lines = [
            f"# Generation Report for M3U to AzuraCast",
            f"## {datetime.datetime.now().strftime('%H:%M %a %-d %B %Y')}",
        ]

        for playlist_name, events in self.playlists.items():
            report_lines.append(f"\n### {playlist_name}\n")

            # Calculate max widths for formatting
            max_widths = self._calculate_column_widths(events)

            # Header
            header = (
                "| "
                + " | ".join(
                    [
                        f"{column.replace('_', ' ').title():<{max_widths[column]}}"
                        for column in [
                            "event_type",
                            "notes",
                            "artist_name",
                            "track_name",
                            "genre",
                            "length_seconds",
                            "gain",
                            "peak",
                        ]
                    ]
                )
                + " |"
            )
            align_row = (
                "|-"
                + "-|-".join(
                    [
                        "-" * max_widths[column]
                        for column in [
                            "event_type",
                            "notes",
                            "artist_name",
                            "track_name",
                            "genre",
                            "length_seconds",
                            "gain",
                            "peak",
                        ]
                    ]
                )
                + "-|"
            )
            report_lines.append(header)
            report_lines.append(align_row)

            # Rows
            for event in events:
                report_lines.append(
                    f"| {event.event_type:<{max_widths['event_type']}}"
                    f" | {event.notes:<{max_widths['notes']}}"
                    f" | {event.artist_name:<{max_widths['artist_name']}}"
                    f" | {event.track_name:<{max_widths['track_name']}}"
                    f" | {event.genre:<{max_widths['genre']}}"
                    f" | {event.length_seconds:<{max_widths['length_seconds']}}"
                    f" | {event.gain:<{max_widths['gain']}}"
                    f" | {event.peak:<{max_widths['peak']}} |"
                )

        return "\n".join(report_lines)

    def generate_pdf(self, page_size: str = "A4", orientation: str = "landscape") -> bytes:
        """Generates a PDF of the Markdown report.

        Args:
            page_size: The page size of the PDF (default is 'A4').
            orientation: The orientation of the PDF (default is 'landscape').

        Returns:
            A bytes object containing the PDF data.
        """
        markdown_report = self.generate_markdown()
        html_report = self._convert_markdown_to_html(markdown_report)

        pdf_options = {
            "page-size": page_size,
            "orientation": orientation,
        }

        pdf_bytes = pdfkit.from_string(html_report, False, options=pdf_options)

        return pdf_bytes

    def _convert_markdown_to_html(self, markdown_content: str) -> str:
        """Converts Markdown content to a formatted HTML.

        Args:
            markdown_content: The raw Markdown content.

        Returns:
            A formatted HTML string with embedded styles.
        """
        styles = """
        <style>
            body {
                font-family: Arial, sans-serif;
            }
            h1, h2, h3 {
                color: #333;
                margin-bottom: 16px;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }
            th {
                background-color: #f2f2f2;
            }
            tr:nth-child(even) {
                background-color: #f9f9f9;
            }
        </style>
        """

        html_template = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Playlist Report</title>
            {styles}
        </head>
        <body>
            {markdown.markdown(markdown_content, extensions=['tables'])}
        </body>
        </html>
        """

        return html_template

    def __enter__(self) -> "PlaylistReport":
        """Enter the runtime context for this object."""
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Exit the runtime context, clean up resources."""
        self.playlists.clear()
