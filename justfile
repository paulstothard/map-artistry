# ============================================================================
# Map Artistry - Justfile
# ============================================================================
# Generate artistic topographic maps with multiple color schemes
#
# Usage:
#   just build edmonton coral     # Build specific map
#   just edmonton                 # Build all Edmonton schemes
#   just locations                # List available locations
#   just schemes                  # List available schemes
#   just all                      # Build everything
#
# ============================================================================

python := "python"

# Available color schemes (add new schemes here)

schemes := "coral river_runs_red blue-yellow natural lava frozen satellite"

# ============================================================================
# Location Configurations
# ============================================================================
# To add a new location:
# 1. Add variables below following the pattern
# 2. Add a convenience recipe at the bottom
# ============================================================================
# Edmonton

edmonton_place := "Edmonton, Alberta"
edmonton_buffer := "5"
edmonton_width := "24"
edmonton_height := "24"
edmonton_dpi := "600"
edmonton_format := "png"
edmonton_aspect := "1.0"
edmonton_zoom_sat := "10"
edmonton_ocean := ""
edmonton_dem_source := "copernicus"

# Victoria

victoria_place := "Victoria, BC"
victoria_buffer := "55"
victoria_width := "24"
victoria_height := "24"
victoria_dpi := "600"
victoria_format := "png"
victoria_aspect := "1.0"
victoria_zoom_sat := "10"
victoria_ocean := "--with-ocean"
victoria_dem_source := "srtm"

# Vancouver Island

vancouver_island_place := "vancouver-island"
vancouver_island_buffer := "70"
vancouver_island_width := "24"
vancouver_island_height := "24"
vancouver_island_dpi := "600"
vancouver_island_format := "png"
vancouver_island_aspect := "1.0"
vancouver_island_zoom_sat := "10"
vancouver_island_ocean := "--with-ocean"
vancouver_island_dem_source := "srtm"

# ============================================================================
# Main Commands
# ============================================================================

# List available locations
locations:
    @echo "Available locations:"
    @echo "  edmonton          - Edmonton, Alberta"
    @echo "  victoria          - Victoria, BC"
    @echo "  vancouver-island  - Vancouver Island, BC"

# List available color schemes
schemes:
    @echo "Available color schemes:"
    @echo "  coral           - Warm coral/red background with white water"
    @echo "  river_runs_red  - Black background with red water features"
    @echo "  blue-yellow     - Blue background with yellow water features"
    @echo "  natural         - Natural earth tones with green/brown terrain"
    @echo "  lava            - Volcanic lava with red water"
    @echo "  frozen          - Frozen landscape with ice and snow"
    @echo "  satellite       - Satellite imagery with terrain overlay"

# Build all locations and schemes
all:
    @just edmonton
    @just victoria
    @just vancouver-island

# ============================================================================
# Convenience Aliases (one per location)
# ============================================================================

# Build all Edmonton maps
edmonton scheme="all":
    #!/usr/bin/env bash
    set -euo pipefail
    if [ "{{ scheme }}" = "all" ]; then
        for s in {{ schemes }}; do
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "Building edmonton - $s"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            just _build-single edmonton "{{ edmonton_place }}" {{ edmonton_buffer }} {{ edmonton_width }} {{ edmonton_height }} {{ edmonton_dpi }} {{ edmonton_format }} {{ edmonton_aspect }} {{ edmonton_zoom_sat }} "{{ edmonton_ocean }}" {{ edmonton_dem_source }} "$s"
        done
    else
        just _build-single edmonton "{{ edmonton_place }}" {{ edmonton_buffer }} {{ edmonton_width }} {{ edmonton_height }} {{ edmonton_dpi }} {{ edmonton_format }} {{ edmonton_aspect }} {{ edmonton_zoom_sat }} "{{ edmonton_ocean }}" {{ edmonton_dem_source }} "{{ scheme }}"
    fi

