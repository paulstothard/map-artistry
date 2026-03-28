#!/usr/bin/env python3
# Copyright (c) 2026 Paul Stothard
# SPDX-License-Identifier: MIT
"""
Smart publish images from output directory to publish directory.
Only copies files that are newer than their destination or don't exist yet.

Usage:
    python scripts/smart-publish-images.py --input output/ --output publish/
    python scripts/smart-publish-images.py --input output/ --output publish/ --pattern "*.png" --force
"""
import argparse
import shutil
from pathlib import Path


def smart_publish_images(
    input_dir: str | Path,
    output_dir: str | Path,
    pattern: str = "*.png",
    force: bool = False,
    verbose: bool = True,
) -> dict[str, int]:
    """
    Copy images from input to output, only if newer or missing.

    Args:
        input_dir: Source directory (can contain subdirectories)
        output_dir: Destination directory (flat structure)
        pattern: Glob pattern for files to copy
        force: If True, copy all files regardless of timestamps
        verbose: Print progress messages

    Returns:
        Dictionary with keys: 'copied', 'updated', 'skipped'
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all matching files recursively
    files = sorted(input_dir.rglob(pattern))

    if not files:
        if verbose:
            print(f"No files matching '{pattern}' found in {input_dir}")
        return

    if verbose:
        print(f"Found {len(files)} files matching '{pattern}'")

    copied = 0
    skipped = 0
    updated = 0

    for src in files:
        # Use just the filename for destination (flatten structure)
        dest = output_dir / src.name

        # Check if we should copy
        should_copy = force

        if not should_copy:
            if not dest.exists():
                should_copy = True
                action = "new"
            else:
                # Compare modification times
                src_mtime = src.stat().st_mtime
                dest_mtime = dest.stat().st_mtime

                if src_mtime > dest_mtime:
                    should_copy = True
                    action = "update"

        if should_copy:
            shutil.copy2(src, dest)  # copy2 preserves metadata
            if action == "new":
                if verbose:
                    print(f"  ✓ {src.name} (new)")
                copied += 1
            else:
                if verbose:
                    print(f"  ✓ {src.name} (updated)")
                updated += 1
        else:
            skipped += 1

    if verbose:
        print(f"\n✓ Published to {output_dir}/")
        print(f"  New: {copied}")
        print(f"  Updated: {updated}")
        print(f"  Skipped (up-to-date): {skipped}")

    return {"copied": copied, "updated": updated, "skipped": skipped}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smart publish images (only copy if newer or missing)"
    )
    parser.add_argument("--input", required=True, help="Input directory")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument(
        "--pattern",
        type=str,
        default="*.png",
        help='File pattern to match (default: "*.png")',
    )
    parser.add_argument(
        "--force", action="store_true", help="Force copy all files (ignore timestamps)"
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress progress messages"
    )

    args = parser.parse_args()

    smart_publish_images(
        args.input,
        args.output,
        pattern=args.pattern,
        force=args.force,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main()
