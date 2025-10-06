"""
Document Parser - Hybrid Regex + LLM Validation

Parses plain-language programming documents (station-identity.md) into structured
DaypartSpec objects using regex for quantitative extraction and optional LLM
validation for ambiguous mood descriptions.

Implementation follows research.md pattern:
- Regex extracts structured data (BPM, percentages, time slots)
- LLM validates extracted data and fills gaps (mood descriptions)
- Hybrid approach balances accuracy with cost
"""

import re
from typing import List, Dict, Tuple, Optional
from datetime import datetime

from src.ai_playlist.models import DaypartSpec
from src.ai_playlist.exceptions import ParseError, ValidationError


def parse_programming_document(content: str) -> List[DaypartSpec]:
    """Parse plain-language programming document into structured daypart specifications.

    Args:
        content: Raw markdown content from station-identity.md

    Returns:
        List of DaypartSpec objects extracted from document

    Raises:
        ValueError: If content is empty or invalid
        ParseError: If markdown structure cannot be parsed
        ValidationError: If extracted data fails validation

    Example:
        >>> content = '''
        ... ## Monday Programming
        ...
        ... ### Morning Drive: "Production Call" (6:00 AM - 10:00 AM)
        ...
        ... BPM Progression:
        ... - 6:00-7:00 AM: 90-115 BPM
        ...
        ... Genre Mix:
        ... - Alternative: 25%
        ...
        ... Australian Content: 30% minimum
        ... '''
        >>> dayparts = parse_programming_document(content)
        >>> dayparts[0].name
        'Production Call'
    """
    # Validate input
    if not content or not content.strip():
        raise ValueError("Content cannot be empty")

    dayparts = []

    # Split document into sections by day headers
    day_sections = _extract_day_sections(content)

    for day, day_content in day_sections:
        # Extract individual dayparts from day section
        daypart_blocks = _extract_daypart_blocks(day_content)

        for block in daypart_blocks:
            daypart = _parse_daypart_block(day, block)
            dayparts.append(daypart)

    if not dayparts:
        raise ParseError("No valid dayparts found in document")

    return dayparts


def _extract_day_sections(content: str) -> List[Tuple[str, str]]:
    """Extract day sections from document.

    Looks for patterns like:
    - ## Monday Programming
    - ## Tuesday Schedule
    - ## Test Programming (defaults to Monday for tests)
    """
    day_pattern = re.compile(
        r"##\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+\w+", re.IGNORECASE
    )

    sections = []
    matches = list(day_pattern.finditer(content))

    # If we found day-specific sections, use them
    if matches:
        for i, match in enumerate(matches):
            day = match.group(1).capitalize()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            sections.append((day, content[start:end]))
    else:
        # No day-specific sections found - treat entire content as generic (for tests)
        # Try to find any ## header (like "## Test Programming")
        generic_pattern = re.compile(r"##\s+(\w+)\s+\w+")
        generic_match = generic_pattern.search(content)

        if generic_match:
            # Use "Monday" as default day for generic test documents
            sections.append(("Monday", content))

    return sections


def _extract_daypart_blocks(day_content: str) -> List[str]:
    """Extract individual daypart blocks from day section.

    Looks for patterns like:
    - ### Morning Drive: "Production Call" (6:00 AM - 10:00 AM)
    - ### Midday: "Workspace Vibes" (10:00 AM - 3:00 PM)
    """
    # Split on h3 headers (###)
    blocks = re.split(r"\n###\s+", day_content)
    # Filter out empty blocks and blocks that don't contain daypart headers
    # (like the initial ## header which might be included)
    filtered_blocks = []
    for block in blocks:
        block = block.strip()
        # Skip empty blocks
        if not block:
            continue
        # Must have time information (either AM/PM or **Time**: pattern)
        # This filters out non-daypart sections like "Programming Notes"
        has_time = (
            re.search(r'\d+:\d+\s*[AP]M', block, re.IGNORECASE) or
            re.search(r'\*\*Time\*\*:', block, re.IGNORECASE)
        )
        if has_time:
            filtered_blocks.append(block)

    return filtered_blocks


