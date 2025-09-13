#!/bin/bash

# ==============================================================================
# convert-map-pdf.sh
#
# Description:
#   Converts a single-page PDF map to PNG images at multiple target resolutions.
#   Output PNGs are saved to the same folder as the input file.
#
# Usage:
#   ./convert-map-pdf.sh [options] path/to/map.pdf
#
# Options:
#   -r <dpi>        Set rasterization resolution in DPI (default: 600)
#   -h, --help      Show help message
#
# Example:
#   ./convert-map-pdf.sh -r 300 map.pdf
#
# Dependencies:
#   - pdftoppm (brew install poppler)
#   - magick (brew install imagemagick)
# ==============================================================================

# Default resolution
dpi=600

# Define desired output widths (in pixels)
resolutions=(14400 7200 3840)

# Parse options
while [[ "$1" == -* ]]; do
  case "$1" in
  -r)
    shift
    dpi="$1"
    ;;
  -h | --help)
    echo "Usage: $0 [options] path/to/map.pdf"
    echo ""
    echo "Converts a map PDF into multiple PNGs at different resolutions."
    echo "Output files are saved in the same folder as the input PDF."
    echo ""
    echo "Options:"
    echo "  -r <dpi>        Set rasterization DPI (default: 600)"
    echo "  -h, --help      Show this help message"
    echo ""
    echo "Example:"
    echo "  $0 -r 300 map.pdf"
    echo ""
    exit 0
    ;;
  *)
    echo "❌ Unknown option: $1"
    exit 1
    ;;
  esac
  shift
done

# Input file (should be last argument)
pdf_file="$(realpath "$1")"

if [[ -z "$pdf_file" ]]; then
  echo "❌ Error: No PDF file specified."
  echo "Run with --help for usage."
  exit 1
fi

if [[ ! -f "$pdf_file" ]]; then
  echo "❌ Error: File \"$pdf_file\" not found."
  exit 1
fi

# Get absolute directory and base name
pdf_dir="$(cd "$(dirname "$pdf_file")" && pwd)"
pdf_base="$(basename "$pdf_file" .pdf)"

# Check dependencies
command -v pdftoppm >/dev/null || {
  echo "❌ pdftoppm not found. Install with 'brew install poppler'"
  exit 1
}
command -v magick >/dev/null || {
  echo "❌ magick (ImageMagick) not found. Install with 'brew install imagemagick'"
  exit 1
}

# Convert once to temporary high-resolution PNG
echo "📥 Converting $pdf_file at ${dpi} DPI..."
pdftoppm -png -r "$dpi" "$pdf_file" "${pdf_dir}/${pdf_base}-temp"

temp_png="${pdf_dir}/${pdf_base}-temp-1.png"

if [[ ! -f "$temp_png" ]]; then
  echo "❌ pdftoppm failed to generate expected PNG: \"$temp_png\""
  echo "   Check that the PDF is valid and not empty."
  exit 1
fi

# Loop through resolutions
for width in "${resolutions[@]}"; do
  output_file="${pdf_dir}/${pdf_base}-${width}.png"
  echo "🖼  Creating ${output_file}..."
  magick "$temp_png" -resize "${width}x" "${output_file}"
done

# Cleanup
rm -f "$temp_png"
echo "✅ Done."
