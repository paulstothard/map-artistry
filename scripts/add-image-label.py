#!/usr/bin/env python3
# Copyright (c) 2026 Paul Stothard
# SPDX-License-Identifier: MIT
"""
Add text labels to images with optional white background.

Usage:
    python scripts/add-image-label.py --input output/ --output labeled/ --label-pattern "{scheme}" --position upper-right
    python scripts/add-image-label.py --input output/ --output labeled/ --label "CORAL" --position upper-right --background white
"""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


# Generated map outputs can legitimately exceed Pillow's default pixel limit.
Image.MAX_IMAGE_PIXELS = None


def extract_scheme_from_filename(filename: str) -> str:
    """Extract scheme name from filename like 'banff-ab-coral.png' -> 'coral'"""
    stem = Path(filename).stem
    parts = stem.split("-")
    if len(parts) >= 2:
        return parts[-1]
    return stem


def add_label_to_image(
    image_path: Path,
    output_path: Path,
    label_text: str,
    position: str = "upper-right",
    background_color: str | None = "white",
    text_color: str = "black",
    padding: int = 20,
    font_size: int | None = None,
) -> None:
    """Add a text label to an image with optional background."""
    with Image.open(image_path) as img:
        # Convert to RGB if needed
        if img.mode != "RGB":
            img = img.convert("RGB")

        draw = ImageDraw.Draw(img)

        # Auto-size font based on image dimensions if not specified
        if font_size is None:
            font_size = max(24, int(img.height * 0.025))

        # Try to load a nice font, fall back to default
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except:
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size
                )
            except:
                font = ImageFont.load_default()

        # Get text bounding box
        bbox = draw.textbbox((0, 0), label_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Calculate position
        if position == "upper-right":
            x = img.width - text_width - padding * 2
            y = padding
        elif position == "upper-left":
            x = padding
            y = padding
        elif position == "lower-right":
            x = img.width - text_width - padding * 2
            y = img.height - text_height - padding * 2
        elif position == "lower-left":
            x = padding
            y = img.height - text_height - padding * 2
        else:
            # Default to upper-right
            x = img.width - text_width - padding * 2
            y = padding

        # Draw background rectangle if specified
        if background_color:
            bg_rect = [
                x - padding // 2,
                y - padding // 2,
                x + text_width + padding // 2,
                y + text_height + padding // 2,
            ]
            draw.rectangle(bg_rect, fill=background_color)

        # Draw text
        draw.text((x, y), label_text, fill=text_color, font=font)

        # Save
        img.save(output_path, optimize=True)


def add_labels_to_images(
    input_dir: str | Path,
    output_dir: str | Path,
    label_text: str | None = None,
    label_pattern: str | None = None,
    position: str = "upper-right",
    background_color: str | None = "white",
    text_color: str = "black",
    padding: int = 20,
    font_size: int | None = None,
) -> None:
    """Add labels to all images in input directory."""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    images = list(input_dir.rglob("*.png")) + list(input_dir.rglob("*.jpg"))
    if not images:
        print(f"No images found in {input_dir}")
        return

    for src in sorted(images):
        # Determine label text
        if label_pattern:
            if "{scheme}" in label_pattern:
                scheme = extract_scheme_from_filename(src.name)
                final_label = label_pattern.replace("{scheme}", scheme.upper())
            elif "{filename}" in label_pattern:
                final_label = label_pattern.replace("{filename}", src.stem)
            else:
                final_label = label_pattern
        elif label_text:
            final_label = label_text
        else:
            # Default to scheme name
            final_label = extract_scheme_from_filename(src.name).upper()

        dest = output_dir / src.name

        add_label_to_image(
            src,
            dest,
            final_label,
            position=position,
            background_color=background_color,
            text_color=text_color,
            padding=padding,
            font_size=font_size,
        )

        print(f"  ✓ {src.name} → {final_label}")

    print(f"\n✓ {len(images)} image(s) labeled and saved to {output_dir}/")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add text labels to images with optional background"
    )
    parser.add_argument("--input", required=True, help="Input directory")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--label", type=str, help="Fixed label text for all images")
    parser.add_argument(
        "--label-pattern",
        type=str,
        help='Label pattern with {scheme} or {filename} (e.g., "{scheme}")',
    )
    parser.add_argument(
        "--position",
        type=str,
        default="upper-right",
        choices=["upper-right", "upper-left", "lower-right", "lower-left"],
        help="Label position (default: upper-right)",
    )
    parser.add_argument(
        "--background",
        type=str,
        default="white",
        help='Background color (e.g., "white", "#ffffff", or "none" for transparent)',
    )
    parser.add_argument(
        "--text-color", type=str, default="black", help='Text color (default: "black")'
    )
    parser.add_argument(
        "--padding", type=int, default=20, help="Padding around text (default: 20px)"
    )
    parser.add_argument(
        "--font-size",
        type=int,
        help="Font size in pixels (auto if not specified)",
    )

    args = parser.parse_args()

    # Handle "none" for transparent background
    bg_color = None if args.background.lower() == "none" else args.background

    add_labels_to_images(
        args.input,
        args.output,
        label_text=args.label,
        label_pattern=args.label_pattern,
        position=args.position,
        background_color=bg_color,
        text_color=args.text_color,
        padding=args.padding,
        font_size=args.font_size,
    )


if __name__ == "__main__":
    main()
