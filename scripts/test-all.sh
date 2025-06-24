#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./scripts/test-all.sh "Place Name" [buffer_km]
# Example:
#   ./scripts/test-all.sh "Edmonton, Alberta" 2
#
# This script:
#   1. Creates a buffered GeoJSON boundary from a place name.
#   2. Downloads elevation (DEM), shapefiles, and satellite image for the area.
#   3. Generates a YAML config referencing the satellite and shapefiles.
#   4. Renders a final map using all data layers.

AREA_NAME="$1"
BUFFER_KM="${2:-2}"  # default buffer if not specified
SAFE_NAME=$(echo "$AREA_NAME" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9' | cut -c1-20)

echo "=== Step 1: Create GeoJSON ==="
OUT_GEOJSON="output/geojson/${SAFE_NAME}_buf${BUFFER_KM}km.geojson"
mkdir -p output/geojson
python ./scripts/download-geojson.py --place "$AREA_NAME" --buffer "${BUFFER_KM}km" --output "$OUT_GEOJSON"

echo "=== Step 2: Download DEM ==="
mkdir -p data/dem
DEM_OUT="data/dem/${SAFE_NAME}_dem.tif"
python ./scripts/download-dem.py --geojson "$OUT_GEOJSON" --output "$DEM_OUT"

echo "=== Step 3: Download Shapefiles ==="
mkdir -p output/shp/testall
python ./scripts/download-shapefiles.py "$OUT_GEOJSON" --output-dir output/shp/testall

echo "=== Step 4: Download Satellite Image ==="
mkdir -p output/satellite
SAT_OUT="output/satellite/${SAFE_NAME}.tif"
python ./scripts/download-satellite-image.py --geojson "$OUT_GEOJSON" --output "$SAT_OUT"

echo "=== Step 5: Generate Config ==="
mkdir -p output/config
YAML_OUT="output/config/${SAFE_NAME}.yaml"
python ./scripts/generate-config.py output/shp/testall/*.zip --output "$YAML_OUT" --geojson "$OUT_GEOJSON" --satellite "$SAT_OUT"

echo "=== Step 6: Generate Map ==="
mkdir -p output/map
MAP_OUT="output/map/${SAFE_NAME}.png"
python ./scripts/generate-map.py --config "$YAML_OUT" --output "$MAP_OUT"