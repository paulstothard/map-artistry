#!/usr/bin/env python3
"""
Resize images for use in README / GitHub.

Usage:
    python scripts/resize-images.py --input publish/ --output examples/ --width 1200
    python scripts/resize-images.py --input publish/ --output examples/ --width 1200 --crop-pattern "*-satellite.*" --crop-bottom 2.5
"""
import argparse
import tempfile
from pathlib import Path
from PIL import Image


# Generated map outputs can legitimately exceed Pillow's default pixel limit.
Image.MAX_IMAGE_PIXELS = None


def resize_images(
    input_dir, output_dir, max_width, crop_pattern=None, crop_bottom_pct=0.0
):
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    images = list(input_dir.glob("*.png")) + list(input_dir.glob("*.jpg"))
    if not images:
        print(f"No images found in {input_dir}")
        return

    # Create temp directory for cropped intermediates if needed
    temp_dir = None
    if crop_pattern and crop_bottom_pct > 0:
        temp_dir = tempfile.mkdtemp(prefix="map_crop_")
        print(f"Using temp directory: {temp_dir}")

    for src in sorted(images):
        with Image.open(src) as source_img:
            w, h = source_img.size

            # Check if this image matches the crop pattern
            should_crop = (
                crop_pattern and crop_bottom_pct > 0 and src.match(crop_pattern)
            )
            if should_crop:
                # Crop equally from all sides to keep center
                crop_pct = crop_bottom_pct
                left_px = int(w * crop_pct / 100)
                right_px = int(w * crop_pct / 100)
                top_px = int(h * crop_pct / 100)
                bottom_px = int(h * crop_pct / 100)

                cropped_img = source_img.crop(
                    (left_px, top_px, w - right_px, h - bottom_px)
                )
                print(
                    f"  {src.name}: cropped {crop_pct}% from all sides ({left_px}px each)"
                )

                # Save intermediate cropped image to temp
                temp_path = Path(temp_dir) / src.name
                cropped_img.save(temp_path)

                # Reopen from temp for resizing
                with Image.open(temp_path) as img_to_resize:
                    w_crop, h_crop = img_to_resize.size
                    if w_crop > max_width:
                        new_h = int(h_crop * max_width / w_crop)
                        img = img_to_resize.resize((max_width, new_h), Image.LANCZOS)
                    else:
                        img = img_to_resize.copy()
                    print(
                        f"  {src.name}: {w}x{h} → {w_crop}x{h_crop} → {img.width}x{img.height}"
                    )
            else:
                # No cropping needed
                if w > max_width:
                    new_h = int(h * max_width / w)
                    img = source_img.resize((max_width, new_h), Image.LANCZOS)
                else:
                    img = source_img.copy()
                print(f"  {src.name}: {w}x{h} → {img.width}x{img.height}")

        dest = output_dir / src.name
        img.save(dest, optimize=True)

    # Cleanup temp directory
    if temp_dir:
        import shutil

        shutil.rmtree(temp_dir)
        print(f"Cleaned up temp directory")

    print(f"\n✓ {len(images)} image(s) saved to {output_dir}/")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="publish/", help="Input directory")
    parser.add_argument("--output", default="examples/", help="Output directory")
    parser.add_argument("--width", type=int, default=1200, help="Max width in pixels")
    parser.add_argument(
        "--crop-pattern",
        type=str,
        default=None,
        help="Glob pattern for files to crop (e.g., '*-satellite.*')",
    )
    parser.add_argument(
        "--crop-bottom",
        type=float,
        default=0.0,
        help="Percentage to crop from bottom of matching files (e.g., 2.5)",
    )
    args = parser.parse_args()
    resize_images(
        args.input, args.output, args.width, args.crop_pattern, args.crop_bottom
    )


if __name__ == "__main__":
    main()
