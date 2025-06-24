#!/usr/bin/env bash
set -euo pipefail

# Create output directory
OUTDIR="output/geojson"
mkdir -p "$OUTDIR"

# Test case 1: Edmonton with no buffer
echo "[ ] Downloading Edmonton geojson (no buffer)..."
python scripts/download-geojson.py \
    "Edmonton, AB" \
    --buffer 0 \
    --output "$OUTDIR/edmonton_nobuf.geojson"
echo "[✓] Wrote $OUTDIR/edmonton_nobuf.geojson"

# Test case 2: Edmonton with 1 km buffer
echo "[ ] Downloading Edmonton geojson (1 km buffer)..."
python scripts/download-geojson.py \
    "Edmonton, AB" \
    --buffer 1.0 \
    --output "$OUTDIR/edmonton_buf1km.geojson"
echo "[✓] Wrote $OUTDIR/edmonton_buf1km.geojson"

# Test case 3: Victoria downtown with 0.5 km buffer
echo "[ ] Downloading Victoria geojson (0.5 km buffer)..."
python scripts/download-geojson.py \
    "Victoria, BC" \
    --buffer 0.5 \
    --output "$OUTDIR/victoria_buf0.5km.geojson"
echo "[✓] Wrote $OUTDIR/victoria_buf0.5km.geojson"

# Test case 4: A full address example
echo "[ ] Downloading geojson for 1600 Pennsylvania Ave NW, Washington, DC (2 km buffer)..."
python scripts/download-geojson.py \
    "1600 Pennsylvania Ave NW, Washington, DC" \
    --buffer 2.0 \
    --output "$OUTDIR/whitehouse_buf2km.geojson"
echo "[✓] Wrote $OUTDIR/whitehouse_buf2km.geojson"