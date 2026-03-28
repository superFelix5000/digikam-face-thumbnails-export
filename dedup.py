#!/usr/bin/env python3
"""Remove duplicate images identified by findimagedupes, keeping one per group."""

import sys
import os
import argparse


def parse_line(line):
    """Parse a findimagedupes output line into individual file paths.

    Supports both:
    - Absolute paths that may contain spaces, separated by ' /' (space + '/')
    - Relative paths without spaces, separated by whitespace
    """
    line = line.strip()
    if not line:
        return []

    if " /" in line:
        # Absolute paths case: paths may contain spaces, so split on " /"
        parts = line.split(" /")
        paths = [parts[0]] + ["/" + p for p in parts[1:]]
    else:
        # Relative paths case: filenames are assumed not to contain spaces,
        # so we can safely split on whitespace.
        paths = line.split()

    # Filter out bare directories (entries ending with '/')
    return [p for p in paths if not p.endswith("/")]


def main():
    parser = argparse.ArgumentParser(
        description="Remove duplicate images from findimagedupes output, keeping one per group."
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="findimagedupes output file (default: stdin)",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--keep",
        choices=["first", "last"],
        default="first",
        help="Which duplicate to keep (default: first)",
    )
    args = parser.parse_args()

    total_deleted = 0
    total_errors = 0

    for line_num, line in enumerate(args.input, 1):
        files = parse_line(line)
        if len(files) < 2:
            continue

        if args.keep == "first":
            keep = files[0]
            to_delete = files[1:]
        else:
            keep = files[-1]
            to_delete = files[:-1]

        print(f"Group {line_num}: keeping {os.path.basename(keep)}")

        for f in to_delete:
            if args.dry_run:
                print(f"  Would delete: {f}")
                total_deleted += 1
            else:
                try:
                    os.remove(f)
                    print(f"  Deleted: {f}")
                    total_deleted += 1
                except OSError as e:
                    print(f"  Error deleting {f}: {e}", file=sys.stderr)
                    total_errors += 1

    if args.dry_run:
        print(f"\nDry run complete. Would delete {total_deleted} file(s).")
    else:
        summary = f"\nDeleted {total_deleted} file(s)."
        if total_errors:
            summary += f" ({total_errors} error(s))"
        print(summary)


if __name__ == "__main__":
    main()
