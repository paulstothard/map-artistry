#!/usr/bin/env python3
# Copyright (c) 2026 Paul Stothard
# SPDX-License-Identifier: MIT
"""
Create a grid montage of images with optional labels.

Usage:
    python scripts/create-image-montage.py --input examples/thumbnails/ --output montage.png --cols 4
    python scripts/create-image-montage.py --input examples/thumbnails/ --output montage.png --cols 4 --add-labels --label-pattern "{scheme}"
"""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math


# Generated map outputs can legitimately exceed Pillow's default pixel limit.
Image.MAX_IMAGE_PIXELS = None


def extract_scheme_from_filename(filename: str) -> str:
    """Extract scheme name from filename like 'banff-ab-coral.png' -> 'coral'"""
    stem = Path(filename).stem
    parts = stem.split("-")
    if len(parts) >= 2:
        return parts[-1]
    return stem


def calculate_optimal_cols(num_images: int) -> int:
    """Calculate optimal number of columns for a grid layout.

    Tries to create a layout that's as square as possible,
    with a preference for wider (landscape) grids.
    """
    if num_images <= 0:
        return 1
    if num_images == 1:
        return 1
    if num_images == 2:
        return 2
    if num_images == 3:
        return 3

    # For 4+, aim for square-ish but prefer landscape
    sqrt = math.sqrt(num_images)
    cols = math.ceil(sqrt)

    # Check if we can reduce cols while keeping reasonable aspect ratio
    rows = math.ceil(num_images / cols)
    if rows >= cols:
        cols = cols + 1

    return cols


