#!/usr/bin/env python3
"""Add created_at parameter to PlaylistSpecification calls."""

from pathlib import Path
import re

file_path = Path("tests/integration/test_constraint_relaxation.py")
content = file_path.read_text()

lines = content.split('\n')
new_lines = []
i = 0

while i < len(lines):
    line = lines[i]
    new_lines.append(line)

    # Check if this line starts a TrackSelectionCriteria that's inside PlaylistSpecification
    if 'track_selection_criteria=TrackSelectionCriteria(' in line:
        # Find the closing paren for TrackSelectionCriteria
        paren_depth = line.count('(') - line.count(')')
        j = i + 1

        while paren_depth > 0 and j < len(lines):
            new_lines.append(lines[j])
            paren_depth += lines[j].count('(') - lines[j].count(')')
            j += 1

        # Now check if the next line is the closing paren for PlaylistSpecification
        if j < len(lines) and lines[j].strip() == ')':
            # This means we need to add created_at before this closing paren
            indent = ' ' * (len(lines[j]) - len(lines[j].lstrip()))
            new_lines.append(f"{indent}created_at=datetime.now()")

        i = j
    else:
        i += 1

file_path.write_text('\n'.join(new_lines))
print(f"✅ Added created_at parameters")
