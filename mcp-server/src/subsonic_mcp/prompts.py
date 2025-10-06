"""MCP Prompts Registry - 5 prompts for common music workflows.

This module implements the PromptRegistry class that exposes 5 MCP prompts
for AI-powered music discovery and playlist generation. All prompt contracts
match prompts.json schema.
"""

from typing import Any
import mcp.types as types


class PromptRegistry:
    """Registry for all 5 MCP prompts.

    Provides 5 prompts that match the prompts.json contract schema:
        1. mood_playlist - Generate curated playlist by mood
        2. music_discovery - Discover new music based on preferences
        3. listening_analysis - Analyze listening patterns
        4. smart_playlist - Create rules-based smart playlist
        5. library_curation - Organize and clean library
    """

    def __init__(self):
        """Initialize prompt registry."""
        self.prompts = self._define_prompts()

    def _define_prompts(self) -> dict[str, types.Prompt]:
        """Define all 5 prompts per prompts.json contract.

        Returns:
            Dictionary mapping prompt names to Prompt definitions
        """
        return {
            "mood_playlist": types.Prompt(
                name="mood_playlist",
                description="Generate a curated playlist based on mood or activity",
                arguments=[
                    types.PromptArgument(
                        name="mood",
                        description="Target mood or genre (e.g., relaxing, energetic, jazz, rock)",
                        required=True,
                    ),
                    types.PromptArgument(
                        name="duration",
                        description="Target duration in minutes",
                        required=False,
                    ),
                ],
            ),
            "music_discovery": types.Prompt(
                name="music_discovery",
                description="Discover new music based on user preferences and listening history",
                arguments=[
                    types.PromptArgument(
                        name="favorite_artists",
                        description="Comma-separated list of favorite artists",
                        required=True,
                    ),
                    types.PromptArgument(
                        name="genres",
                        description="Comma-separated list of preferred genres (optional)",
                        required=False,
                    ),
                ],
            ),
            "listening_analysis": types.Prompt(
                name="listening_analysis",
                description="Analyze listening patterns and library composition",
                arguments=[
                    types.PromptArgument(
                        name="analysis_type",
                        description="Type of analysis to perform",
                        required=True,
                    )
                ],
            ),
            "smart_playlist": types.Prompt(
                name="smart_playlist",
                description="Create a rules-based smart playlist with specific criteria",
                arguments=[
                    types.PromptArgument(
                        name="criteria",
                        description="Playlist generation criteria (e.g., '80s rock with high energy')",
                        required=True,
                    ),
                    types.PromptArgument(
                        name="max_tracks",
                        description="Maximum number of tracks in playlist",
                        required=False,
                    ),
                ],
            ),
            "library_curation": types.Prompt(
                name="library_curation",
                description="Organize and clean music library (find duplicates, missing metadata, quality issues)",
                arguments=[
                    types.PromptArgument(
                        name="task",
                        description="Curation task to perform",
                        required=True,
                    )
                ],
            ),
        }

    def get_all(self) -> list[types.Prompt]:
        """Get all prompt definitions.

        Returns:
            List of all 5 Prompt objects
        """
        return list(self.prompts.values())

    @staticmethod
    async def get_prompt(prompt_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get a prompt with arguments filled in (used in tests).

        Args:
            prompt_name: Name of prompt to get
            arguments: Prompt arguments

        Returns:
            Prompt result with description and messages

        Raises:
            ValueError: If prompt_name is invalid
        """
        # Route to appropriate handler
        handlers = {
            "mood_playlist": PromptRegistry._mood_playlist,
            "music_discovery": PromptRegistry._music_discovery,
            "listening_analysis": PromptRegistry._listening_analysis,
            "smart_playlist": PromptRegistry._smart_playlist,
            "library_curation": PromptRegistry._library_curation,
        }

        if prompt_name not in handlers:
            raise ValueError(f"Unknown prompt: {prompt_name}")

        return handlers[prompt_name](arguments)

    # Prompt handler methods (private static)

    @staticmethod
    def _mood_playlist(arguments: dict[str, Any]) -> dict[str, Any]:
        """Generate mood_playlist prompt."""
        mood = arguments["mood"]
        duration = arguments.get("duration", 60)

        prompt_text = f"""Create a curated {duration}-minute playlist for a {mood} mood.

Use the available music tools to:
1. Search for tracks that match the {mood} mood/genre
2. Analyze the library to find suitable tracks
3. Consider tempo, energy, and genre characteristics

Generate a playlist with approximately {duration} minutes of music that creates
the perfect {mood} atmosphere. Include track titles, artists, and brief descriptions
of why each track fits the mood."""

        return {
            "description": f"Generate {mood} mood playlist ({duration} minutes)",
            "messages": [
                {
                    "role": "user",
                    "content": {"type": "text", "text": prompt_text},
                }
            ],
        }

    @staticmethod
    def _music_discovery(arguments: dict[str, Any]) -> dict[str, Any]:
        """Generate music_discovery prompt."""
        favorite_artists = arguments["favorite_artists"]
        genres = arguments.get("genres", "")

        genre_text = f" Focus on these genres: {genres}." if genres else ""

        prompt_text = f"""Discover new music based on my preferences.

Favorite artists: {favorite_artists}{genre_text}

Use the music library tools to:
1. Find similar artists and tracks
2. Explore related genres
3. Analyze patterns in the library

Recommend 10-15 tracks or artists I might enjoy, with explanations of why
each recommendation matches my taste. Include diversity while staying true
to my preferences."""

        return {
            "description": f"Discover music similar to {favorite_artists}",
            "messages": [
                {
                    "role": "user",
                    "content": {"type": "text", "text": prompt_text},
                }
            ],
        }

    @staticmethod
    def _listening_analysis(arguments: dict[str, Any]) -> dict[str, Any]:
        """Generate listening_analysis prompt."""
        analysis_type = arguments["analysis_type"]

        analysis_prompts = {
            "genre_distribution": """Analyze the genre distribution in my music library.

Use analyze_library and get_genres tools to:
1. Get genre statistics
2. Calculate percentages for each genre
3. Identify most and least represented genres
4. Visualize distribution (text-based)

Provide insights about my musical diversity and genre preferences.""",
            "artist_diversity": """Analyze artist diversity in my music library.

Use library tools to:
1. Count unique artists
2. Identify most collected artists
3. Calculate average tracks per artist
4. Find one-hit wonders vs. deep catalogs

Provide insights about my collection strategy and artist loyalty.""",
            "decade_breakdown": """Analyze music by decade in my library.

Use library tools to:
1. Group tracks by release decade
2. Calculate counts and percentages
3. Identify dominant eras
4. Note gaps or underrepresented periods

Provide insights about my musical time period preferences.""",
        }

        prompt_text = analysis_prompts.get(
            analysis_type, "Analyze the music library."
        )

        return {
            "description": f"Analyze library: {analysis_type}",
            "messages": [
                {
                    "role": "user",
                    "content": {"type": "text", "text": prompt_text},
                }
            ],
        }

    @staticmethod
    def _smart_playlist(arguments: dict[str, Any]) -> dict[str, Any]:
        """Generate smart_playlist prompt."""
        criteria = arguments["criteria"]
        max_tracks = arguments.get("max_tracks", 50)

        prompt_text = f"""Create a smart playlist based on these criteria: {criteria}

Maximum tracks: {max_tracks}

Use the music library tools to:
1. Search for tracks matching the criteria
2. Filter by genre, year, or other attributes
3. Find similar tracks to expand the selection
4. Ensure variety while maintaining theme

Generate a playlist of up to {max_tracks} tracks that perfectly match the
criteria "{criteria}". Include track details and explanation of selection."""

        return {
            "description": f"Smart playlist: {criteria}",
            "messages": [
                {
                    "role": "user",
                    "content": {"type": "text", "text": prompt_text},
                }
            ],
        }

    @staticmethod
    def _library_curation(arguments: dict[str, Any]) -> dict[str, Any]:
        """Generate library_curation prompt."""
        task = arguments["task"]

        curation_prompts = {
            "duplicates": """Find duplicate tracks in my music library.

Use library tools to:
1. Get all tracks
2. Compare titles and artists
3. Check for exact matches and near-duplicates
4. Identify tracks with same artist/title but different albums

Report all duplicates with details for manual review.""",
            "missing_metadata": """Find tracks with missing or incomplete metadata.

Use library tools to:
1. Get all tracks
2. Check for missing genre, year, album, or artist
3. Identify tracks with generic or placeholder values
4. Group by metadata issue type

Report all tracks needing metadata cleanup.""",
            "quality_issues": """Identify potential quality issues in the library.

Use library tools to:
1. Check bitrates (flag anything < 128 kbps)
2. Find unusually short tracks (< 30 seconds)
3. Identify missing streaming URLs
4. Detect format inconsistencies

Report all quality issues for review.""",
        }

        prompt_text = curation_prompts.get(
            task, "Curate the music library."
        )

        return {
            "description": f"Library curation: {task}",
            "messages": [
                {
                    "role": "user",
                    "content": {"type": "text", "text": prompt_text},
                }
            ],
        }
