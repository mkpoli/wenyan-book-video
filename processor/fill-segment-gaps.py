#!/usr/bin/env python3
"""
Fill gaps in segment numbering by renumbering files sequentially.

This script finds all segment files (e.g., 1-15, 1-16, 1-21, 1-22) and renumbers
them sequentially starting from a specified number (e.g., 1-14, 1-15, 1-16, 1-17),
filling any gaps in the numbering.

Works with:
- Segment text files: {chapter}-{segment}.txt
- Audio files: audio-{chapter}-{segment}.mp3
- Female audio files: audio-{chapter}-{segment}-f.mp3
- Transcript files: audio-{chapter}-{segment}.txt

Usage:
    uv run fill-segment-gaps.py <chapter> [--start <number>] [--min <number>] [--max <number>]

Examples:
    # Fill gaps in chapter 1, starting from 14
    uv run fill-segment-gaps.py 1 --start 14

    # Fill gaps in chapter 2, starting from 1, only process files 5-20
    uv run fill-segment-gaps.py 2 --start 1 --min 5 --max 20
"""

import argparse
import re
from collections import defaultdict
from pathlib import Path

# Base directory (renderer/public from processor directory)
BASE_DIR = Path(__file__).parent.parent / "renderer" / "public"


def extract_number_from_filename(filename: str, pattern_prefix: str):
    """Extract the segment number from a filename."""
    # Match pattern like "1-15" or "audio-1-15" or "audio-1-15-f"
    match = re.search(rf"{re.escape(pattern_prefix)}(\d+)", filename)
    if match:
        return int(match.group(1))
    return None


def find_files_to_rename(
    base_dir: Path,
    pattern_prefix: str,
    min_number: int,
    max_number: int,
    exclude_patterns=None,
):
    """Find all files matching the pattern and organize by directory."""
    if exclude_patterns is None:
        exclude_patterns = []

    files_by_dir = defaultdict(list)
    processed_files = set()  # Track files we've already found to avoid duplicates

    # Search recursively for files matching the pattern
    for old_num in range(min_number, max_number + 1):
        old_pattern = f"{pattern_prefix}{old_num}"
        for file_path in base_dir.rglob(f"*{old_pattern}*"):
            if file_path.is_file():
                # Skip if we've already processed this file
                if file_path in processed_files:
                    continue

                # Skip if file matches any exclude pattern
                skip = False
                for exclude in exclude_patterns:
                    if exclude in file_path.name:
                        skip = True
                        break
                if skip:
                    continue

                # Verify this file actually matches our number pattern
                num = extract_number_from_filename(file_path.name, pattern_prefix)
                if num == old_num:
                    files_by_dir[file_path.parent].append((file_path, old_num))
                    processed_files.add(file_path)

    return files_by_dir


def rename_files_safely_in_dir(
    directory: Path, files_to_rename: list, pattern_prefix: str, start_number: int
):
    """Safely rename files using temporary names, filling gaps sequentially."""
    if not files_to_rename:
        return 0

    renamed_count = 0
    temp_renames = []

    # Sort by old_num to process in order
    files_to_rename.sort(key=lambda x: x[1])

    # Phase 1: Rename all files to temporary names
    print(f"  Phase 1: Renaming to temporary names...")
    current_new_num = start_number

    for old_file, old_num in files_to_rename:
        if not old_file.exists():
            print(f"    SKIP: {old_file.name} (does not exist)")
            continue

        # Calculate the new number (sequential, starting from start_number)
        new_num = current_new_num
        current_new_num += 1

        # Rename to temporary name
        old_pattern = f"{pattern_prefix}{old_num}"
        temp_pattern = f"{pattern_prefix}__TEMP__{old_num}"
        temp_name = old_file.name.replace(old_pattern, temp_pattern)
        temp_file = old_file.parent / temp_name

        print(
            f"    {old_file.name} -> {temp_name} (temp, will become {pattern_prefix}{new_num})"
        )
        old_file.rename(temp_file)
        temp_renames.append((temp_file, old_num, new_num))

    # Phase 2: Rename from temporary names to final names
    print(f"  Phase 2: Renaming from temporary to final names...")
    for temp_file, old_num, new_num in temp_renames:
        old_pattern = f"{pattern_prefix}__TEMP__{old_num}"
        new_pattern = f"{pattern_prefix}{new_num}"

        new_name = temp_file.name.replace(old_pattern, new_pattern)
        new_file = temp_file.parent / new_name

        if temp_file.exists():
            print(f"    {temp_file.name} -> {new_name}")
            temp_file.rename(new_file)
            renamed_count += 1

    return renamed_count


def main():
    """Main function to rename segment files to fill gaps."""
    parser = argparse.ArgumentParser(
        description="Fill gaps in segment numbering by renumbering files sequentially."
    )
    parser.add_argument(
        "chapter",
        type=int,
        help="Chapter number (e.g., 1 for chapter 1)",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=14,
        help="Starting number for renumbering (default: 14)",
    )
    parser.add_argument(
        "--min",
        type=int,
        default=15,
        help="Minimum segment number to process (default: 15)",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=36,
        help="Maximum segment number to process (default: 36)",
    )

    args = parser.parse_args()

    chapter = args.chapter
    start_number = args.start
    min_number = args.min
    max_number = args.max

    total_renamed = 0

    # Patterns to search for: (pattern_prefix, exclude_patterns)
    # exclude_patterns: patterns to exclude (e.g., "audio" when searching for "{chapter}-" to avoid matching "audio-{chapter}-{segment}")
    patterns = [
        (
            f"{chapter}-",
            ["audio"],
        ),  # segments: {chapter}-{segment}.txt (exclude files with "audio" in name)
        (
            f"audio-{chapter}-",
            [],
        ),  # audios: audio-{chapter}-{segment}.mp3, etc.
    ]

    all_processed_files = set()  # Track all files we've processed across patterns

    for pattern_prefix, exclude_patterns in patterns:
        print(f"\n{'='*70}")
        print(
            f"Processing pattern: *{pattern_prefix}[{min_number}-{max_number}]* -> starting from {start_number}"
        )
        if exclude_patterns:
            print(f"Excluding files containing: {exclude_patterns}")
        print(f"{'='*70}")

        # Find all files matching this pattern
        files_by_dir = find_files_to_rename(
            BASE_DIR, pattern_prefix, min_number, max_number, exclude_patterns
        )

        if not files_by_dir:
            print(
                f"  No files found matching pattern *{pattern_prefix}[{min_number}-{max_number}]*"
            )
            continue

        # Process each directory
        for directory, files_to_rename in sorted(files_by_dir.items()):
            # Filter out files we've already processed
            files_to_rename = [
                (f, n) for f, n in files_to_rename if f not in all_processed_files
            ]

            if not files_to_rename:
                continue

            rel_dir = directory.relative_to(BASE_DIR)
            print(f"\nProcessing directory: {rel_dir}")
            print(f"  Found {len(files_to_rename)} files to rename")

            # Show what files we found and what they'll become
            file_nums = sorted([num for _, num in files_to_rename])
            target_nums = list(range(start_number, start_number + len(file_nums)))
            print(f"  Files to rename: {file_nums}")
            print(f"  Will become: {target_nums}")

            count = rename_files_safely_in_dir(
                directory, files_to_rename, pattern_prefix, start_number
            )
            total_renamed += count

            # Mark files as processed
            for file_path, _ in files_to_rename:
                all_processed_files.add(file_path)

            print(f"  Successfully renamed {count} files in {rel_dir}")

    print(f"\n{'='*70}")
    print(f"Total files renamed: {total_renamed}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
