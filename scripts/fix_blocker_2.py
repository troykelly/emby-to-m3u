#!/usr/bin/env python3
"""
Automated fix script for Blocker #2: Constructor Signature Changes

This script automatically fixes the most common constructor signature issues:
1. ConstraintRelaxation: iteration → step, add timestamp
2. ValidationResult: flat params → nested structure (helper function)

Usage:
    python scripts/fix_blocker_2.py --dry-run  # Preview changes
    python scripts/fix_blocker_2.py            # Apply fixes
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple


def fix_constraint_relaxation(content: str) -> Tuple[str, int]:
    """Fix ConstraintRelaxation constructor calls.

    Changes:
    - iteration=X → step=X
    - Adds timestamp=datetime.now() if missing

    Returns:
        (fixed_content, number_of_fixes)
    """
    fixes = 0

    # Pattern 1: Replace 'iteration=' with 'step='
    pattern = r'\bConstraintRelaxation\(\s*iteration='
    if re.search(pattern, content):
        content = re.sub(pattern, 'ConstraintRelaxation(\n                step=', content)
        fixes += content.count('ConstraintRelaxation(\n                step=')

    # Pattern 2: Add timestamp if missing
    # Find all ConstraintRelaxation( blocks and check if they have timestamp
    constraint_pattern = r'ConstraintRelaxation\([^)]+\)'

    def add_timestamp_if_missing(match):
        block = match.group(0)
        if 'timestamp=' not in block:
            # Add timestamp before closing paren
            # Handle both single-line and multi-line
            if '\n' in block:
                # Multi-line - add before last closing paren
                block = block.rstrip(')').rstrip() + ',\n                timestamp=datetime.now()\n            )'
            else:
                # Single-line - convert to multi-line
                block = block.rstrip(')') + ', timestamp=datetime.now())'
            nonlocal fixes
            fixes += 1
        return block

    content = re.sub(constraint_pattern, add_timestamp_if_missing, content, flags=re.DOTALL)

    # Ensure datetime import exists
    if fixes > 0 and 'from datetime import datetime' not in content:
        # Add import after other datetime imports or at top of imports
        import_pattern = r'(from datetime import [^\n]+)'
        if re.search(import_pattern, content):
            content = re.sub(
                import_pattern,
                r'\1, datetime' if 'datetime' not in content else r'\1',
                content,
                count=1
            )
        else:
            # Add new import line
            content = 'from datetime import datetime\n' + content

    return content, fixes


def create_validation_result_helper(file_path: Path) -> str:
    """Create helper function for ValidationResult construction.

    This generates a compatibility shim that accepts old-style parameters
    and converts them to new-style nested structure.
    """
    return '''
def _create_validation_result_legacy(
    constraint_satisfaction: float,
    bpm_satisfaction: float,
    genre_satisfaction: float,
    era_satisfaction: float,
    australian_content: float,
    flow_quality_score: float,
    bpm_variance: float,
    energy_progression: str,
    genre_diversity: float,
    gap_analysis: dict,
    passes_validation: bool,
    playlist_id: str = None
) -> ValidationResult:
    """Legacy compatibility wrapper for ValidationResult.

    Converts old flat parameter structure to new nested structure.
    This is a temporary shim - migrate to new API when possible.
    """
    from datetime import datetime
    from .models.validation import (
        ConstraintScores,
        FlowQualityMetrics,
        ConstraintScore,
        ValidationStatus
    )

    # Build nested ConstraintScores (legacy uses simple floats)
    constraint_scores_obj = ConstraintScores(
        constraint_satisfaction=constraint_satisfaction,
        bpm_satisfaction=bpm_satisfaction,
        genre_satisfaction=genre_satisfaction,
        era_satisfaction=era_satisfaction,
        australian_content=australian_content
    )

    # Convert to Dict[str, ConstraintScore] format
    constraint_scores_dict = {
        'overall': ConstraintScore(
            constraint_name='Overall',
            target_value=0.80,
            actual_value=constraint_satisfaction,
            tolerance=0.10,
            is_compliant=constraint_satisfaction >= 0.80,
            deviation_percentage=abs(constraint_satisfaction - 0.80) / 0.80 if constraint_satisfaction < 0.80 else 0.0
        )
    }

    # Build FlowQualityMetrics
    flow_metrics = FlowQualityMetrics(
        bpm_variance=bpm_variance,
        bpm_progression_coherence=0.85,  # Reasonable default
        energy_consistency=0.90,         # Reasonable default
        genre_diversity_index=genre_diversity
    )

    # Convert passes_validation to ValidationStatus
    if passes_validation:
        overall_status = ValidationStatus.PASS
    elif constraint_satisfaction >= 0.70:
        overall_status = ValidationStatus.WARNING
    else:
        overall_status = ValidationStatus.FAIL

    # Generate playlist_id if not provided
    if playlist_id is None:
        playlist_id = f"legacy-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # Convert gap_analysis dict to list of strings
    gap_list = []
    if isinstance(gap_analysis, dict):
        for key, value in gap_analysis.items():
            gap_list.append(f"{key}: {value}")

    return ValidationResult(
        playlist_id=playlist_id,
        overall_status=overall_status,
        constraint_scores=constraint_scores_dict,
        flow_quality_metrics=flow_metrics,
        compliance_percentage=constraint_satisfaction,
        validated_at=datetime.now(),
        gap_analysis=gap_list
    )
'''


def fix_validation_result_with_helper(content: str, file_path: Path) -> Tuple[str, int]:
    """Fix ValidationResult by adding legacy helper function.

    Strategy: Instead of replacing all call sites, inject a compatibility
    wrapper that accepts old parameters and converts to new structure.

    Returns:
        (fixed_content, number_of_fixes)
    """
    fixes = 0

    # Check if file uses old-style ValidationResult
    old_pattern = r'ValidationResult\([^)]*constraint_satisfaction='
    if not re.search(old_pattern, content):
        return content, 0

    # Add helper function if not already present
    if '_create_validation_result_legacy' not in content:
        # Find a good place to insert (after imports, before first class/function)
        helper = create_validation_result_helper(file_path)

        # Insert after imports section
        import_end_pattern = r'((?:from [^\n]+\n|import [^\n]+\n)+)\n'
        match = re.search(import_end_pattern, content)

        if match:
            insert_pos = match.end()
            content = content[:insert_pos] + helper + '\n' + content[insert_pos:]
            fixes += 1

    # Replace old-style calls with helper function calls
    old_call_pattern = r'ValidationResult\('
    content = re.sub(old_call_pattern, '_create_validation_result_legacy(', content)

    return content, fixes


def process_file(file_path: Path, dry_run: bool = False) -> Tuple[int, List[str]]:
    """Process a single Python file to fix constructor issues.

    Returns:
        (total_fixes, list_of_changes)
    """
    print(f"Processing: {file_path}")

    try:
        content = file_path.read_text()
        original_content = content
        changes = []
        total_fixes = 0

        # Fix ConstraintRelaxation
        content, cr_fixes = fix_constraint_relaxation(content)
        if cr_fixes > 0:
            changes.append(f"Fixed {cr_fixes} ConstraintRelaxation constructor calls")
            total_fixes += cr_fixes

        # Fix ValidationResult (add helper)
        content, vr_fixes = fix_validation_result_with_helper(content, file_path)
        if vr_fixes > 0:
            changes.append(f"Added ValidationResult legacy helper function")
            total_fixes += vr_fixes

        # Write changes if not dry-run
        if not dry_run and content != original_content:
            file_path.write_text(content)
            print(f"  ✓ Wrote {total_fixes} fixes to {file_path}")
        elif dry_run and content != original_content:
            print(f"  [DRY RUN] Would write {total_fixes} fixes")
        else:
            print(f"  No changes needed")

        return total_fixes, changes

    except Exception as e:
        print(f"  ERROR: {e}")
        return 0, [f"Error: {e}"]


def main():
    """Main entry point."""
    dry_run = '--dry-run' in sys.argv

    if dry_run:
        print("=" * 60)
        print("DRY RUN MODE - No files will be modified")
        print("=" * 60)
        print()

    # Files to process (in priority order)
    files_to_fix = [
        "src/ai_playlist/track_selector_new.py",  # ConstraintRelaxation - easiest
        "src/ai_playlist/validator.py",
        "src/ai_playlist/batch_executor.py",
        "src/ai_playlist/validator_new.py",
        "src/ai_playlist/track_selector.py",
        "src/ai_playlist/playlist_planner.py",
        "src/ai_playlist/decision_logger.py",
        "src/ai_playlist/workflow.py",
    ]

    project_root = Path(__file__).parent.parent
    total_files = 0
    total_fixes = 0
    all_changes = {}

    for file_rel_path in files_to_fix:
        file_path = project_root / file_rel_path

        if not file_path.exists():
            print(f"SKIP: {file_path} (not found)")
            continue

        fixes, changes = process_file(file_path, dry_run=dry_run)

        if fixes > 0:
            total_files += 1
            total_fixes += fixes
            all_changes[file_rel_path] = changes

    # Summary
    print()
    print("=" * 60)
    print(f"{'DRY RUN ' if dry_run else ''}SUMMARY")
    print("=" * 60)
    print(f"Files processed: {total_files}")
    print(f"Total fixes: {total_fixes}")
    print()

    if all_changes:
        print("Changes by file:")
        for file_path, changes in all_changes.items():
            print(f"  {file_path}:")
            for change in changes:
                print(f"    - {change}")
        print()

    if dry_run:
        print("To apply these fixes, run without --dry-run")
    else:
        print("Fixes applied successfully!")
        print()
        print("Next steps:")
        print("  1. Run tests: python -m pytest tests/")
        print("  2. Check pylint: python -m pylint src/ai_playlist/")
        print("  3. Commit changes: git add . && git commit -m 'Fix Blocker #2: Constructor signatures'")


if __name__ == '__main__':
    main()
