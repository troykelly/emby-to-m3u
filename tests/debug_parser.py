#!/usr/bin/env python3
"""Debug script to understand what content is passed to genre_mix and era_distribution parsers."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import re

path = Path("/workspaces/emby-to-m3u/station-identity.md")

with open(path, 'r') as f:
    content = f.read()

# Find the first daypart section
daypart_pattern = re.compile(
    r'###\s+([^:\n]+):\s*"([^"]+)"\s*\((\d{1,2}:\d{2}\s*[AP]M)\s*-\s*(\d{1,2}:\d{2}\s*[AP]M)(?:\s+[A-Z]+)?.*?\)(.*?)(?=###|$)',
    re.IGNORECASE | re.DOTALL
)

match = daypart_pattern.search(content)
if match:
    daypart_content = match.group(5)
    print("="*80)
    print("DAYPART CONTENT (first 2000 chars):")
    print("="*80)
    print(daypart_content[:2000])
    print("\n" + "="*80)
    print("TESTING GENRE MIX REGEX:")
    print("="*80)

    # Test genre mix regex (updated)
    section_match = re.search(
        r'\*+Genre\s+Mix\*+:(.*?)(?=\n\s*\*+[A-Z]|\n\s*###|$)',
        daypart_content,
        re.IGNORECASE | re.DOTALL
    )

    if section_match:
        print("FOUND Genre Mix section!")
        print("Content:", section_match.group(1)[:500])
    else:
        print("NOT FOUND - trying different patterns...")

        # Try simpler pattern
        test1 = re.search(r'\*Genre Mix\*:', daypart_content, re.IGNORECASE)
        if test1:
            print("Found '*Genre Mix*:' at position", test1.start())

        test2 = re.search(r'\*\*Genre Mix\*\*:', daypart_content, re.IGNORECASE)
        if test2:
            print("Found '**Genre Mix**:' at position", test2.start())

        # Show what's around "Genre Mix"
        idx = daypart_content.lower().find('genre mix')
        if idx >= 0:
            print(f"\nFound 'genre mix' at index {idx}")
            print("Context (50 chars before and after):")
            print(repr(daypart_content[max(0, idx-50):idx+100]))

    print("\n" + "="*80)
    print("TESTING ERA MIX REGEX:")
    print("="*80)

    # Test era mix regex (updated)
    section_match = re.search(
        r'\*+Era\s+(?:Distribution|Mix)\*+:(.*?)(?=\n\s*\*+[A-Z]|\n\s*###|$)',
        daypart_content,
        re.IGNORECASE | re.DOTALL
    )

    if section_match:
        print("FOUND Era Mix section!")
        print("Content:", section_match.group(1)[:500])
    else:
        print("NOT FOUND - checking for Era Mix in content...")
        idx = daypart_content.lower().find('era mix')
        if idx >= 0:
            print(f"\nFound 'era mix' at index {idx}")
            print("Context (50 chars before and after):")
            print(repr(daypart_content[max(0, idx-50):idx+100]))
else:
    print("Could not find any daypart section!")
