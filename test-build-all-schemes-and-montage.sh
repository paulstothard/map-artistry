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
echo "✅ Complete!"
echo "   Maps: ${OUTPUT_DIR}/maple-ridge-bc-*.png"
echo "   Montage: ${MONTAGE_FILE}"