# Build all Victoria maps
victoria scheme="all":
    #!/usr/bin/env bash
    set -euo pipefail
    if [ "{{ scheme }}" = "all" ]; then
        for s in {{ schemes }}; do
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "Building victoria - $s"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            just _build-single victoria "{{ victoria_place }}" {{ victoria_buffer }} {{ victoria_width }} {{ victoria_height }} {{ victoria_dpi }} {{ victoria_format }} {{ victoria_aspect }} {{ victoria_zoom_sat }} "{{ victoria_ocean }}" {{ victoria_dem_source }} "$s"
        done
    else
        just _build-single victoria "{{ victoria_place }}" {{ victoria_buffer }} {{ victoria_width }} {{ victoria_height }} {{ victoria_dpi }} {{ victoria_format }} {{ victoria_aspect }} {{ victoria_zoom_sat }} "{{ victoria_ocean }}" {{ victoria_dem_source }} "{{ scheme }}"
    fi

# Build all Vancouver Island maps
vancouver-island scheme="all":
    #!/usr/bin/env bash
    set -euo pipefail
    if [ "{{ scheme }}" = "all" ]; then
        for s in {{ schemes }}; do
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "Building vancouver-island - $s"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            just _build-single vancouver-island "{{ vancouver_island_place }}" {{ vancouver_island_buffer }} {{ vancouver_island_width }} {{ vancouver_island_height }} {{ vancouver_island_dpi }} {{ vancouver_island_format }} {{ vancouver_island_aspect }} {{ vancouver_island_zoom_sat }} "{{ vancouver_island_ocean }}" {{ vancouver_island_dem_source }} "$s"
        done
    else
        just _build-single vancouver-island "{{ vancouver_island_place }}" {{ vancouver_island_buffer }} {{ vancouver_island_width }} {{ vancouver_island_height }} {{ vancouver_island_dpi }} {{ vancouver_island_format }} {{ vancouver_island_aspect }} {{ vancouver_island_zoom_sat }} "{{ vancouver_island_ocean }}" {{ vancouver_island_dem_source }} "{{ scheme }}"
    fi

# ============================================================================
# Internal Build Pipeline
# ============================================================================

# Build a single map
_build-single location place buffer width height dpi format aspect zoom_sat ocean dem_source scheme:
    @just _download-data {{ location }} "{{ place }}" {{ buffer }} {{ aspect }} {{ zoom_sat }} {{ dpi }} "{{ ocean }}" {{ dem_source }}
    @just _generate-config {{ location }} {{ scheme }} "output/{{ location }}-{{ scheme }}"
    @just _apply-overlay "output/{{ location }}-{{ scheme }}" {{ location }} {{ scheme }}
    @just _generate-map {{ location }} "output/{{ location }}-{{ scheme }}" {{ width }} {{ height }} {{ dpi }} {{ format }}

