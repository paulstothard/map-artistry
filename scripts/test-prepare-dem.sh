#!/usr/bin/env bash
set -euo pipefail

# where to put your clipped DEMs
mkdir -p data/dem

# Loop over every GeoJSON boundary in data/geojson/
for boundary in data/geojson/*.map.geojson; do
    name=$(basename "$boundary" .map.geojson)
    out="data/dem/${name}_dem.tif"

    echo "[ ] Preparing DEM for ${name}..."
    python scripts/prepare-dem.py \
        -b "$boundary" \
        -o "$out"
    echo "[✓] DEM written to ${out}"
done
