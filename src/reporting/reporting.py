# src/reporting/reporting.py

import datetime
from typing import Dict, List, Optional


class Event:
    """Class representing an event in the playlist report."""
    
    def __init__(
        self,
        event_type: str,
        notes: str,
        artist_name: Optional[str] = '',
        track_name: Optional[str] = '',
        genre: Optional[str] = '',
        length_seconds: Optional[int] = 0,
        gain: Optional[str] = '',
        peak: Optional[str] = ''
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
        artist_name: Optional[str] = '',
        track_name: Optional[str] = '',
        genre: Optional[str] = '',
        length_seconds: Optional[int] = 0,
        gain: Optional[str] = '',
        peak: Optional[str] = ''
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
        event = Event(
            event_type, notes, artist_name, track_name, genre, length_seconds, gain, peak
        )
        if playlist_name not in self.playlists:
            self.playlists[playlist_name] = []
        self.playlists[playlist_name].append(event)

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

            report_lines.append(
                "| Event | Notes | Artist Name | Track Name | Genre | Length (s) | Gain | Peak |"
            )
            report_lines.append(
                "|-------|-------|-------------|------------|-------|------------|------|------|"
            )

            for event in events:
                report_lines.append(
                    f"| {event.event_type} | {event.notes} | {event.artist_name} | {event.track_name} | "
                    f"{event.genre} | {event.length_seconds} | {event.gain} | {event.peak} |"
                )

        return "\n".join(report_lines)