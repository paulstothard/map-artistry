# ============================================================================
# Map Artistry - Dynamic Map Generation
# Copyright (c) 2026 Paul Stothard
# ============================================================================
#
# Usage:
#   just build "Edmonton, AB" coral
#   just build --width 36 --height 24 "Vancouver Island, BC" natural
#   just build --buffer-km 20 "Victoria, BC" natural
#
# Most settings (boundary padding, zoom, DEM source, layer source) are calculated automatically.
# If ocean boundary source data is installed, the build also derives a local ocean
# layer when it overlaps the requested region.
#
# ============================================================================
# Python interpreter (uses venv if available)

python := if path_exists("venv/bin/python") == "true" { "venv/bin/python" } else { "python3" }

# ============================================================================
# Main Commands
# ============================================================================

# Build a map for any region with automatic settings
[arg("height", long="height", help="Map height in inches")]
[arg("width", long="width", help="Map width in inches")]
[arg("buffer_km", long="buffer-km", help="Optional extra distance around the region boundary, in kilometers")]
[arg("format", long="format", help="Output format: png, pdf, svg")]
[arg("dpi", long="dpi", help="Resolution in DPI")]
build region scheme width="24" height="24" dpi="600" format="png" buffer_km="":
    @just _build-map "{{ region }}" "{{ scheme }}" "{{ width }}" "{{ height }}" "{{ dpi }}" "{{ format }}" "{{ buffer_km }}"

# List available color schemes
schemes:
    {{ python }} scripts/generate-config.py --list-schemes

# Show help
help:
    @echo "Map Artistry - Dynamic Map Generation"
    @echo ""
    @echo "Usage:"
    @echo "  just build [--width 24] [--height 24] [--dpi 600] [--format png] [--buffer-km 20] REGION SCHEME"
    @echo ""
    @echo "Examples:"
    @echo '  just build "Edmonton, AB" coral'
    @echo '  just build --width 36 --height 24 "Vancouver Island, BC" natural'
    @echo '  just build --width 36 --height 24 --dpi 600 "Canada" lava'
    @echo '  just build --buffer-km 20 "Victoria, BC" natural'
    @echo ""
    @echo "Parameters:"
    @echo "  --width      Map width in inches (default: 24)"
    @echo "  --height     Map height in inches (default: 24)"
    @echo "  --dpi        Resolution in DPI (default: 600)"
    @echo "  --format     Output format: png, pdf, svg (default: png)"
    @echo "  --buffer-km  Optional extra distance around the region boundary, in kilometers"
    @echo ""
    @echo "Other commands:"
    @echo "  just schemes  - List available color schemes"
    @echo "  just help     - Show this help"
    @echo ""
    @echo "All settings are calculated automatically based on region size:"
    @echo "  • Boundary padding (extra distance added around the region boundary)"
    @echo "  • DEM source (Copernicus, COP90, SRTM, or ETOPO)"
    @echo "  • Satellite zoom level"
    @echo "  • Ocean layer derivation from installed ocean boundaries"
    @echo "  • Layer data source (OSM or Natural Earth)"

# List all recipes
@list:
    just --list

# Publish generated maps to publish/ folder
publish:
    @echo "📤 Publishing maps to publish/ folder..."
    @mkdir -p publish
    @find output -name "*.png" -o -name "*.pdf" | while read f; do \
        bn=$(basename "$f"); \
        cp "$f" "publish/$bn"; \
        echo "  ✓ $bn"; \
    done
    @echo "✅ Published $(find publish -type f | wc -l | tr -d ' ') maps"