def create_montage(
    input_dir: str | Path,
    output_path: str | Path,
    cols: int | str = 4,
    spacing: int = 10,
    background_color: str = "white",
    add_labels: bool = False,
    label_pattern: str = "{scheme}",
    label_position: str = "upper-right",
    label_background: str | None = "white",
    label_text_color: str = "black",
    label_padding: int = 10,
    pattern: str = "*",
) -> None:
    """Create a grid montage from images in input directory."""
    input_dir = Path(input_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Collect images matching pattern (recursively)
    png_images = list(input_dir.rglob(f"{pattern}.png"))
    jpg_images = list(input_dir.rglob(f"{pattern}.jpg"))
    images = sorted(png_images + jpg_images)
    if not images:
        print(f"No images found in {input_dir}")
        return

    print(f"Creating montage from {len(images)} images...")

    # Auto-calculate columns if requested
    if isinstance(cols, str) and cols.lower() == "auto":
        cols = calculate_optimal_cols(len(images))
        print(f"  Auto-calculated columns: {cols}")

    # Load all images and get max dimensions
    loaded_images = []
    max_width = 0
    max_height = 0

    for img_path in images:
        try:
            img = Image.open(img_path)
            if img.mode != "RGB":
                img = img.convert("RGB")
            loaded_images.append((img_path.name, img))
            max_width = max(max_width, img.width)
            max_height = max(max_height, img.height)
        except Exception as e:
            print(f"  ✗ Failed to load {img_path.name}: {e}")

    if not loaded_images:
        print("No images could be loaded")
        return

    # Calculate grid dimensions
    rows = math.ceil(len(loaded_images) / cols)
    montage_width = cols * max_width + (cols + 1) * spacing
    montage_height = rows * max_height + (rows + 1) * spacing

    print(f"  Grid: {cols} cols × {rows} rows")
    print(f"  Cell size: {max_width}×{max_height}px")
    print(f"  Montage size: {montage_width}×{montage_height}px")

    # Create montage canvas
    montage = Image.new("RGB", (montage_width, montage_height), background_color)

    # Place images in grid
    for idx, (filename, img) in enumerate(loaded_images):
        row = idx // cols
        col = idx % cols

        # Calculate position (centered in cell)
        x = col * max_width + (col + 1) * spacing + (max_width - img.width) // 2
        y = row * max_height + (row + 1) * spacing + (max_height - img.height) // 2

        # Add label if requested
        if add_labels:
            draw = ImageDraw.Draw(img)

            # Determine label text
            if "{scheme}" in label_pattern:
                scheme = extract_scheme_from_filename(filename)
                label_text = label_pattern.replace("{scheme}", scheme.upper())
            elif "{filename}" in label_pattern:
                label_text = label_pattern.replace("{filename}", Path(filename).stem)
            else:
                label_text = label_pattern

            # Auto-size font based on image dimensions
            font_size = max(16, int(img.height * 0.04))

            try:
                font = ImageFont.truetype(
                    "/System/Library/Fonts/Helvetica.ttc", font_size
                )
            except:
                try:
                    font = ImageFont.truetype(
                        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                        font_size,
                    )
                except:
                    font = ImageFont.load_default()

            # Get text bounding box
            bbox = draw.textbbox((0, 0), label_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # Calculate label position
            if label_position == "upper-right":
                label_x = img.width - text_width - label_padding * 2
                label_y = label_padding
            elif label_position == "upper-left":
                label_x = label_padding
                label_y = label_padding
            elif label_position == "lower-right":
                label_x = img.width - text_width - label_padding * 2
                label_y = img.height - text_height - label_padding * 2
            elif label_position == "lower-left":
                label_x = label_padding
                label_y = img.height - text_height - label_padding * 2
            else:
                # Default to upper-right
                label_x = img.width - text_width - label_padding * 2
                label_y = label_padding

            # Draw background rectangle
            if label_background:
                bg_rect = [
                    label_x - label_padding // 2,
                    label_y - label_padding // 2,
                    label_x + text_width + label_padding // 2,
                    label_y + text_height + label_padding // 2,
                ]
                draw.rectangle(bg_rect, fill=label_background)

            # Draw text
            draw.text((label_x, label_y), label_text, fill=label_text_color, font=font)

        # Paste image into montage
        montage.paste(img, (x, y))
        print(f"  ✓ {filename}")

    # Save montage
    montage.save(output_path, optimize=True)
    print(f"\n✓ Montage saved to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a grid montage from images with optional labels"
    )
    parser.add_argument("--input", required=True, help="Input directory with images")
    parser.add_argument("--output", required=True, help="Output montage image path")
    parser.add_argument(
        "--cols",
        type=str,
        default="4",
        help='Number of columns or "auto" for optimal layout (default: 4)',
    )
    parser.add_argument(
        "--spacing", type=int, default=10, help="Spacing between images (default: 10px)"
    )
    parser.add_argument(
        "--background",
        type=str,
        default="white",
        help='Background color (default: "white")',
    )
    parser.add_argument(
        "--add-labels", action="store_true", help="Add labels to each image"
    )
    parser.add_argument(
        "--label-pattern",
        type=str,
        default="{scheme}",
        help='Label pattern with {scheme} or {filename} (default: "{scheme}")',
    )
    parser.add_argument(
        "--label-position",
        type=str,
        default="upper-right",
        choices=["upper-right", "upper-left", "lower-right", "lower-left"],
        help="Label position (default: upper-right)",
    )
    parser.add_argument(
        "--label-background",
        type=str,
        default="white",
        help='Label background color (default: "white", use "none" for transparent)',
    )
    parser.add_argument(
        "--label-text-color",
        type=str,
        default="black",
        help='Label text color (default: "black")',
    )
    parser.add_argument(
        "--label-padding",
        type=int,
        default=10,
        help="Padding around label text (default: 10px)",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="*",
        help='Glob pattern to filter images (default: "*" for all images, e.g., "maple-ridge-bc-*")',
    )

    args = parser.parse_args()

    # Handle "none" for transparent background
    label_bg = (
        None if args.label_background.lower() == "none" else args.label_background
    )

    # Handle cols: "auto" or convert to int
    cols_value = args.cols if args.cols.lower() == "auto" else int(args.cols)

    create_montage(
        args.input,
        args.output,
        cols=cols_value,
        spacing=args.spacing,
        background_color=args.background,
        add_labels=args.add_labels,
        label_pattern=args.label_pattern,
        label_position=args.label_position,
        label_background=label_bg,
        label_text_color=args.label_text_color,
        label_padding=args.label_padding,
        pattern=args.pattern,
    )


if __name__ == "__main__":
    main()
