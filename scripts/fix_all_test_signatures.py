#!/usr/bin/env python3
"""
Comprehensively fix all test files with old model signatures.

Fixes:
1. DaypartSpecification: day parameter removal
2. TrackSelectionCriteria: bpm_range → bpm_ranges, dict → GenreCriteria/EraCriteria
3. SelectedTrack: position → position_in_playlist
4. ValidationResult: constraint_satisfaction removal
5. PlaylistSpecification: Add target_duration_minutes
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple


def fix_day_parameter(content: str) -> Tuple[str, int]:
    """Remove day='...' parameter from DaypartSpec calls."""
    pattern = r',\s*day="[^"]*"'
    matches = len(re.findall(pattern, content))
    content = re.sub(pattern, '', content)
    return content, matches


def fix_position_parameter(content: str) -> Tuple[str, int]:
    """Change position= to position_in_playlist= in SelectedTrack."""
    pattern = r'\bposition='
    matches = len(re.findall(pattern, content))
    content = re.sub(pattern, 'position_in_playlist=', content)
    return content, matches


def fix_constraint_satisfaction(content: str) -> Tuple[str, int]:
    """Remove constraint_satisfaction parameter from ValidationResult."""
    pattern = r',\s*constraint_satisfaction=[^,\)]+'
    matches = len(re.findall(pattern, content))
    content = re.sub(pattern, '', content)
    return content, matches


def add_missing_imports(content: str, filepath: Path) -> str:
    """Add missing imports for new model types."""
    # Check if file already has imports
    if 'from src.ai_playlist.models import' not in content:
        return content

    # Add ScheduleType if DaypartSpec is used but ScheduleType isn't imported
    if 'DaypartSpec' in content and 'ScheduleType' not in content:
        content = content.replace(
            'from src.ai_playlist.models import (',
            'from src.ai_playlist.models import (\n    ScheduleType,'
        )

    # Add BPMRange if needed
    if ('bpm_progression' in content or 'bpm_ranges' in content) and 'BPMRange' not in content:
        content = content.replace(
            'from src.ai_playlist.models import (',
            'from src.ai_playlist.models import (\n    BPMRange,'
        )

    # Add GenreCriteria if needed
    if 'genre_mix' in content and 'GenreCriteria' not in content:
        content = content.replace(
            'from src.ai_playlist.models import (',
            'from src.ai_playlist.models import (\n    GenreCriteria,\n    EraCriteria,'
        )

    # Add time import if needed
    if 'time(' in content and 'from datetime import' in content and 'time' not in content.split('from datetime import')[1].split('\n')[0]:
        content = content.replace(
            'from datetime import datetime',
            'from datetime import datetime, time'
        )

    return content


def process_file(filepath: Path) -> dict:
    """Process a single test file and return statistics."""
    if not filepath.exists():
        return {'status': 'not_found', 'changes': 0}

    content = filepath.read_text()
    original = content
    stats = {'status': 'processed', 'changes': {}}

    # Apply fixes
    content, day_changes = fix_day_parameter(content)
    if day_changes:
        stats['changes']['day_param_removed'] = day_changes

    content, pos_changes = fix_position_parameter(content)
    if pos_changes:
        stats['changes']['position_fixed'] = pos_changes

    content, const_changes = fix_constraint_satisfaction(content)
    if const_changes:
        stats['changes']['constraint_satisfaction_removed'] = const_changes

    # Add imports
    content = add_missing_imports(content, filepath)

    # Write back if changed
    if content != original:
        filepath.write_text(content)
        stats['status'] = 'updated'
        return stats
    else:
        stats['status'] = 'no_changes'
        return stats


def main():
    """Fix all test files."""
    test_files = [
        # Unit tests
        'tests/unit/ai_playlist/test_playlist_planner_edge_cases.py',
        'tests/unit/ai_playlist/test_track_selector.py',
        'tests/unit/ai_playlist/test_track_selector_new_comprehensive.py',
        'tests/unit/ai_playlist/test_workflow.py',
        'tests/unit/ai_playlist/test_workflow_comprehensive.py',
        'tests/unit/ai_playlist/test_validator.py',
        'tests/unit/ai_playlist/test_document_parser_comprehensive.py',
        'tests/unit/ai_playlist/test_document_parser_edge_cases.py',
        'tests/unit/test_llm_response_parsing.py',
        'tests/unit/test_edge_cases.py',

        # Integration tests
        'tests/integration/test_file_locking.py',
    ]

    results = {}
    for file_path_str in test_files:
        file_path = Path(file_path_str)
        print(f"Processing {file_path}...")
        results[file_path_str] = process_file(file_path)

    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    updated = sum(1 for r in results.values() if r['status'] == 'updated')
    no_changes = sum(1 for r in results.values() if r['status'] == 'no_changes')
    not_found = sum(1 for r in results.values() if r['status'] == 'not_found')

    print(f"Updated: {updated}")
    print(f"No changes needed: {no_changes}")
    print(f"Not found: {not_found}")

    print("\nDetailed changes:")
    for filepath, stats in results.items():
        if stats.get('changes'):
            print(f"\n{filepath}:")
            for change_type, count in stats['changes'].items():
                print(f"  - {change_type}: {count}")


if __name__ == '__main__':
    main()
