"""
Document Parser for Station Identity - T031

Parses station-identity.md into StationIdentityDocument with all programming structures,
dayparts, BPM progressions, genre/era distributions, and Australian content requirements.

Success Criteria (T020):
- Load actual station-identity.md file
- Parse all programming structures (Weekday, Saturday, Sunday)
- Extract dayparts with complete metadata
- Validate Australian content minimum = 30%
- Genre/era percentages sum to 1.0 ±0.01
"""

import re
import hashlib
from pathlib import Path
from datetime import datetime, time
from typing import List, Dict, Tuple, Optional
import uuid

from src.ai_playlist.models.core import (
    StationIdentityDocument,
    ProgrammingStructure,
    DaypartSpecification,
    ScheduleType,
    BPMRange,
    GenreCriteria,
    EraCriteria,
    RotationStrategy,
    RotationCategory,
    ContentRequirements,
    GenreDefinition,
    SpecialtyConstraint
)


class DocumentParser:
    """Parser for station-identity.md documents."""

    def load_document(self, path: Path) -> StationIdentityDocument:
        """Load and parse station-identity.md file.

        Args:
            path: Path to station-identity.md

        Returns:
            Parsed StationIdentityDocument instance

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If content is invalid
        """
        if not path.exists():
            raise FileNotFoundError(f"Station identity file not found: {path}")

        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        if not content.strip():
            raise ValueError("Station identity file is empty")

        # Calculate version hash
        version = hashlib.sha256(content.encode()).hexdigest()

        # Parse programming structures
        programming_structures = self._parse_programming_structures(content)

        # Parse rotation strategy
        rotation_strategy = self._parse_rotation_strategy(content)

        # Parse content requirements
        content_requirements = self._parse_content_requirements(content)

        # Parse genre definitions
        genre_definitions = self._parse_genre_definitions(content)

        return StationIdentityDocument(
            document_path=path,
            programming_structures=programming_structures,
            rotation_strategy=rotation_strategy,
            content_requirements=content_requirements,
            genre_definitions=genre_definitions,
            version=version,
            loaded_at=datetime.now()
        )

    def _parse_programming_structures(self, content: str) -> List[ProgrammingStructure]:
        """Parse programming structures (Weekday, Saturday, Sunday)."""
        structures = []

        # Find programming structure sections
        # Pattern: ## Monday to Friday Programming or ## Weekday Programming
        weekday_pattern = re.compile(
            r'##\s+(Monday\s+to\s+Friday|Weekday)\s+Programming(.*?)(?=##\s+\w+\s+Programming|$)',
            re.IGNORECASE | re.DOTALL
        )
        saturday_pattern = re.compile(
            r'##\s+Saturday\s+Programming(.*?)(?=##\s+\w+\s+Programming|$)',
            re.IGNORECASE | re.DOTALL
        )
        sunday_pattern = re.compile(
            r'##\s+Sunday\s+Programming(.*?)(?=##\s+\w+\s+Programming|$)',
            re.IGNORECASE | re.DOTALL
        )

        # Parse weekday
        weekday_match = weekday_pattern.search(content)
        if weekday_match:
            dayparts = self._parse_dayparts(weekday_match.group(2), ScheduleType.WEEKDAY)
            structures.append(ProgrammingStructure(
                schedule_type=ScheduleType.WEEKDAY,
                dayparts=dayparts
            ))

        # Parse Saturday
        saturday_match = saturday_pattern.search(content)
        if saturday_match:
            dayparts = self._parse_dayparts(saturday_match.group(1), ScheduleType.SATURDAY)
            structures.append(ProgrammingStructure(
                schedule_type=ScheduleType.SATURDAY,
                dayparts=dayparts
            ))

        # Parse Sunday
        sunday_match = sunday_pattern.search(content)
        if sunday_match:
            dayparts = self._parse_dayparts(sunday_match.group(1), ScheduleType.SUNDAY)
            structures.append(ProgrammingStructure(
                schedule_type=ScheduleType.SUNDAY,
                dayparts=dayparts
            ))

        return structures

    def _parse_dayparts(self, section: str, schedule_type: ScheduleType) -> List[DaypartSpecification]:
        """Parse dayparts from a programming structure section."""
        dayparts = []

        # Pattern 1 (Weekday): ### Morning Drive: "Production Call" (6:00 AM - 10:00 AM)
        weekday_pattern = re.compile(
            r'###\s+([^:\n]+):\s*"([^"]+)"\s*\((\d{1,2}:\d{2}\s*[AP]M)\s*-\s*(\d{1,2}:\d{2}\s*[AP]M)(?:\s+[A-Z]+)?.*?\)(.*?)(?=###|\*\*\d+:\d+|$)',
            re.IGNORECASE | re.DOTALL
        )

        # Pattern 2 (Weekend): **6:00-10:00 AM - "Weekend Wake-Up"** or **10:00 AM-2:00 PM - "Saturday Discovery"**
        weekend_pattern = re.compile(
            r'\*\*(\d{1,2}:\d{2})\s*([AP]M)?\s*-\s*(\d{1,2}:\d{2})\s*([AP]M)\s*-\s*"([^"]+)"\*\*(.*?)(?=\*\*\d+:\d+|###|$)',
            re.IGNORECASE | re.DOTALL
        )

        # Try weekday pattern first
        for match in weekday_pattern.finditer(section):
            daypart_type = match.group(1).strip()
            name = match.group(2).strip()
            time_start_str = match.group(3).strip()
            time_end_str = match.group(4).strip()
            daypart_content = match.group(5)

            # Convert to time objects
            time_start = self._parse_time(time_start_str)
            time_end = self._parse_time(time_end_str)

            # Calculate duration
            duration_hours = self._calculate_duration(time_start, time_end)

            # Parse BPM progression
            bpm_progression = self._parse_bpm_progression(daypart_content, time_start)

            # Parse genre mix
            genre_mix = self._parse_genre_mix(daypart_content)

            # Parse era distribution
            era_distribution = self._parse_era_distribution(daypart_content)

            # Parse mood guidelines
            mood_guidelines = self._parse_mood_guidelines(daypart_content)

            # Parse content focus
            content_focus = self._parse_content_focus(daypart_content, name)

            # Parse rotation percentages
            rotation_percentages = self._parse_rotation_percentages(daypart_content)

            # Parse tracks per hour
            tracks_per_hour = self._parse_tracks_per_hour(daypart_content)

            # Parse target demographic
            target_demographic = self._parse_target_demographic(daypart_content, name)

            daypart = DaypartSpecification(
                id=str(uuid.uuid4()),
                name=name,
                schedule_type=schedule_type,
                time_start=time_start,
                time_end=time_end,
                duration_hours=duration_hours,
                target_demographic=target_demographic,
                bpm_progression=bpm_progression,
                genre_mix=genre_mix,
                era_distribution=era_distribution,
                mood_guidelines=mood_guidelines,
                content_focus=content_focus,
                rotation_percentages=rotation_percentages,
                tracks_per_hour=tracks_per_hour
            )

            dayparts.append(daypart)

        # Try weekend pattern for Saturday/Sunday programming
        for match in weekend_pattern.finditer(section):
            time_start_hour = match.group(1).strip()
            start_am_pm = match.group(2)  # Optional - might be None
            time_end_hour = match.group(3).strip()
            end_am_pm = match.group(4).strip()
            name = match.group(5).strip()
            daypart_content = match.group(6)

            # Build full time strings
            # If start time doesn't have AM/PM, use end time's AM/PM
            if start_am_pm:
                time_start_str = f"{time_start_hour} {start_am_pm.strip()}"
            else:
                time_start_str = f"{time_start_hour} {end_am_pm}"
            time_end_str = f"{time_end_hour} {end_am_pm}"

            # Convert to time objects
            time_start = self._parse_time(time_start_str)
            time_end = self._parse_time(time_end_str)

            # Calculate duration
            duration_hours = self._calculate_duration(time_start, time_end)

            # Parse BPM progression
            bpm_progression = self._parse_bpm_progression(daypart_content, time_start)

            # Parse genre mix
            genre_mix = self._parse_genre_mix(daypart_content)

            # Parse era distribution
            era_distribution = self._parse_era_distribution(daypart_content)

            # Parse mood guidelines
            mood_guidelines = self._parse_mood_guidelines(daypart_content)

            # Parse content focus
            content_focus = self._parse_content_focus(daypart_content, name)

            # Parse rotation percentages
            rotation_percentages = self._parse_rotation_percentages(daypart_content)

            # Parse tracks per hour
            tracks_per_hour = self._parse_tracks_per_hour(daypart_content)

            # Parse target demographic
            target_demographic = self._parse_target_demographic(daypart_content, name)

            daypart = DaypartSpecification(
                id=str(uuid.uuid4()),
                name=name,
                schedule_type=schedule_type,
                time_start=time_start,
                time_end=time_end,
                duration_hours=duration_hours,
                target_demographic=target_demographic,
                bpm_progression=bpm_progression,
                genre_mix=genre_mix,
                era_distribution=era_distribution,
                mood_guidelines=mood_guidelines,
                content_focus=content_focus,
                rotation_percentages=rotation_percentages,
                tracks_per_hour=tracks_per_hour
            )

            dayparts.append(daypart)

        return dayparts

    def _parse_time(self, time_str: str) -> time:
        """Parse time string to time object."""
        # Normalize whitespace
        time_str = re.sub(r'\s+', ' ', time_str.strip())
        dt = datetime.strptime(time_str, '%I:%M %p')
        return dt.time()

    def _calculate_duration(self, start: time, end: time) -> float:
        """Calculate duration in hours between two times."""
        start_mins = start.hour * 60 + start.minute
        end_mins = end.hour * 60 + end.minute

        # Handle overnight shows
        if end_mins <= start_mins:
            end_mins += 24 * 60

        return (end_mins - start_mins) / 60.0

    def _parse_bpm_progression(self, content: str, daypart_start: time) -> List[BPMRange]:
        """Parse BPM progression from content."""
        bpm_ranges = []

        # Pattern: - 6:00-7:00 AM: 90-115 BPM
        pattern = re.compile(
            r'-\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})\s*[AP]M:\s*(\d+)\s*-\s*(\d+)\s*BPM',
            re.IGNORECASE
        )

        for match in pattern.finditer(content):
            # Get the AM/PM from the match
            am_pm = 'AM' if 'AM' in match.group(0) else 'PM'

            time_start_str = f"{match.group(1)} {am_pm}"
            time_end_str = f"{match.group(2)} {am_pm}"

            time_start = self._parse_time(time_start_str)
            time_end = self._parse_time(time_end_str)

            bpm_min = int(match.group(3))
            bpm_max = int(match.group(4))

            bpm_ranges.append(BPMRange(
                time_start=time_start,
                time_end=time_end,
                bpm_min=bpm_min,
                bpm_max=bpm_max
            ))

        return bpm_ranges

    def _parse_genre_mix(self, content: str) -> Dict[str, GenreCriteria]:
        """Parse genre mix from content."""
        genre_mix = {}

        # Find Genre Mix section using line-by-line parsing
        lines = content.split('\n')
        in_genre_section = False
        genre_lines = []

        for line in lines:
            # Check if this is the Genre Mix header using simple string matching
            stripped = line.strip()
            if stripped.startswith('*') and 'genre mix' in stripped.lower() and stripped.endswith('*'):
                in_genre_section = True
                continue

            # If we're in the section, collect lines until we hit another section
            if in_genre_section:
                # Stop if we hit another section header
                if stripped.startswith('*') and ':' in stripped and not stripped.startswith('- '):
                    break
                if stripped.startswith('#'):
                    break
                # Collect content lines
                if stripped:
                    genre_lines.append(line)

        # Parse the collected genre lines
        if genre_lines:
            section = '\n'.join(genre_lines)

            # Pattern: - Contemporary Alternative: 25% (with optional description in parens)
            # Skip lines with "minimum" keyword (like "Australian Artists: 30% minimum...")
            for line in genre_lines:
                # Skip lines that are notes about minimums
                if 'minimum' in line.lower():
                    continue

                # Pattern: - Contemporary Alternative: 25%
                match = re.search(r'-\s*([A-Za-z\s/&]+?):\s*(\d+)%', line)
                if match:
                    genre = match.group(1).strip()
                    percentage = int(match.group(2)) / 100.0

                    genre_mix[genre] = GenreCriteria(
                        target_percentage=percentage,
                        tolerance=0.10  # ±10% default
                    )

        return genre_mix

    def _parse_era_distribution(self, content: str) -> Dict[str, EraCriteria]:
        """Parse era distribution from content."""
        era_distribution = {}

        # Find Era Distribution/Mix section using line-by-line parsing
        lines = content.split('\n')
        in_era_section = False
        era_lines = []

        for line in lines:
            # Check if this is the Era Mix/Distribution header using simple string matching
            stripped = line.strip()
            if stripped.startswith('*') and ('era mix' in stripped.lower() or 'era distribution' in stripped.lower()) and stripped.endswith('*'):
                in_era_section = True
                continue

            # If we're in the section, collect lines until we hit another section
            if in_era_section:
                # Stop if we hit another section header
                if stripped.startswith('*') and ':' in stripped and not stripped.startswith('- '):
                    break
                if stripped.startswith('#'):
                    break
                # Collect content lines
                if stripped:
                    era_lines.append(line)

        # Parse the collected era lines
        if era_lines:
            section = '\n'.join(era_lines)

            # Pattern 1: - Current (0-2 years): 40%
            # Pattern 2: - Current (last 2 years): 40%
            # Pattern 3: - Strategic Throwbacks (10-20 years): 5%
            pattern1 = re.compile(r'-\s*([A-Za-z\s]+)\s*\((\d+)-(\d+)\s*years?\):\s*(\d+)%')
            pattern2 = re.compile(r'-\s*([A-Za-z\s]+)\s*\((?:last|past)\s+(\d+)\s*years?\):\s*(\d+)%', re.IGNORECASE)

            # Try pattern 1 (range format: 0-2 years, 10-20 years)
            for match in pattern1.finditer(section):
                era_name = match.group(1).strip()
                min_years_ago = int(match.group(2))
                max_years_ago = int(match.group(3))
                percentage = int(match.group(4)) / 100.0

                # Calculate year ranges
                current_year = datetime.now().year
                max_year = current_year - min_years_ago
                min_year = current_year - max_years_ago

                era_distribution[era_name] = EraCriteria(
                    era_name=era_name,
                    min_year=min_year,
                    max_year=max_year,
                    target_percentage=percentage,
                    tolerance=0.10  # ±10% default
                )

            # Try pattern 2 (last N years format)
            for match in pattern2.finditer(section):
                era_name = match.group(1).strip()
                years_ago = int(match.group(2))
                percentage = int(match.group(3)) / 100.0

                # Calculate year ranges (last N years = 0 to N years ago)
                current_year = datetime.now().year
                max_year = current_year  # current
                min_year = current_year - years_ago

                era_distribution[era_name] = EraCriteria(
                    era_name=era_name,
                    min_year=min_year,
                    max_year=max_year,
                    target_percentage=percentage,
                    tolerance=0.10  # ±10% default
                )

        return era_distribution

    def _parse_mood_guidelines(self, content: str) -> List[str]:
        """Parse mood guidelines from content."""
        moods = []

        # Find Mood section
        section_match = re.search(
            r'\*\*Mood\*\*:(.*?)(?=\n\*\*|\n###|$)',
            content,
            re.IGNORECASE | re.DOTALL
        )

        if section_match:
            section = section_match.group(1).strip()
            moods.append(section)

        return moods

    def _parse_content_focus(self, content: str, name: str) -> str:
        """Parse content focus from content."""
        # Find Content Focus section
        section_match = re.search(
            r'\*\*Content\s+Focus\*\*:(.*?)(?=\n\*\*|\n###|$)',
            content,
            re.IGNORECASE | re.DOTALL
        )

        if section_match:
            return section_match.group(1).strip()

        # Default based on name
        return f"{name} programming content"

    def _parse_rotation_percentages(self, content: str) -> Dict[str, float]:
        """Parse rotation percentages from content."""
        rotation_percentages = {}

        # Find Rotation section
        section_match = re.search(
            r'\*\*Rotation\*\*:(.*?)(?=\n\*\*|\n###|$)',
            content,
            re.IGNORECASE | re.DOTALL
        )

        if section_match:
            section = section_match.group(1)

            # Pattern: - Power: 30%
            pattern = re.compile(r'-\s*([A-Za-z\s]+):\s*(\d+)%')

            for match in pattern.finditer(section):
                category = match.group(1).strip()
                percentage = int(match.group(2)) / 100.0
                rotation_percentages[category] = percentage

        return rotation_percentages

    def _parse_tracks_per_hour(self, content: str) -> Tuple[int, int]:
        """Parse tracks per hour from content."""
        # Pattern: 12-14 tracks per hour
        pattern = re.compile(r'(\d+)\s*-\s*(\d+)\s*tracks?\s*per\s*hour', re.IGNORECASE)
        match = pattern.search(content)

        if match:
            return (int(match.group(1)), int(match.group(2)))

        # Default
        return (12, 14)

    def _parse_target_demographic(self, content: str, name: str) -> str:
        """Parse target demographic from content."""
        # Find Target Demographic section
        section_match = re.search(
            r'\*\*Target\s+Demographic\*\*:(.*?)(?=\n\*\*|\n###|$)',
            content,
            re.IGNORECASE | re.DOTALL
        )

        if section_match:
            return section_match.group(1).strip()

        # Default based on name
        return f"{name} audience"

    def _parse_australian_content(self, content: str) -> float:
        """Parse Australian content minimum from content."""
        # Pattern: Australian Content: 30% minimum or Australian: 30%
        pattern = re.compile(
            r'Australian(?:\s+Content)?:\s*(\d+)%',
            re.IGNORECASE
        )
        match = pattern.search(content)

        if match:
            return int(match.group(1)) / 100.0

        # Default to 30% (station requirement)
        return 0.30

    def _parse_rotation_strategy(self, content: str) -> RotationStrategy:
        """Parse rotation strategy from content."""
        categories = {}

        # Find Rotation Strategy section
        section_match = re.search(
            r'##\s+Rotation\s+Strategy(.*?)(?=##|$)',
            content,
            re.IGNORECASE | re.DOTALL
        )

        if section_match:
            section = section_match.group(1)

            # Pattern: ### Power (30%) - 40-60 spins/week, 4-6 weeks
            pattern = re.compile(
                r'###\s+([A-Za-z]+)\s*\([^)]+\)\s*-\s*(\d+)-(\d+)\s*spins?/week,?\s*(\d+)-(\d+)\s*weeks?',
                re.IGNORECASE
            )

            for match in pattern.finditer(section):
                name = match.group(1)
                spins_per_week = int(match.group(2))  # Use min value
                lifecycle_weeks = int(match.group(4))  # Use min value

                categories[name] = RotationCategory(
                    name=name,
                    spins_per_week=spins_per_week,
                    lifecycle_weeks=lifecycle_weeks
                )

        return RotationStrategy(categories=categories)

    def _parse_content_requirements(self, content: str) -> ContentRequirements:
        """Parse content requirements from content."""
        # Default Australian content requirement
        australian_min = 0.30
        australian_target = 0.35

        # Look for Australian content requirement
        pattern = re.compile(
            r'Australian(?:\s+Content)?:\s*(\d+)(?:-(\d+))?%',
            re.IGNORECASE
        )
        match = pattern.search(content)

        if match:
            australian_min = int(match.group(1)) / 100.0
            if match.group(2):
                australian_target = int(match.group(2)) / 100.0
            else:
                australian_target = australian_min

        return ContentRequirements(
            australian_content_min=australian_min,
            australian_content_target=australian_target
        )

    def _parse_genre_definitions(self, content: str) -> List[GenreDefinition]:
        """Parse genre definitions from content."""
        # This would parse a genre definitions section if it exists
        # For now, return empty list
        return []


# Backward compatibility function
def parse_programming_document(path: Path) -> StationIdentityDocument:
    """Parse programming document from file path (backward compatibility).

    Args:
        path: Path to station-identity.md file

    Returns:
        Parsed StationIdentityDocument instance

    Note:
        This is a convenience function that wraps DocumentParser.load_document()
        for backward compatibility with existing code.
    """
    parser = DocumentParser()
    return parser.load_document(path)
