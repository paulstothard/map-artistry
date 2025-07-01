#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/test-all.sh "Place Name" BUFFER_KM [step]
#
# Example: ./scripts/test-all.sh "Edmonton, Alberta" 2
# Optional third argument lets you jump to a specific step:
#   "geojson" — Start at GeoJSON generation (default)
#   "dem"     — Start at DEM download
#   "layers"  — Start at vector layer download
#   "satellite" — Start at satellite image download
#   "config"  — Start at config generation
#   "map"     — Start at map drawing

 # Check that at least one argument (area name) is provided
if [[ $# -lt 1 ]]; then
  echo "Usage: ./scripts/test-all.sh \"Place Name\" BUFFER_KM [step]"
  exit 1
fi

AREA_NAME="$1"
BUFFER_KM="${2:-2}" # default buffer if not specified
STEP=${3:-all}
SAFE_NAME=$(echo "$AREA_NAME" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9' | cut -c1-20)

# Set output paths based on area and buffer
set_output_paths() {
  PLACE="$AREA_NAME"
  BUFFER="$BUFFER_KM"
  GEOJSON_BASENAME="$(echo "$PLACE" | tr '[:upper:]' '[:lower:]' | tr -dc '[:alnum:]')_buf${BUFFER}km"
  GEOJSON_PATH="output/geojson/${GEOJSON_BASENAME}.geojson"
  DEM_PATH="output/dem/${GEOJSON_BASENAME}_dem.tif"
  LAYER_DIR="output/layers/testall"
  SATELLITE_PATH="output/satellite/${GEOJSON_BASENAME}.tif"
  CONFIG_PATH="output/config/${GEOJSON_BASENAME}.yaml"
  MAP_PATH="output/map/${GEOJSON_BASENAME}.png"
}

# Step 1: Create GeoJSON
if [[ "$STEP" == "all" || "$STEP" == "geojson" ]]; then
  set_output_paths
  echo "=== Step 1: Create GeoJSON ==="
  mkdir -p output/geojson
  python ./scripts/download-geojson.py "$AREA_NAME" --buffer "$BUFFER_KM" --output "$GEOJSON_PATH"
else
  set_output_paths
fi

# Step 2: Download DEM
if [[ "$STEP" == "all" || "$STEP" == "dem" ]]; then
  set_output_paths
  echo "=== Step 2: Download DEM ==="
  mkdir -p data/dem
  python ./scripts/download-dem.py --boundary "$GEOJSON_PATH" --output "$DEM_PATH"
else
  set_output_paths
fi

# Step 3: Download Vector Layers
if [[ "$STEP" == "all" || "$STEP" == "layers" ]]; then
  set_output_paths
  echo "=== Step 3: Download Vector Layers ==="
  mkdir -p "$LAYER_DIR"
  python ./scripts/download-osm-layers.py --geojson "$GEOJSON_PATH" --output-dir "$LAYER_DIR"
fi

# Step 4: Download Satellite Image
if [[ "$STEP" == "all" || "$STEP" == "satellite" ]]; then
  set_output_paths
  echo "=== Step 4: Download Satellite Image ==="
  mkdir -p output/satellite
  python scripts/download-satellite-image.py \
    --geojson "$GEOJSON_PATH" \
    --output "$SATELLITE_PATH" \
    --zoom 14
else
  set_output_paths
fi

# Step 5: Generate Config
if [[ "$STEP" == "all" || "$STEP" == "config" ]]; then
  set_output_paths
  echo "=== Step 5: Generate Config ==="
  mkdir -p output/config
  python ./scripts/generate-config.py "$LAYER_DIR"/*.gpkg --output "$CONFIG_PATH" --geojson "$GEOJSON_PATH" --satellite "$SATELLITE_PATH" --dem "$DEM_PATH"
else
  set_output_paths
fi

# Step 6: Generate Map
if [[ "$STEP" == "all" || "$STEP" == "map" ]]; then
  set_output_paths
  echo "=== Step 6: Generate Map ==="
  set_output_paths
  mkdir -p output/map
  python3 scripts/generate-map.py \
    -g "$GEOJSON_PATH" \
    "$CONFIG_PATH" \
    --output "$MAP_PATH"
fi
