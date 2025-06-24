#!/usr/bin/env bash
set -euo pipefail

OUTDIR="data/dem"
mkdir -p "$OUTDIR"

# Loop over every GeoJSON boundary in data/geojson/
for boundary in data/geojson/*.map.geojson; do
    name=$(basename "$boundary" .map.geojson)
    out="$OUTDIR/${name}_dem.tif"

    echo "[ ] Preparing DEM for ${name}..."
    python scripts/download-dem.py \
        -b "$boundary" \
        -o "$out"
    echo "[✓] DEM written to ${out}"
done
