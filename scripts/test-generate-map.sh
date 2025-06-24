#!/usr/bin/env bash
set -euo pipefail

OUTDIR="output/map"
mkdir -p "$OUTDIR"

# Create output directory
mkdir -p output

# Edmonton maps
echo "[ ] Generating Edmonton map (coral)..."
python scripts/generate-map.py \
    output/config/edmonton_config_coral.yaml \
    -g output/geojson/edmonton.map.geojson \
    -W 36 -H 24 --dpi 600 -f png \
    -o "$OUTDIR/edmonton_map_coral.png"
echo "[✓] Edmonton map (coral) written to $OUTDIR/edmonton_map_coral.png"

echo "[ ] Generating Edmonton map (river_runs_red)..."
python scripts/generate-map.py \
    output/config/edmonton_config_river_runs_red.yaml \
    -g output/geojson/edmonton.map.geojson \
    -W 36 -H 24 --dpi 600 -f png \
    -o "$OUTDIR/edmonton_map_river_runs_red.png"

echo "[✓] Edmonton map (river_runs_red) written to $OUTDIR/edmonton_map_river_runs_red.png"

# Edmonton south maps
echo "[ ] Generating Edmonton south map (coral)..."
python scripts/generate-map.py \
    output/config/edmonton_south_config_coral.yaml \
    -g output/geojson/edmonton-south.map.geojson \
    -W 36 -H 24 --dpi 600 -f png \
    -o "$OUTDIR/edmonton_south_map_coral.png"
echo "[✓] Edmonton south map (coral) written to $OUTDIR/edmonton_south_map_coral.png"

echo "[ ] Generating Edmonton south map (river_runs_red)..."
python scripts/generate-map.py \
    output/config/edmonton_south_config_river_runs_red.yaml \
    -g output/geojson/edmonton-south.map.geojson \
    -W 36 -H 24 --dpi 600 -f png \
    -o "$OUTDIR/edmonton_south_map_river_runs_red.png"
echo "[✓] Edmonton south map (river_runs_red) written to $OUTDIR/edmonton_south_map_river_runs_red.png"

# Victoria maps
echo "[ ] Generating Victoria map (coral)..."
python scripts/generate-map.py \
    output/config/victoria_config_coral.yaml \
    -g output/geojson/victoria.map.geojson \
    -W 24 -H 24 --dpi 600 -f png \
    -o "$OUTDIR/victoria_map_coral.png"
echo "[✓] Victoria map (coral) written to $OUTDIR/victoria_map_coral.png"

echo "[ ] Generating Victoria map (river_runs_red)..."
python scripts/generate-map.py \
    output/config/victoria_config_river_runs_red.yaml \
    -g output/geojson/victoria.map.geojson \
    -W 24 -H 24 --dpi 600 -f png \
    -o "$OUTDIR/victoria_map_river_runs_red.png"
echo "[✓] Victoria map (river_runs_red) written to $OUTDIR/victoria_map_river_runs_red.png"
