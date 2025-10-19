#!/usr/bin/env python3
import re

# Real test from markdown
test = """*Genre Mix:*
- Contemporary Alternative: 25% (indie rock, modern alternative)
- Electronic/Downtempo: 20% (Bonobo, Four Tet, Jon Hopkins)

*Era Mix:*
- Current (last 2 years): 40%"""

print("Test string:")
print(test)
print("\n" + "="*80)

# The actual pattern from my code
pattern = r'\*+Genre\s+Mix\*+:(.*?)(?=\n\s*\*+[A-Z]|\n\s*###|$)'

print(f"Pattern: {pattern}")
print()

match = re.search(pattern, test, re.IGNORECASE | re.DOTALL)
if match:
    print("✓ MATCHED!")
    print(f"  Full match: {repr(match.group(0)[:50])}...")
    print(f"  Captured group 1: {repr(match.group(1)[:200])}...")
else:
    print("✗ NO MATCH")
    print("\nTrying simpler patterns...")

    # Try without lookahead
    pattern2 = r'\*+Genre\s+Mix\*+:(.*)'
    match2 = re.search(pattern2, test, re.DOTALL)
    if match2:
        print(f"\n✓ Pattern without lookahead matched!")
        print(f"  Captured: {repr(match2.group(1)[:200])}...")

    # Try with simpler lookahead
    pattern3 = r'\*Genre\s+Mix\*:(.*?)(?=\n\n)'
    match3 = re.search(pattern3, test, re.DOTALL)
    if match3:
        print(f"\n✓ Pattern with \\n\\n lookahead matched!")
        print(f"  Captured: {repr(match3.group(1)[:200])}...")
