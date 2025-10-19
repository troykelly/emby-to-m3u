#!/usr/bin/env python3
"""
Batch fix test files to match refactored model signatures.

Fixes:
1. PlaylistSpecification: Add target_duration_minutes=240 (4 hours default)
2. TrackSelectionCriteria: bpm_range → bpm_ranges
3. DaypartSpecification: Remove 'day' parameter
4. ValidationResult: Remove 'constraint_satisfaction' parameter
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

def fix_playlist_specification(content: str) -> Tuple[str, int]:
    """Add target_duration_minutes parameter to PlaylistSpecification constructors."""
    count = 0

    # Pattern: PlaylistSpecification(...) without target_duration_minutes
    # Look for cases where we have track_selection_criteria followed by created_at or cost_budget
    pattern = r'(PlaylistSpecification\([^)]*?track_selection_criteria\s*=\s*[^,]+,)(\s*created_at\s*=)'
    replacement = r'\1\n            target_duration_minutes=240,\2'

    new_content, n = re.subn(pattern, replacement, content)
    count += n

    # Also handle cases where cost_budget comes after track_selection_criteria
    pattern2 = r'(PlaylistSpecification\([^)]*?track_selection_criteria\s*=\s*[^,]+,)(\s*cost_budget_allocated\s*=)'
    replacement2 = r'\1\n            target_duration_minutes=240,\2'

    new_content, n = re.subn(pattern2, replacement2, new_content)
    count += n

    return new_content, count

def fix_track_selection_criteria(content: str) -> Tuple[str, int]:
    """Change bpm_range to bpm_ranges in TrackSelectionCriteria."""
    count = 0

    # Simple replacement: bpm_range= to bpm_ranges=
    pattern = r'\bbpm_range\s*='
    replacement = r'bpm_ranges='

    new_content, n = re.subn(pattern, replacement, content)
    count += n

    return new_content, count

def fix_daypart_specification(content: str) -> Tuple[str, int]:
    """Remove 'day' parameter from DaypartSpecification."""
    count = 0

    # Pattern: day=something, (with optional spaces and newlines)
    pattern = r',?\s*day\s*=\s*[^,\)]+,?'

    new_content, n = re.subn(pattern, '', content)
    count += n

    return new_content, count

def fix_validation_result(content: str) -> Tuple[str, int]:
    """Remove constraint_satisfaction parameter from ValidationResult."""
    count = 0

    # Pattern: constraint_satisfaction=something, (with optional spaces and newlines)
    pattern = r',?\s*constraint_satisfaction\s*=\s*[^,\)]+,?'

    new_content, n = re.subn(pattern, '', content)
    count += n

    return new_content, count

def fix_file(filepath: Path) -> Tuple[int, List[str]]:
    """Fix a single test file."""
    try:
        content = filepath.read_text()
        original_content = content

        fixes_applied = []
        total_fixes = 0

        # Apply all fixes
        content, n = fix_playlist_specification(content)
        if n > 0:
            fixes_applied.append(f"PlaylistSpecification: {n} fixes")
            total_fixes += n

        content, n = fix_track_selection_criteria(content)
        if n > 0:
            fixes_applied.append(f"TrackSelectionCriteria: {n} fixes")
            total_fixes += n

        content, n = fix_daypart_specification(content)
        if n > 0:
            fixes_applied.append(f"DaypartSpecification: {n} fixes")
            total_fixes += n

        content, n = fix_validation_result(content)
        if n > 0:
            fixes_applied.append(f"ValidationResult: {n} fixes")
            total_fixes += n

        # Only write if changes were made
        if content != original_content:
            filepath.write_text(content)

        return total_fixes, fixes_applied

    except Exception as e:
        print(f"Error processing {filepath}: {e}", file=sys.stderr)
        return 0, []

def main():
    """Process all test files."""
    test_dirs = [
        Path("/workspaces/emby-to-m3u/tests/unit"),
        Path("/workspaces/emby-to-m3u/tests/integration"),
    ]

    total_files_fixed = 0
    total_fixes = 0

    for test_dir in test_dirs:
        if not test_dir.exists():
            continue

        for test_file in test_dir.rglob("test_*.py"):
            # Skip obsolete tests
            if "obsolete" in str(test_file):
                continue

            fixes, details = fix_file(test_file)
            if fixes > 0:
                total_files_fixed += 1
                total_fixes += fixes
                print(f"✓ {test_file.name}: {', '.join(details)}")

    print(f"\n✅ Fixed {total_fixes} issues in {total_files_fixed} files")

if __name__ == "__main__":
    main()
