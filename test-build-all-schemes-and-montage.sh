#!/usr/bin/env bash
set -euo pipefail

# Test script for build-all-schemes and montage creation
# Generates all 16 color schemes for Maple Ridge, BC and creates a labeled montage

REGION="Maple Ridge, BC"
OUTPUT_DIR="user/output"
MONTAGE_FILE="user/maple-ridge-all-schemes-montage.png"

echo "🎨 Generating all color schemes for ${REGION}..."
just build-all-schemes "${REGION}"

echo ""
echo "🖼️  Creating montage with automatic layout and scheme labels..."
just create-montage "${OUTPUT_DIR}" "${MONTAGE_FILE}" --cols auto --add-labels true --pattern "maple-ridge-bc-*"

echo ""
echo "📤 Publishing montage to examples/full/ (1200px) and examples/thumbnails/ (400px)..."

# Copy montage to temp dir for resizing (resize recipe works on directories)
TEMP_DIR=$(mktemp -d)
trap "rm -rf ${TEMP_DIR}" EXIT

cp "${MONTAGE_FILE}" "${TEMP_DIR}/"

# Create full size (1200px)
mkdir -p examples/full
just resize "${TEMP_DIR}" examples/full --width 1200

# Create thumbnail (400px)
mkdir -p examples/thumbnails
just resize "${TEMP_DIR}" examples/thumbnails --width 400

echo ""
echo "✅ Complete!"
echo "   Maps: ${OUTPUT_DIR}/maple-ridge-bc-*.png"
echo "   Montage: ${MONTAGE_FILE}"
echo "   Published: examples/full/maple-ridge-all-schemes-montage.png"
echo "   Thumbnail: examples/thumbnails/maple-ridge-all-schemes-montage.png"
