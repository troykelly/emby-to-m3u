#!/usr/bin/env python3
"""
Fix TrackSelectionCriteria calls in integration tests.

The old model signature had:
- tolerance_bpm, tolerance_genre_percent, tolerance_era_percent

The new model requires:
- energy_flow_requirements: List[str]
- rotation_distribution: Dict[str, float]
- no_repeat_window_hours: float

Also: bpm_ranges should be List[BPMRange], not List[Tuple]
"""

import re
from pathlib import Path

def fix_file(filepath: Path) -> int:
    """Fix TrackSelectionCriteria calls in a file.

    Returns:
        Number of fixes made
    """
    content = filepath.read_text()
    original_content = content

    # Remove old tolerance parameters
    content = re.sub(
        r',?\s*tolerance_bpm\s*=\s*\d+',
        '',
        content
    )
    content = re.sub(
        r',?\s*tolerance_genre_percent\s*=\s*0\.\d+',
        '',
        content
    )
    content = re.sub(
        r',?\s*tolerance_era_percent\s*=\s*0\.\d+',
        '',
        content
    )

    # Fix bpm_ranges from List[Tuple] to proper format
    # Pattern: bpm_ranges=[(min, max)]
    # Replace with: bpm_ranges=[BPMRange(time(0,0), time(23,59), min, max)]
    def replace_bpm_range(match):
        tuple_content = match.group(1)
        # Extract min, max from tuple
        parts = tuple_content.strip('()').split(',')
        if len(parts) == 2:
            bpm_min = parts[0].strip()
            bpm_max = parts[1].strip()
            return f'bpm_ranges=[BPMRange(time(0, 0), time(23, 59), {bpm_min}, {bpm_max})]'
        return match.group(0)

    content = re.sub(
        r'bpm_ranges=\[(\(\d+,\s*\d+\))\]',
        replace_bpm_range,
        content
    )

    # Add required imports if not present
    if 'from datetime import time' not in content and 'BPMRange(time(' in content:
        # Find the imports section
        import_match = re.search(r'(from datetime import [^\n]+)', content)
        if import_match:
            old_import = import_match.group(1)
            if 'time' not in old_import:
                new_import = old_import.rstrip() + ', time'
                content = content.replace(old_import, new_import)

    if 'BPMRange' in content and 'from src.ai_playlist.models import' in content:
        # Add BPMRange to imports
        import_pattern = r'(from src\.ai_playlist\.models import [^\n]+)'
        import_match = re.search(import_pattern, content)
        if import_match and 'BPMRange' not in import_match.group(1):
            old_import = import_match.group(1)
            # Insert BPMRange after the opening (
            new_import = old_import.replace('import (', 'import (\n    BPMRange,')
            content = content.replace(old_import, new_import)

    # Add required parameters to TrackSelectionCriteria
    # Find all TrackSelectionCriteria( calls
    lines = content.split('\n')
    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if 'TrackSelectionCriteria(' in line:
            # Collect full call
            call_lines = [line]
            paren_depth = line.count('(') - line.count(')')
            j = i + 1

            while paren_depth > 0 and j < len(lines):
                call_lines.append(lines[j])
                paren_depth += lines[j].count('(') - lines[j].count(')')
                j += 1

            full_call = '\n'.join(call_lines)

            # Check if missing required params
            needs_energy = 'energy_flow_requirements' not in full_call
            needs_rotation = 'rotation_distribution' not in full_call
            needs_no_repeat = 'no_repeat_window_hours' not in full_call

            if needs_energy or needs_rotation or needs_no_repeat:
                # Find where to insert (before closing paren)
                last_line_idx = len(call_lines) - 1
                close_paren_line = call_lines[last_line_idx]

                # Get indentation from previous parameter line
                indent_line = call_lines[-2] if len(call_lines) > 1 else call_lines[0]
                indent = len(indent_line) - len(indent_line.lstrip())

                # Insert new parameters before closing paren
                new_params = []
                if needs_energy:
                    new_params.append(' ' * indent + 'energy_flow_requirements=["energetic"],')
                if needs_rotation:
                    new_params.append(' ' * indent + 'rotation_distribution={"Power": 1.0},')
                if needs_no_repeat:
                    new_params.append(' ' * indent + 'no_repeat_window_hours=4.0,')

                # Insert before last line
                call_lines = call_lines[:-1] + new_params + [call_lines[-1]]

            new_lines.extend(call_lines)
            i = j
        else:
            new_lines.append(line)
            i += 1

    content = '\n'.join(new_lines)

    if content != original_content:
        filepath.write_text(content)
        return 1
    return 0


def main():
    project_root = Path(__file__).parent.parent
    file_path = project_root / "tests/integration/test_constraint_relaxation.py"

    fixes = fix_file(file_path)
    if fixes:
        print(f"✅ Fixed {file_path.name}")
    else:
        print(f"➖ No changes needed for {file_path.name}")


if __name__ == "__main__":
    main()
