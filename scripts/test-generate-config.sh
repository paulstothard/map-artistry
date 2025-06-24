#!/usr/bin/env bash
set -euo pipefail

OUTDIR="output/config"
mkdir -p "$OUTDIR"

# Create output directory
mkdir -p output

# Edmonton: uses Alberta shapefile
echo "[ ] Generating Edmonton config (coral scheme)..."
python scripts/generate-config.py \
    data/shp/alberta-latest-free.shp.zip \
    -g data/geojson/edmonton.map.geojson \
    -o $OUTDIR/edmonton_config_coral.yaml \
    -d data/dem/edmonton_dem.tif \
    -t 50 \
    -s coral
echo "[✓] Edmonton (coral) config written to $OUTDIR/edmonton_config_coral.yaml"

echo "[ ] Generating Edmonton config (river_runs_red scheme)..."
python scripts/generate-config.py \
    data/shp/alberta-latest-free.shp.zip \
    -g data/geojson/edmonton.map.geojson \
    -o $OUTDIR/edmonton_config_river_runs_red.yaml \
    -d data/dem/edmonton_dem.tif \
    -t 50 \
    -s river_runs_red
echo "[✓] Edmonton (river_runs_red) config written to $OUTDIR/edmonton_config_river_runs_red.yaml"

# Edmonton south: uses Alberta shapefile
echo "[ ] Generating Edmonton south config (coral scheme)..."
python scripts/generate-config.py \
    data/shp/alberta-latest-free.shp.zip \
    -g data/geojson/edmonton-south.map.geojson \
    -o $OUTDIR/edmonton_south_config_coral.yaml \
    -d data/dem/edmonton-south_dem.tif \
    -t 50 \
    -s coral
echo "[✓] Edmonton south (coral) config written to $OUTDIR/edmonton_south_config_coral.yaml"

echo "[ ] Generating Edmonton south config (river_runs_red scheme)..."
python scripts/generate-config.py \
    data/shp/alberta-latest-free.shp.zip \
    -g data/geojson/edmonton-south.map.geojson \
    -o $OUTDIR/edmonton_south_config_river_runs_red.yaml \
    -d data/dem/edmonton-south_dem.tif \
    -t 50 \
    -s river_runs_red
echo "[✓] Edmonton south (river_runs_red) config written to $OUTDIR/edmonton_south_config_river_runs_red.yaml"

# Victoria: uses BC, WA, and World Seas shapefiles
echo "[ ] Generating Victoria config (coral scheme)..."
python scripts/generate-config.py \
    data/shp/british-columbia-latest-free.shp.zip \
    data/shp/washington-latest-free.shp.zip \
    data/shp/World_Seas_IHO_v3.zip \
    -g data/geojson/victoria.map.geojson \
    -o $OUTDIR/victoria_config_coral.yaml \
    -d data/dem/victoria_dem.tif \
    -t 50 \
    -s coral
echo "[✓] Victoria (coral) config written to $OUTDIR/victoria_config_coral.yaml"

echo "[ ] Generating Victoria config (river_runs_red scheme)..."
python scripts/generate-config.py \
    data/shp/british-columbia-latest-free.shp.zip \
    data/shp/washington-latest-free.shp.zip \
    data/shp/World_Seas_IHO_v3.zip \
    -g data/geojson/victoria.map.geojson \
    -o $OUTDIR/victoria_config_river_runs_red.yaml \
    -d data/dem/victoria_dem.tif \
    -t 50 \
    -s river_runs_red
echo "[✓] Victoria (river_runs_red) config written to $OUTDIR/victoria_config_river_runs_red.yaml"
