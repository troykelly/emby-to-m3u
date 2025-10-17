#!/usr/bin/env python3
import re

test = "*Genre Mix:*"

patterns = [
    (r"\*", "Single escaped asterisk"),
    (r"\*+", "One or more asterisks"),
    (r"\*Genre", "Asterisk + Genre"),
    (r"\*Genre\s+Mix", "With space"),
    (r"\*Genre\s+Mix\*", "With closing asterisk"),
    (r"\*Genre\s+Mix\*:", "Complete pattern"),
]

print("Test string:", repr(test))
print()

for pattern, desc in patterns:
    match = re.search(pattern, test)
    if match:
        print(f"✓ {desc:30} matched: {repr(match.group(0))}")
    else:
        print(f"✗ {desc:30} NO MATCH")