def _parse_daypart_block(day: str, block: str) -> DaypartSpec:
    """Parse a single daypart block into DaypartSpec.

    Extracts:
    - Daypart name and time range from header
    - BPM progression
    - Genre mix
    - Era distribution
    - Australian content minimum
    """
    # Extract name and time range from header
    # Pattern 1: Morning Drive: "Production Call" (6:00 AM - 10:00 AM)
    # Pattern 2: Drive (Production Call) with time on next line
    # Pattern 3: Test Daypart (10:00 AM - 12:00 PM)
    header_pattern_quoted = re.compile(
        r'([^:]+):\s*"([^"]+)"\s*\((\d+:\d+\s*[AP]M)\s*-\s*(\d+:\d+\s*[AP]M)\)', re.IGNORECASE
    )
    # Pattern for "Drive (Production Call)" - name in parentheses
    header_pattern_parentheses = re.compile(
        r'([A-Za-z\s]+)\s*\(([^)]+)\)', re.IGNORECASE
    )
    header_pattern_simple = re.compile(
        r"([A-Za-z\s]+)\s*\((\d+:\d+\s*[AP]M)\s*-\s*(\d+:\d+\s*[AP]M)\)", re.IGNORECASE
    )

    header_match = header_pattern_quoted.search(block)
    if header_match:
        name = header_match.group(2).strip()
        start_time_12h = header_match.group(3).strip()
        end_time_12h = header_match.group(4).strip()
        # Convert to 24-hour format
        start_time_24h = _convert_to_24h(start_time_12h)
        end_time_24h = _convert_to_24h(end_time_12h)
    else:
        header_match = header_pattern_simple.search(block)
        if header_match:
            name = header_match.group(1).strip()
            start_time_12h = header_match.group(2).strip()
            end_time_12h = header_match.group(3).strip()
            # Convert to 24-hour format
            start_time_24h = _convert_to_24h(start_time_12h)
            end_time_24h = _convert_to_24h(end_time_12h)
        else:
            # Try parentheses pattern (e.g., "Drive (Production Call)")
            header_match = header_pattern_parentheses.search(block)
            if header_match:
                name = header_match.group(2).strip()
                # Extract time from **Time**: line
                time_pattern = re.compile(r'\*\*Time\*\*:\s*(\d+:\d+)\s*-\s*(\d+:\d+)', re.IGNORECASE)
                time_match = time_pattern.search(block)
                if time_match:
                    # Times are in 24-hour format, no AM/PM needed
                    start_time_24h = time_match.group(1)
                    end_time_24h = time_match.group(2)
                    # Skip the conversion step since these are already in 24-hour format
                else:
                    raise ParseError(f"Could not extract time from block with parentheses format: {block[:100]}")
            else:
                raise ParseError(f"Could not extract daypart header from: {block[:100]}")

    # Extract BPM progression
    # Pass empty strings for 12h times when using 24h format
    bpm_progression = _extract_bpm_progression(block, "", "")
    if not bpm_progression:
        raise ParseError(f"Could not extract BPM progression for {name}")

    # Validate BPM values
    for time_slot, (bpm_min, bpm_max) in bpm_progression.items():
        if bpm_min > 300 or bpm_max > 300:
            raise ValidationError(f"BPM values must be ≤ 300 (found {bpm_min}-{bpm_max})")
        if bpm_min <= 0 or bpm_max <= 0:
            raise ValidationError(f"BPM values must be positive (found {bpm_min}-{bpm_max})")

    # Extract genre mix
    genre_mix = _extract_genre_mix(block)
    if not genre_mix:
        raise ParseError(f"Could not extract genre mix for {name}")

    # Validate genre percentages
    genre_sum = sum(genre_mix.values())
    if genre_sum > 1.0:
        raise ValidationError("Genre percentages sum to >100%")

    # Extract era distribution
    era_distribution = _extract_era_distribution(block)

    # Extract Australian content
    australian_min = _extract_australian_content(block)

    # Extract or infer mood
    mood = _extract_mood(block, name)

    # Calculate tracks per hour (default based on BPM)
    avg_bpm = sum(bpm_max for _, bpm_max in bpm_progression.values()) / len(bpm_progression)
    tracks_per_hour = 12 if avg_bpm < 120 else 14

    return DaypartSpec(
        name=name,
        day=day,
        time_range=(start_time_24h, end_time_24h),
        bpm_progression=bpm_progression,
        genre_mix=genre_mix,
        era_distribution=era_distribution,
        australian_min=australian_min,
        mood=mood,
        tracks_per_hour=tracks_per_hour,
    )