# Download all shared data for a location
_download-data location place buffer aspect zoom_sat dpi ocean dem_source:
    #!/usr/bin/env bash
    set -euo pipefail
    DATA_DIR="downloads/regions/{{ location }}"
    mkdir -p "$DATA_DIR/layers"

    echo "📦 Preparing data for {{ location }}..."

    # 1. Boundary GeoJSON
    if [ ! -f "$DATA_DIR/area.geojson" ]; then
        echo "📍 Downloading boundary for {{ place }}..."
        {{ python }} scripts/download-geojson.py "{{ place }}" \
            --buffer {{ buffer }} \
            --aspect-ratio {{ aspect }} \
            --output "$DATA_DIR/area.geojson"
    else
        echo "✓ Boundary exists"
    fi

    # 2. DEM (Digital Elevation Model)
    if [ ! -f "$DATA_DIR/dem.tif" ]; then
        echo "⛰️  Downloading DEM ({{ dem_source }})..."
        {{ python }} scripts/download-dem.py \
            --boundary "$DATA_DIR/area.geojson" \
            --output "$DATA_DIR/dem.tif" \
            --source {{ dem_source }}
    else
        echo "✓ DEM exists"
    fi

    # 3. OSM Layers
    if ! ls "$DATA_DIR/layers"/*.gpkg 1> /dev/null 2>&1; then
        echo "🗺️  Downloading OSM layers..."
        {{ python }} scripts/download-osm-layers.py \
            --geojson "$DATA_DIR/area.geojson" \
            --output-dir "$DATA_DIR/layers"
    else
        echo "✓ OSM layers exist"
    fi

    # 4. Satellite imagery
    if [ ! -f "$DATA_DIR/satellite.tif" ]; then
        echo "🛰️  Downloading satellite imagery (zoom {{ zoom_sat }})..."
        {{ python }} scripts/download-satellite-image.py \
            --geojson "$DATA_DIR/area.geojson" \
            --output "$DATA_DIR/satellite.tif" \
            --zoom {{ zoom_sat }} \
            --dpi {{ dpi }}
    else
        echo "✓ Satellite imagery exists"
    fi

    # 5. Ocean data
    if [ "{{ ocean }}" = "--with-ocean" ] && [ ! -f "$DATA_DIR/layers/ocean.gpkg" ]; then
        OCEAN_SHP="downloads/ocean-boundaries/World_Seas_IHO_v3.shp"
        if [ -f "$OCEAN_SHP" ]; then
            echo "🌊 Converting ocean data..."
            ogr2ogr -f GPKG -nlt MULTIPOLYGON -nln ocean \
                "$DATA_DIR/layers/ocean.gpkg" "$OCEAN_SHP"
        else
            echo "⚠️  Warning: Ocean shapefile not found at $OCEAN_SHP"
            echo "   Download from https://www.marineregions.org/downloads.php"
        fi
    fi

    echo "✅ Data ready: $DATA_DIR"

# Generate config
_generate-config location scheme output_dir:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p {{ output_dir }}

    DATA_DIR="downloads/regions/{{ location }}"
    echo "⚙️  Generating {{ scheme }} config..."

    # Include satellite if available
    SAT_FLAG=""
    if [ -f "$DATA_DIR/satellite.tif" ]; then
        SAT_FLAG="--satellite $DATA_DIR/satellite.tif"
    fi

    {{ python }} scripts/generate-config.py "$DATA_DIR/layers"/*.gpkg \
        --output {{ output_dir }}/config-base.yaml \
        --geojson "$DATA_DIR/area.geojson" \
        --dem "$DATA_DIR/dem.tif" \
        --scheme {{ scheme }} \
        $SAT_FLAG

# Apply config overlay
_apply-overlay output_dir location scheme:
    #!/usr/bin/env bash
    set -euo pipefail

    OVERLAY="configs/{{ location }}-{{ scheme }}-overlay.yaml"

    if [ -f "$OVERLAY" ]; then
        echo "🔧 Applying overlay: $OVERLAY"
        {{ python }} scripts/merge-config.py \
            {{ output_dir }}/config-base.yaml \
            "$OVERLAY" \
            {{ output_dir }}/config.yaml
    else
        cp {{ output_dir }}/config-base.yaml {{ output_dir }}/config.yaml
    fi

# Generate map
_generate-map location output_dir width height dpi format:
    #!/usr/bin/env bash
    set -euo pipefail

    echo "🎨 Rendering map..."
    {{ python }} scripts/generate-map.py \
        -g "downloads/regions/{{ location }}/area.geojson" \
        {{ output_dir }}/config.yaml \
        --output {{ output_dir }}/map.{{ format }} \
        --width {{ width }} \
        --height {{ height }} \
        --dpi {{ dpi }} \
        --format {{ format }}
    echo "✅ Complete: {{ output_dir }}/map.{{ format }}"

# ============================================================================
# Utilities
# ============================================================================

# Publish maps to publish/ folder
publish:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p publish
    find output -name "map.*" -type f | while read -r mapfile; do
        folder=$(basename $(dirname "$mapfile"))
        extension="${mapfile##*.}"
        cp "$mapfile" "publish/${folder}.${extension}"
    done
    echo "✅ Published to publish/"

# List all recipes
help:
    @just --list