# Create resized examples for GitHub README from published maps
publish-examples width="1200" thumbnail_width="400":
    @echo "📸 Creating examples for GitHub README..."
    @echo "  Full size: {{ width }}px → examples/full/"
    @echo "  Thumbnails: {{ thumbnail_width }}px → examples/thumbnails/"
    @echo "  Cropping 2.5% from all sides of all images"
    {{ python }} scripts/resize-images.py \
        --input publish/ \
        --output examples/full/ \
        --width {{ width }} \
        --crop-pattern "*" \
        --crop-bottom 2.5
    {{ python }} scripts/resize-images.py \
        --input publish/ \
        --output examples/thumbnails/ \
        --width {{ thumbnail_width }} \
        --crop-pattern "*" \
        --crop-bottom 2.5
    @echo "✅ Examples ready:"
    @echo "   Full: examples/full/"
    @echo "   Thumbnails: examples/thumbnails/"

# ============================================================================
# Internal Recipes (prefixed with _)
# ============================================================================

# Main build orchestration
_build-map region scheme width height dpi format buffer:
    #!/usr/bin/env bash
    set -euo pipefail

    REGION="{{ region }}"
    SCHEME="{{ scheme }}"
    WIDTH={{ width }}
    HEIGHT={{ height }}
    DPI={{ dpi }}
    FORMAT={{ format }}
    USER_BUFFER="{{ buffer }}"

    # Sanitize region name for filesystem (replace spaces, slashes, etc.)
    LOCATION=$(echo "$REGION" | tr '[:upper:]' '[:lower:]' | sed 's/[, ]/-/g' | sed 's/--*/-/g')
    DATA_DIR="downloads/regions/$LOCATION"
    OUTPUT_DIR="output/${LOCATION}-${SCHEME}"
    CONFIG_DIR="configs"

    echo "🗺️  Building map: $REGION ($SCHEME scheme)"
    echo "   Output: $OUTPUT_DIR"
    echo ""

    mkdir -p "$DATA_DIR/layers"
    mkdir -p "$OUTPUT_DIR"
    mkdir -p "$CONFIG_DIR"

    # ========================================================================
    # Step 1: Determine buffer size (user-supplied or auto-calculated)
    # ========================================================================
    if [ -n "$USER_BUFFER" ]; then
        BUFFER="$USER_BUFFER"
        echo "📍 Step 1: Using user-supplied buffer: ${BUFFER}km"
    else
        echo "📍 Step 1: Analyzing region and calculating settings..."
        ESTIMATE_JSON=$({{ python }} scripts/calculate-area.py --place "$REGION")
        BUFFER=$(echo "$ESTIMATE_JSON" | {{ python }} -c "import sys, json; print(json.load(sys.stdin)['buffer_km'])")
        echo "   Recommended buffer: ${BUFFER}km"
    fi
    echo ""

    # ========================================================================
    # Step 2: Download boundary with calculated buffer
    # ========================================================================
    echo "📍 Step 2: Downloading boundary..."

    # Calculate aspect ratio from width/height
    ASPECT=$({{ python }} -c "print(round(${WIDTH} / ${HEIGHT}, 3))")

    {{ python }} scripts/download-geojson.py "$REGION" \
        --buffer "$BUFFER" \
        --aspect-ratio "$ASPECT" \
        --output "$DATA_DIR/area.geojson"

    {{ python }} scripts/validate-geojson.py "$DATA_DIR/area.geojson"

    echo "   ✓ Boundary saved (aspect ratio: $ASPECT)"
    echo ""

    # ========================================================================
    # Step 3: Calculate strategy from actual buffered area
    # ========================================================================
    echo "🧠 Step 3: Calculating resource strategy..."
    STRATEGY_JSON=$({{ python }} scripts/calculate-area.py "$DATA_DIR/area.geojson")
    AREA_KM2=$(echo "$STRATEGY_JSON" | {{ python }} -c "import sys, json; print(json.load(sys.stdin)['area_km2'])")
    TIER=$(echo "$STRATEGY_JSON" | {{ python }} -c "import sys, json; print(json.load(sys.stdin)['tier'])")
    DEM_SOURCE=$(echo "$STRATEGY_JSON" | {{ python }} -c "import sys, json; print(json.load(sys.stdin)['recommendations']['dem_source'])")
    SAT_ZOOM=$(echo "$STRATEGY_JSON" | {{ python }} -c "import sys, json; print(json.load(sys.stdin)['recommendations']['sat_zoom'])")
    OSM_SOURCE=$(echo "$STRATEGY_JSON" | {{ python }} -c "import sys, json; print(json.load(sys.stdin)['recommendations']['osm_source'])")

    echo "   📊 Area: ${AREA_KM2} km² (tier: ${TIER})"
    echo "   📦 Strategy:"
    echo "      • DEM: ${DEM_SOURCE}"
    echo "      • Satellite zoom: ${SAT_ZOOM}"
    echo "      • Layers: ${OSM_SOURCE}"
    echo ""

    # ========================================================================
    # Step 4: Optional ocean layer prep
    # ========================================================================
    echo "🌊 Step 4: Preparing optional ocean layer..."
    OCEAN_SHP="downloads/ocean-boundaries/World_Seas_IHO_v3.shp"
    if [ -f "$OCEAN_SHP" ]; then
        echo "   ✓ Ocean boundary source available"
    else
        echo "   ℹ️  Ocean boundary source not installed - continuing without ocean layer"
    fi
    echo ""

    # ========================================================================
    # Step 5: Check for cached data or download
    # ========================================================================
    echo "📦 Step 5: Preparing data..."

    # Check if boundary changed (checksum validation)
    CHECKSUM_FILE="$DATA_DIR/.geojson-checksum"
    NEW_CHECKSUM=$(shasum -a 256 "$DATA_DIR/area.geojson" | cut -d' ' -f1)

    if [ -f "$CHECKSUM_FILE" ]; then
        OLD_CHECKSUM=$(cat "$CHECKSUM_FILE")
        if [ "$NEW_CHECKSUM" != "$OLD_CHECKSUM" ]; then
            echo "   ⚠️  Boundary changed - invalidating cached data..."
            rm -f "$DATA_DIR/dem.tif"
            rm -f "$DATA_DIR/satellite.tif"
            rm -f "$DATA_DIR/layers"/*.gpkg
        fi
    fi

    # Update stored checksum
    echo "$NEW_CHECKSUM" > "$CHECKSUM_FILE"

    # Download DEM
    if [ ! -f "$DATA_DIR/dem.tif" ]; then
        echo "   ⛰️  Downloading DEM (${DEM_SOURCE})..."
        if ! {{ python }} scripts/download-dem.py \
            --boundary "$DATA_DIR/area.geojson" \
            --output "$DATA_DIR/dem.tif" \
            --source "$DEM_SOURCE"; then

            # Fallback strategy if primary source fails
            if [ "$DEM_SOURCE" = "cop90" ] || [ "$DEM_SOURCE" = "gmted2010" ]; then
                echo "   ⚠️  COP90 failed, falling back to SRTM..."
                DEM_SOURCE="srtm"
                {{ python }} scripts/download-dem.py \
                    --boundary "$DATA_DIR/area.geojson" \
                    --output "$DATA_DIR/dem.tif" \
                    --source "$DEM_SOURCE"
            elif [ "$DEM_SOURCE" = "srtm" ]; then
                echo "   ⚠️  SRTM failed, falling back to ETOPO1..."
                DEM_SOURCE="etopo1"
                {{ python }} scripts/download-dem.py \
                    --boundary "$DATA_DIR/area.geojson" \
                    --output "$DATA_DIR/dem.tif" \
                    --source "$DEM_SOURCE"
            else
                echo "   ❌ DEM download failed"
                exit 1
            fi
        fi
    else
        echo "   ✓ DEM exists"
    fi

    # Download layers
    if ! ls "$DATA_DIR/layers"/*.gpkg 1> /dev/null 2>&1; then
        echo "   🗺️  Downloading layers (${OSM_SOURCE})..."
        {{ python }} scripts/download-osm-layers.py \
            --geojson "$DATA_DIR/area.geojson" \
            --output-dir "$DATA_DIR/layers" \
            --source "$OSM_SOURCE"
    else
        echo "   ✓ Layers exist"
    fi

    # Download satellite imagery
    if [ ! -f "$DATA_DIR/satellite.tif" ]; then
        echo "   🛰️  Downloading satellite imagery (zoom ${SAT_ZOOM})..."
        {{ python }} scripts/download-satellite-image.py \
            --geojson "$DATA_DIR/area.geojson" \
            --output "$DATA_DIR/satellite.tif" \
            --zoom "$SAT_ZOOM" \
            --dpi "$DPI"
    else
        echo "   ✓ Satellite imagery exists"
    fi

    # Derive a local ocean layer whenever the source dataset is installed.
    if [ -f "$OCEAN_SHP" ] && [ ! -f "$DATA_DIR/layers/ocean.gpkg" ]; then
        echo "   🌊 Preparing ocean layer..."
        {{ python }} scripts/prepare-ocean-layer.py \
            --boundary "$DATA_DIR/area.geojson" \
            --ocean-boundaries "$OCEAN_SHP" \
            --output "$DATA_DIR/layers/ocean.gpkg"
    fi

    if ! ls "$DATA_DIR/layers"/*.gpkg 1> /dev/null 2>&1; then
        echo "   ❌ No vector layers were prepared"
        echo "   Expected one or more .gpkg files in $DATA_DIR/layers before config generation"
        exit 1
    fi

    echo "   ✅ Data ready"
    echo ""

    # ========================================================================
    # Step 6: Generate configuration
    # ========================================================================
    echo "⚙️  Step 6: Generating map configuration..."
    CONFIG_BASE="$CONFIG_DIR/${LOCATION}-base.yaml"
    CONFIG_OVERLAY="$CONFIG_DIR/${LOCATION}-${SCHEME}-overlay.yaml"
    CONFIG_FINAL="$CONFIG_DIR/${LOCATION}-${SCHEME}-final.yaml"

    # Generate base config
    {{ python }} scripts/generate-config.py \
        "$DATA_DIR/layers"/*.gpkg \
        --geojson "$DATA_DIR/area.geojson" \
        --output "$CONFIG_BASE" \
        --scheme "$SCHEME" \
        --dem "$DATA_DIR/dem.tif" \
        --satellite "$DATA_DIR/satellite.tif"

    # Apply overlay if exists
    if [ -f "$CONFIG_OVERLAY" ]; then
        echo "   ✓ Applying overlay: $CONFIG_OVERLAY"
        {{ python }} scripts/merge-config.py \
            "$CONFIG_BASE" \
            "$CONFIG_OVERLAY" \
            "$CONFIG_FINAL"
    else
        echo "   ℹ️  No overlay found (create with: configs/${LOCATION}-${SCHEME}-overlay.yaml)"
        cp "$CONFIG_BASE" "$CONFIG_FINAL"
    fi

    echo "   ✓ Configuration ready: $CONFIG_FINAL"
    echo ""

    # ========================================================================
    # Step 7: Generate map
    # ========================================================================
    echo "🎨 Step 7: Rendering map..."
    OUTPUT_FILE="$OUTPUT_DIR/${LOCATION}-${SCHEME}.${FORMAT}"

    {{ python }} scripts/generate-map.py \
        "$CONFIG_FINAL" \
        --geojson "$DATA_DIR/area.geojson" \
        --output "$OUTPUT_FILE" \
        -W "$WIDTH" \
        -H "$HEIGHT" \
        --dpi "$DPI"

    echo ""
    echo "✅ Map complete: $OUTPUT_FILE"
    echo ""
    echo "📊 Summary:"
    echo "   Location: $REGION"
    echo "   Area: ${AREA_KM2} km²"
    echo "   Scheme: $SCHEME"
    echo "   Size: ${WIDTH}x${HEIGHT} inches @ ${DPI} DPI"
    echo "   Tier: $TIER ($DEM_SOURCE DEM, zoom $SAT_ZOOM, $OSM_SOURCE layers)"
    echo ""