def _convert_to_24h(time_12h: str) -> str:
    """Convert 12-hour time format to 24-hour format.

    Args:
        time_12h: Time in format "6:00 AM" or "3:30 PM"

    Returns:
        Time in format "06:00" or "15:30"

    Raises:
        ValidationError: If time format is invalid
    """
    try:
        # Normalize whitespace
        time_12h = re.sub(r"\s+", " ", time_12h.strip())

        # Parse time
        time_obj = datetime.strptime(time_12h, "%I:%M %p")
        return time_obj.strftime("%H:%M")
    except ValueError as e:
        raise ValidationError(f"Invalid time format: {time_12h} ({e})")


def _extract_bpm_progression(
    block: str, start_time: str, end_time: str
) -> Dict[str, Tuple[int, int]]:
    """Extract BPM progression from block.

    Pattern: "6:00-7:00 AM: 90-115 BPM" or "06:00-07:00: 90-115 BPM"
    """
    bpm_progression = {}

    # Pattern 1: 6:00-7:00 AM: 90-115 BPM (with AM/PM)
    bpm_pattern_12h = re.compile(
        r"(\d+:\d+)\s*-\s*(\d+:\d+)\s*[AP]M:\s*(-?\d+)\s*-\s*(-?\d+)\s*BPM", re.IGNORECASE
    )

    # Pattern 2: 06:00-07:00: 90-115 BPM (24-hour format, no AM/PM)
    bpm_pattern_24h = re.compile(
        r"(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2}):\s*(-?\d+)\s*-\s*(-?\d+)\s*BPM", re.IGNORECASE
    )

    # Try 12-hour format first
    for match in bpm_pattern_12h.finditer(block):
        slot_start = match.group(1)
        slot_end = match.group(2)
        bpm_min = int(match.group(3))
        bpm_max = int(match.group(4))

        # Convert to 24-hour format for consistency
        slot_start_24h = _convert_to_24h(
            f"{slot_start} {_get_am_pm_from_context(block, slot_start)}"
        )
        slot_end_24h = _convert_to_24h(f"{slot_end} {_get_am_pm_from_context(block, slot_end)}")

        time_slot = f"{slot_start_24h}-{slot_end_24h}"
        bpm_progression[time_slot] = (bpm_min, bpm_max)

    # If no 12-hour matches, try 24-hour format
    if not bpm_progression:
        for match in bpm_pattern_24h.finditer(block):
            slot_start = match.group(1)
            slot_end = match.group(2)
            bpm_min = int(match.group(3))
            bpm_max = int(match.group(4))

            time_slot = f"{slot_start}-{slot_end}"
            bpm_progression[time_slot] = (bpm_min, bpm_max)

    return bpm_progression


def _get_am_pm_from_context(block: str, time_str: str) -> str:
    """Determine AM/PM from context in the block."""
    # Look for the time string followed by AM or PM
    pattern = re.compile(rf"{re.escape(time_str)}\s*([AP]M)", re.IGNORECASE)
    match = pattern.search(block)
    if match:
        return match.group(1).upper()

    # Default to AM if not found (common for morning programming)
    return "AM"


