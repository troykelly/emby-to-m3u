#!/usr/bin/env python3
import re

# Test string
test = "*Genre Mix:*\n- Contemporary Alternative: 25%"

print("Test string:", repr(test))
print()

# Pattern 1: Escaped asterisks
pattern1 = r"\*Genre Mix\*:"
print(f"Pattern 1: {pattern1}")
match1 = re.search(pattern1, test)
print(f"Result: {match1}")
print()

# Pattern 2: Double backslash
pattern2 = "\\*Genre Mix\\*:"
print(f"Pattern 2: {pattern2}")
match2 = re.search(pattern2, test)
print(f"Result: {match2}")
print()

# Pattern 3: Using re.escape
escaped = re.escape("*Genre Mix:*")
print(f"Pattern 3 (escaped): {escaped}")
match3 = re.search(escaped, test)
print(f"Result: {match3}")
