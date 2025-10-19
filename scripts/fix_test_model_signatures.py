#!/usr/bin/env python3
"""
Fix test files to use correct DaypartSpecification and TrackSelectionCriteria signatures.

Replaces old simple constructors with proper model signatures.
"""

import re
from pathlib import Path


OLD_DAYPART_PATTERN = r'''DaypartSpec\(\s*name="([^"]+)",\s*time_range=\([^)]+\),\s*bpm_progression=\{[^}]+\},\s*genre_mix=\{([^}]+)\},\s*era_distribution=\{([^}]+)\},\s*australian_min=([0-9.]+),\s*mood="([^"]+)",\s*tracks_per_hour=(\d+)\s*\)'''


def fix_daypart_spec(content: str) -> str:
    """Replace old DaypartSpec calls with proper DaypartSpecification."""

    # Replace DaypartSpec with DaypartSpecification
    content = content.replace('from src.ai_playlist.models import (',
                             'from src.ai_playlist.models import (\n    ScheduleType,\n    BPMRange,\n    GenreCriteria,\n    EraCriteria,')

    # Add imports at top if not present
    if 'from datetime import' in content and 'time' not in content.split('from datetime import')[1].split('\n')[0]:
        content = content.replace('from datetime import datetime', 'from datetime import datetime, date, time')

    # Replace simple DaypartSpec calls with proper signature
    def replace_daypart(match):
        name = match.group(1)
        # Extract genre values - just use first one for simplicity
        australian_min = float(match.group(4))
        mood = match.group(5)
        tracks_per_hour = int(match.group(6))

        return f'''DaypartSpecification(
            id="test-daypart-001",
            name="{name}",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time(6, 0),
            time_end=time(10, 0),
            duration_hours=4.0,
            target_demographic="Test audience",
            bpm_progression=[BPMRange(time(6, 0), time(10, 0), 90, 130)],
            genre_mix={{"Rock": 0.50, "Electronic": 0.30, "Pop": 0.20}},
            era_distribution={{"Current (0-2 years)": 0.60, "Recent (2-5 years)": 0.40}},
            mood_guidelines=["{mood}", "energetic"],
            content_focus="Test programming",
            rotation_percentages={{"Power": 0.30, "Medium": 0.40, "Light": 0.30}},
            tracks_per_hour=({tracks_per_hour}, {tracks_per_hour}),
        )'''

    content = re.sub(OLD_DAYPART_PATTERN, replace_daypart, content, flags=re.DOTALL)

    return content


def fix_track_criteria(content: str) -> str:
    """Replace old TrackSelectionCriteria calls with proper signature."""

    # Pattern for old criteria
    old_pattern = r'''TrackSelectionCriteria\(\s*bpm_range=\((\d+),\s*(\d+)\),\s*bpm_tolerance=(\d+),\s*genre_mix=\{([^}]+)\},\s*genre_tolerance=([0-9.]+),\s*era_distribution=\{([^}]+)\},\s*era_tolerance=([0-9.]+),\s*australian_min=([0-9.]+),\s*energy_flow="([^"]+)"(?:,\s*excluded_track_ids=\[[^\]]*\])?\s*\)'''

    def replace_criteria(match):
        bpm_min = match.group(1)
        bpm_max = match.group(2)
        australian_min = match.group(8)
        energy_flow = match.group(9)

        return f'''TrackSelectionCriteria(
            bpm_ranges=[BPMRange(time(0, 0), time(23, 59), {bpm_min}, {bpm_max})],
            genre_mix={{
                "Rock": GenreCriteria(target_percentage=0.50, tolerance=0.10),
                "Electronic": GenreCriteria(target_percentage=0.30, tolerance=0.10),
            }},
            era_distribution={{
                "Current": EraCriteria("Current", 2023, 2025, 0.60, 0.10),
                "Recent": EraCriteria("Recent", 2020, 2022, 0.40, 0.10),
            }},
            australian_content_min={australian_min},
            energy_flow_requirements=["{energy_flow}", "energetic"],
            rotation_distribution={{"Power": 0.30, "Medium": 0.40, "Light": 0.30}},
            no_repeat_window_hours=4.0,
        )'''

    content = re.sub(old_pattern, replace_criteria, content, flags=re.DOTALL)

    return content


def process_file(file_path: Path) -> bool:
    """Process a single test file."""
    print(f"Processing {file_path}...")

    content = file_path.read_text()
    original = content

    content = fix_daypart_spec(content)
    content = fix_track_criteria(content)

    if content != original:
        file_path.write_text(content)
        print(f"  ✅ Updated {file_path}")
        return True
    else:
        print(f"  ⏭️  No changes needed")
        return False


def main():
    """Fix all test files with model signature issues."""
    test_files = [
        Path("tests/unit/ai_playlist/test_batch_executor.py"),
        Path("tests/unit/ai_playlist/test_batch_executor_comprehensive.py"),
        Path("tests/unit/ai_playlist/test_azuracast_sync_unit.py"),
        Path("tests/unit/ai_playlist/test_hive_coordinator.py"),
    ]

    updated = 0
    for file_path in test_files:
        if file_path.exists():
            if process_file(file_path):
                updated += 1
        else:
            print(f"⚠️  File not found: {file_path}")

    print(f"\n✅ Updated {updated} files")


if __name__ == "__main__":
    main()
