#!/usr/bin/env python3
"""
Resize images for use in README / GitHub.

Usage:
    python scripts/resize-images.py --input publish/ --output examples/ --width 1200
"""
import argparse
from pathlib import Path
from PIL import Image


def resize_images(input_dir, output_dir, max_width):
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    images = list(input_dir.glob("*.png")) + list(input_dir.glob("*.jpg"))
    if not images:
        print(f"No images found in {input_dir}")
        return

    for src in sorted(images):
        img = Image.open(src)
        w, h = img.size
        if w > max_width:
            new_h = int(h * max_width / w)
            img = img.resize((max_width, new_h), Image.LANCZOS)
        dest = output_dir / src.name
        img.save(dest, optimize=True)
        print(f"  {src.name}: {w}x{h} → {img.width}x{img.height}")

    print(f"\n✓ {len(images)} image(s) saved to {output_dir}/")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="publish/", help="Input directory")
    parser.add_argument("--output", default="examples/", help="Output directory")
    parser.add_argument("--width", type=int, default=1200, help="Max width in pixels")
    args = parser.parse_args()
    resize_images(args.input, args.output, args.width)


if __name__ == "__main__":
    main()
