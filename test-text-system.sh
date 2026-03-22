#!/usr/bin/env bash
# ============================================================================
# Map Artistry - Text System Test Script
# ============================================================================
#
# This script tests the text positioning system by generating a single map
# for Edmonton with the porcelain_ink scheme at 300 DPI.
#
# Usage:
#   ./test-text-system.sh
#
# Customize text content below to test different layouts and text elements.
# ============================================================================

set -euo pipefail

# Activate virtual environment if available
[ -d "venv" ] && source venv/bin/activate

PYTHON_BIN="python3"
[ -x "venv/bin/python" ] && PYTHON_BIN="venv/bin/python"

# ============================================================================
# Configuration
# ============================================================================

REGION="Edmonton, AB"
SCHEME="porcelain_ink"
WIDTH=24
HEIGHT=24
DPI=300
FORMAT="png"

# Text content - customize these to test the text system
TEXT_TITLE="EDMONTON RIDE"
TEXT_SUBTITLE="15 MARCH 2024"
TEXT_LOCATION="EDMONTON, ALBERTA"
TEXT_STATS=(
  "42.5 KM:DISTANCE"
  "385 M:ELEV GAIN"
  "2 HR 14 MIN:TIME"
)

# ============================================================================
# Derived values
# ============================================================================

LOCATION=$(echo "$REGION" | tr '[:upper:]' '[:lower:]' | sed 's/[, ]/-/g' | sed 's/--*/-/g')
DATA_DIR="downloads/regions/${LOCATION}"
CONFIG_DIR="configs-text-tests"
OUTPUT_DIR="output-text-tests"
CONFIG_FILE="$CONFIG_DIR/${LOCATION}-${SCHEME}-text-test.yaml"
OUTPUT_FILE="$OUTPUT_DIR/${LOCATION}-${SCHEME}-text-test.${FORMAT}"

mkdir -p "$CONFIG_DIR"
mkdir -p "$OUTPUT_DIR"

# ============================================================================
# Pre-flight checks
# ============================================================================

echo ""
echo "🧪 Map Artistry - Text System Test"
echo "===================================="
echo ""
echo "Region:     $REGION"
echo "Scheme:     $SCHEME"
echo "Size:       ${WIDTH}x${HEIGHT} inches @ ${DPI} DPI"
echo "Format:     $FORMAT"
echo ""
echo "Text elements:"
echo "  Title:    $TEXT_TITLE"
echo "  Subtitle: $TEXT_SUBTITLE"
echo "  Location: $TEXT_LOCATION"
echo "  Stats:    ${TEXT_STATS[*]}"
echo ""

# Check if data exists
if [ ! -d "$DATA_DIR" ]; then
  echo "❌ Error: Data directory not found: $DATA_DIR"
  echo ""
  echo "Please generate the Edmonton map first using:"
  echo "  just build \"$REGION\" $SCHEME"
  echo ""
  echo "This will download all necessary data (DEM, layers, satellite)."
  exit 1
fi

if [ ! -f "$DATA_DIR/area.geojson" ]; then
  echo "❌ Error: Boundary file not found: $DATA_DIR/area.geojson"
  exit 1
fi

if [ ! -f "$DATA_DIR/dem.tif" ]; then
  echo "❌ Error: DEM file not found: $DATA_DIR/dem.tif"
  exit 1
fi

if ! ls "$DATA_DIR/layers"/*.gpkg 1>/dev/null 2>&1; then
  echo "❌ Error: No layers found in $DATA_DIR/layers/"
  exit 1
fi

echo "✓ Data directory exists"
echo "✓ All required files present"
echo ""

# ============================================================================
# Generate configuration with text
# ============================================================================

echo "⚙️  Generating configuration with text..."

# Build text stats arguments
STATS_ARGS=()
for stat in "${TEXT_STATS[@]}"; do
  STATS_ARGS+=(--text-stats "$stat")
done

$PYTHON_BIN scripts/generate-config.py \
  "$DATA_DIR/layers"/*.gpkg \
  --geojson "$DATA_DIR/area.geojson" \
  --output "$CONFIG_FILE" \
  --scheme "$SCHEME" \
  --dem "$DATA_DIR/dem.tif" \
  --enable-text \
  --text-title "$TEXT_TITLE" \
  --text-subtitle "$TEXT_SUBTITLE" \
  --text-location "$TEXT_LOCATION" \
  "${STATS_ARGS[@]}"

echo "   ✓ Configuration ready: $CONFIG_FILE"
echo ""

# ============================================================================
# Render map
# ============================================================================

echo "🎨 Rendering map..."

$PYTHON_BIN scripts/generate-map.py \
  "$CONFIG_FILE" \
  --geojson "$DATA_DIR/area.geojson" \
  --output "$OUTPUT_FILE" \
  --format "$FORMAT" \
  -W "$WIDTH" \
  -H "$HEIGHT" \
  --dpi "$DPI"

echo ""
echo "✅ Map complete: $OUTPUT_FILE"
echo ""
echo "📝 Next steps:"
echo "   • Open the map to review text positioning"
echo "   • Edit this script to test different text content"
echo "   • Adjust text position in schemes/porcelain_ink.yaml"
echo "   • Check the generated config: $CONFIG_FILE"
echo ""
