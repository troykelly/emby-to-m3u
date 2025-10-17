#!/usr/bin/env python3
"""
Fix PlaylistSpecification instantiations in test files.

Adds target_duration_minutes=240 parameter to all PlaylistSpecification() calls
that are missing it.
"""

import re
import sys
from pathlib import Path

# Files to fix
FILES_TO_FIX = [
    "tests/integration/test_constraint_relaxation.py",
    "tests/integration/test_tool_calling.py",
    "tests/unit/ai_playlist/test_models_validation_comprehensive.py",
    "tests/unit/ai_playlist/test_openai_client_comprehensive.py",
    "tests/unit/ai_playlist/test_track_selector_new_comprehensive.py",
    "tests/unit/test_llm_response_parsing.py",
]

def fix_file(filepath: Path) -> tuple[int, str]:
    """Fix PlaylistSpecification calls in a file.

    Returns:
        Tuple of (fixes_made, status_message)
    """
    content = filepath.read_text()
    original_content = content

    # Pattern to match PlaylistSpecification( with parameters until closing )
    # We need to find calls that don't have target_duration_minutes

    fixes = 0
    lines = content.split('\n')
    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if this line starts a PlaylistSpecification call
        if 'PlaylistSpecification(' in line and 'target_duration_minutes' not in line:
            # Collect the full call (might span multiple lines)
            call_lines = [line]
            paren_depth = line.count('(') - line.count(')')
            j = i + 1

            while paren_depth > 0 and j < len(lines):
                call_lines.append(lines[j])
                paren_depth += lines[j].count('(') - lines[j].count(')')
                j += 1

            full_call = '\n'.join(call_lines)

            # Check if target_duration_minutes is present in full call
            if 'target_duration_minutes' not in full_call:
                # Find where to insert target_duration_minutes
                # Insert after generation_date line
                for k, call_line in enumerate(call_lines):
                    if 'generation_date=' in call_line:
                        # Get the indentation from the next line
                        if k + 1 < len(call_lines):
                            next_line = call_lines[k + 1]
                            indent = len(next_line) - len(next_line.lstrip())
                            insert_line = ' ' * indent + 'target_duration_minutes=240,'
                            call_lines.insert(k + 1, insert_line)
                            fixes += 1
                            break

                new_lines.extend(call_lines)
                i = j
            else:
                new_lines.append(line)
                i += 1
        else:
            new_lines.append(line)
            i += 1

    new_content = '\n'.join(new_lines)

    if new_content != original_content:
        filepath.write_text(new_content)
        return fixes, f"Fixed {fixes} PlaylistSpecification calls"
    else:
        return 0, "No changes needed"


def main():
    project_root = Path(__file__).parent.parent
    total_fixes = 0

    for file_path in FILES_TO_FIX:
        full_path = project_root / file_path

        if not full_path.exists():
            print(f"⚠️  {file_path}: File not found")
            continue

        fixes, message = fix_file(full_path)
        total_fixes += fixes
        print(f"{'✅' if fixes > 0 else '➖'} {file_path}: {message}")

    print(f"\n📊 Total fixes: {total_fixes}")
    return 0 if total_fixes > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
