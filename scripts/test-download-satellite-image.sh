#!/usr/bin/env bash

set -euo pipefail

OUTDIR="output/satellite"
mkdir -p "${OUTDIR}"

echo "=== Test 1: From place ==="
python3 scripts/download-satellite-image.py \
  --place "Downtown Edmonton, AB" \
  --output "${OUTDIR}/place-test.tif" \
  --zoom 17

echo "✓ Place-based GeoTIFF downloaded."

echo
echo "=== Test 2: From GeoJSON ==="
cat >"${OUTDIR}/test-area.geojson" <<EOF
{
  "type": "FeatureCollection",
  "features": [{
    "type": "Feature",
    "geometry": {
      "type": "Polygon",
      "coordinates": [[
        [-113.49, 53.54],
        [-113.49, 53.541],
        [-113.488, 53.541],
        [-113.488, 53.54],
        [-113.49, 53.54]
      ]]
    },
    "properties": {}
  }]
}
EOF

python3 scripts/download-satellite-image.py \
  --geojson "${OUTDIR}/test-area.geojson" \
  --output "${OUTDIR}/geojson-test.png" \
  --format png \
  --zoom 18

echo "✓ GeoJSON-based PNG downloaded."

echo
echo "All satellite image tests passed. 🎉"
