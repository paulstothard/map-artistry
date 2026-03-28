#!/usr/bin/env python3
# Copyright (c) 2026 Paul Stothard
# SPDX-License-Identifier: MIT
"""
Create a multi-page PDF from images (one image per page).

Usage:
    python scripts/create-pdf-from-images.py --input publish/ --output maps.pdf
    python scripts/create-pdf-from-images.py --input publish/ --output maps.pdf --dpi 150 --page-size letter
"""
import argparse
from pathlib import Path
from PIL import Image


# Generated map outputs can legitimately exceed Pillow's default pixel limit.
Image.MAX_IMAGE_PIXELS = None


# Common page sizes in inches (width, height)
PAGE_SIZES = {
    "letter": (8.5, 11),
    "legal": (8.5, 14),
    "tabloid": (11, 17),
    "a4": (8.27, 11.69),
    "a3": (11.69, 16.54),
}


def create_pdf_from_images(
    input_dir: str | Path,
    output_path: str | Path,
    dpi: int = 150,
    page_size: str | tuple[float, float] = "letter",
    fit_mode: str = "contain",
    margin_inches: float = 0.5,
) -> None:
    """
    Create a multi-page PDF from images in input directory.

    Args:
        input_dir: Directory containing images
        output_path: Output PDF path
        dpi: Resolution for PDF rendering (150-300 recommended)
        page_size: Page size name or tuple (width, height) in inches
        fit_mode: How to fit images - "contain" (fit within margins), "fill" (fill page), "actual" (original size)
        margin_inches: Margin size in inches when using "contain" mode
    """
    input_dir = Path(input_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Collect all images (recursively)
    images = sorted(list(input_dir.rglob("*.png")) + list(input_dir.rglob("*.jpg")))
    if not images:
        print(f"No images found in {input_dir}")
        return

    print(f"Creating PDF from {len(images)} images...")

    # Get page dimensions in pixels
    if isinstance(page_size, str):
        if page_size.lower() in PAGE_SIZES:
            page_w_in, page_h_in = PAGE_SIZES[page_size.lower()]
        else:
            print(f"Unknown page size '{page_size}', using letter")
            page_w_in, page_h_in = PAGE_SIZES["letter"]
    else:
        page_w_in, page_h_in = page_size

    page_w_px = int(page_w_in * dpi)
    page_h_px = int(page_h_in * dpi)

    print(f"  Page size: {page_size} ({page_w_in}×{page_h_in} in)")
    print(f"  Resolution: {dpi} DPI")
    print(f"  Page dimensions: {page_w_px}×{page_h_px} px")
    print(f"  Fit mode: {fit_mode}")

    # Prepare pages
    pdf_pages = []

    for idx, img_path in enumerate(images):
        try:
            # Load image
            img = Image.open(img_path)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            # Create blank page
            page = Image.new("RGB", (page_w_px, page_h_px), "white")

            if fit_mode == "actual":
                # Place image at actual size, centered
                x = (page_w_px - img.width) // 2
                y = (page_h_px - img.height) // 2
                page.paste(img, (x, y))
            elif fit_mode == "fill":
                # Resize to fill page (may crop)
                img_ratio = img.width / img.height
                page_ratio = page_w_px / page_h_px

                if img_ratio > page_ratio:
                    # Image is wider - fit to height
                    new_height = page_h_px
                    new_width = int(img.width * (new_height / img.height))
                else:
                    # Image is taller - fit to width
                    new_width = page_w_px
                    new_height = int(img.height * (new_width / img.width))

                resized = img.resize((new_width, new_height), Image.LANCZOS)
                x = (page_w_px - new_width) // 2
                y = (page_h_px - new_height) // 2
                page.paste(resized, (x, y))
            else:  # fit_mode == "contain" (default)
                # Resize to fit within margins
                margin_px = int(margin_inches * dpi)
                available_w = page_w_px - 2 * margin_px
                available_h = page_h_px - 2 * margin_px

                # Calculate scaling to fit within available space
                scale_w = available_w / img.width
                scale_h = available_h / img.height
                scale = min(scale_w, scale_h)

                new_width = int(img.width * scale)
                new_height = int(img.height * scale)

                resized = img.resize((new_width, new_height), Image.LANCZOS)
                x = (page_w_px - new_width) // 2
                y = (page_h_px - new_height) // 2
                page.paste(resized, (x, y))

            pdf_pages.append(page)
            print(f"  ✓ {img_path.name} ({img.width}×{img.height}px)")

        except Exception as e:
            print(f"  ✗ Failed to process {img_path.name}: {e}")

    if not pdf_pages:
        print("No images could be processed")
        return

    # Save as PDF
    print(f"\nSaving PDF...")
    pdf_pages[0].save(
        output_path,
        save_all=True,
        append_images=pdf_pages[1:],
        resolution=dpi,
        optimize=False,
    )

    # Get file size
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"✓ PDF saved to {output_path} ({size_mb:.1f} MB, {len(pdf_pages)} pages)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a multi-page PDF from images (one image per page)"
    )
    parser.add_argument("--input", required=True, help="Input directory with images")
    parser.add_argument("--output", required=True, help="Output PDF path")
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="Resolution in DPI (150-300 recommended, default: 150)",
    )
    parser.add_argument(
        "--page-size",
        type=str,
        default="letter",
        choices=list(PAGE_SIZES.keys()),
        help='Page size (default: "letter")',
    )
    parser.add_argument(
        "--fit-mode",
        type=str,
        default="contain",
        choices=["contain", "fill", "actual"],
        help='How to fit images: "contain" (fit within margins), "fill" (fill page), "actual" (original size)',
    )
    parser.add_argument(
        "--margin",
        type=float,
        default=0.5,
        help='Margin size in inches when using "contain" mode (default: 0.5)',
    )

    args = parser.parse_args()

    create_pdf_from_images(
        args.input,
        args.output,
        dpi=args.dpi,
        page_size=args.page_size,
        fit_mode=args.fit_mode,
        margin_inches=args.margin,
    )


if __name__ == "__main__":
    main()
