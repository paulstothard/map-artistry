#!/usr/bin/env bash
set -euo pipefail

# Directory to hold downloaded GeoPackage files
OUTDIR="output/layers"
mkdir -p "${OUTDIR}"

echo '{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Polygon","coordinates":[[[-113.49,53.54],[-113.49,53.541],[-113.488,53.541],[-113.488,53.54],[-113.49,53.54]]]},"properties":{}}]}' >"${OUTDIR}/tiny.geojson"

# Helper to assert a file exists
assert_exists() {
    if [[ ! -f "$1" ]]; then
        echo "✗ Expected file $1 not found!"
        exit 1
    else
        echo "✓ Found $1"
    fi
}

echo
echo "=== Test 1: Edmonton bbox (default layers) ==="
python scripts/download-osm-layers.py \
    --place "Edmonton, AB" \
    --output-dir "${OUTDIR}/test1" \
    --layers highway building waterway landuse
echo "Checking files…"
assert_exists "${OUTDIR}/test1/highway.gpkg"
assert_exists "${OUTDIR}/test1/building.gpkg"
assert_exists "${OUTDIR}/test1/waterway.gpkg"
assert_exists "${OUTDIR}/test1/landuse.gpkg"

echo
echo "=== Test 2: Small buffer area, custom layers ==="
python scripts/download-osm-layers.py \
    --place "Downtown Edmonton, AB" \
    --output-dir "${OUTDIR}/test2" \
    --layers water waterway
echo "Checking files…"
assert_exists "${OUTDIR}/test2/water.gpkg"
assert_exists "${OUTDIR}/test2/waterway.gpkg"

echo
echo "=== Test 3: Full address envelope ==="
python scripts/download-osm-layers.py \
    --place "White House, Washington, DC" \
    --output-dir "${OUTDIR}/test3" \
    --layers building landuse
echo "Checking files…"
assert_exists "${OUTDIR}/test3/building.gpkg"
assert_exists "${OUTDIR}/test3/landuse.gpkg"

echo
echo "=== Test 4: Small GeoJSON input ==="
python scripts/download-osm-layers.py \
    --geojson "${OUTDIR}/tiny.geojson" \
    --output-dir "${OUTDIR}/test4" \
    --layers building
echo "Checking files…"
assert_exists "${OUTDIR}/test4/building.gpkg"

echo
echo "All tests passed! 🎉"