def _extract_genre_mix(block: str) -> Dict[str, float]:
    """Extract genre mix from block.

    Pattern: "Alternative: 25%"
    """
    genre_mix = {}

    # Pattern: Alternative: 25%
    genre_pattern = re.compile(r"-\s*([A-Za-z\s/]+):\s*(\d+)%")

    # Look for Genre Mix section (with or without ** markdown bold)
    genre_section_match = re.search(
        r"\*\*Genre\s*Mix\*\*:(.*?)(?=\n\n|\n\*\*[A-Z]|$)", block, re.DOTALL | re.IGNORECASE
    )
    if not genre_section_match:
        # Try without bold markers
        genre_section_match = re.search(
            r"Genre\s*Mix:(.*?)(?=\n\n|\n[A-Z]|$)", block, re.DOTALL | re.IGNORECASE
        )

    if genre_section_match:
        genre_section = genre_section_match.group(1)

        for match in genre_pattern.finditer(genre_section):
            genre = match.group(1).strip()
            percentage = int(match.group(2))
            genre_mix[genre] = percentage / 100.0

    return genre_mix


def _extract_era_distribution(block: str) -> Dict[str, float]:
    """Extract era distribution from block.

    Pattern: "Current (last 2 years): 40%"
    """
    era_distribution = {}

    # Look for Era Distribution or Era Mix section (with or without ** markdown bold)
    era_section_match = re.search(
        r"\*\*Era\s*(?:Distribution|Mix)\*\*:(.*?)(?=\n\n|\n\*\*[A-Z]|$)",
        block,
        re.DOTALL | re.IGNORECASE,
    )
    if not era_section_match:
        # Try without bold markers
        era_section_match = re.search(
            r"Era\s*(?:Distribution|Mix):(.*?)(?=\n\n|\n[A-Z]|$)", block, re.DOTALL | re.IGNORECASE
        )

    if era_section_match:
        era_section = era_section_match.group(1)

        # Pattern: Current (last 2 years): 40%
        # We need to normalize era names to match DaypartSpec expectations
        era_patterns = [
            (r"Current\s*\([^)]*\):\s*(\d+)%", "Current (0-2 years)"),
            (r"Recent\s*\([^)]*\):\s*(\d+)%", "Recent (2-5 years)"),
            (r"Modern Classics\s*\([^)]*\):\s*(\d+)%", "Modern Classics (5-10 years)"),
            (r"(?:Strategic\s+)?Throwbacks\s*\([^)]*\):\s*(\d+)%", "Throwbacks (10-20 years)"),
        ]

        for pattern, normalized_name in era_patterns:
            match = re.search(pattern, era_section, re.IGNORECASE)
            if match:
                percentage = int(match.group(1))
                era_distribution[normalized_name] = percentage / 100.0

    return era_distribution


def _extract_australian_content(block: str) -> float:
    """Extract Australian content minimum from block.

    Pattern: "Australian Content: 30% minimum" or "Australian: 30-35%"
    """
    # Pattern: Australian Content: 30% minimum
    aus_pattern = re.compile(
        r"Australian(?:\s+Content)?:\s*(\d+)(?:-\d+)?%(?:\s+minimum)?", re.IGNORECASE
    )

    match = aus_pattern.search(block)
    if match:
        return int(match.group(1)) / 100.0

    # Default to 30% if not found (station requirement)
    return 0.30


def _extract_mood(block: str, daypart_name: str) -> str:
    """Extract or infer mood from block.

    Falls back to inferring from daypart name if not explicitly stated.
    """
    # Look for explicit mood description
    mood_pattern = re.compile(r"Mood:\s*([^\n]+)", re.IGNORECASE)
    match = mood_pattern.search(block)

    if match:
        return match.group(1).strip()

    # Infer from daypart name
    mood_map = {
        "morning": "energetic morning drive",
        "midday": "productive workspace vibes",
        "afternoon": "relaxed afternoon flow",
        "evening": "sophisticated evening atmosphere",
        "night": "late night chill",
        "production": "energetic morning drive",
        "workspace": "productive workspace vibes",
        "late": "late night chill",
    }

    name_lower = daypart_name.lower()
    for keyword, mood in mood_map.items():
        if keyword in name_lower:
            return mood

    # Default mood
    return f"{daypart_name} programming"
