# ============================================================================
# Map Artistry - Dynamic Map Generation
# Copyright (c) 2026 Paul Stothard
# ============================================================================
#
# Usage:
#   just build "Edmonton, AB" coral
#   just build --width 36 --height 24 "Vancouver Island, BC" natural
#   just build --buffer-km 20 "Victoria, BC" natural
#   just build-route "Edmonton, AB" downloads/cycling-routes/my-ride.gpx coral
#   just build-route --text-title "EDMONTON LOOP" --text-stats "94 KM||DISTANCE" "Edmonton, AB" downloads/cycling-routes/my-ride.gpx coral
#   just build-gpx downloads/cycling-routes/my-ride.gpx coral
#   just build-gpx --text-title "RIVER VALLEY LOOP" --text-stats "64 KM||DISTANCE" downloads/cycling-routes/my-ride.gpx coral
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

# Build a route map from region + GPX (region boundary with GPX route overlay)
[arg("height", long="height", help="Map height in inches")]
[arg("width", long="width", help="Map width in inches")]
[arg("buffer_km", long="buffer-km", help="Optional extra distance around the region boundary, in kilometers")]
[arg("text_location", long="text-location", help="Optional panel location")]
[arg("text_stats", long="text-stats", help="Optional panel stats. Supports VALUE||LABEL and ';;' separator")]
[arg("text_subtitle", long="text-subtitle", help="Optional panel subtitle")]
[arg("text_title", long="text-title", help="Optional panel title")]
[arg("format", long="format", help="Output format: png, pdf, svg")]
[arg("dpi", long="dpi", help="Resolution in DPI")]
[arg("text_units", long="text-units", help="Route stat units: auto, metric, imperial")]
build-route region gpx scheme width="24" height="24" dpi="600" format="png" buffer_km="" text_title="" text_subtitle="" text_location="" text_stats="" text_units="auto":
    @just _build-map-route "{{ region }}" "{{ gpx }}" "{{ scheme }}" "{{ width }}" "{{ height }}" "{{ dpi }}" "{{ format }}" "{{ buffer_km }}" "{{ text_title }}" "{{ text_subtitle }}" "{{ text_location }}" "{{ text_stats }}" "{{ text_units }}"

# Build a route map from GPX only (derive region boundary from GPX bbox)
[arg("height", long="height", help="Map height in inches")]
[arg("width", long="width", help="Map width in inches")]
[arg("buffer_km", long="buffer-km", help="Optional extra distance around the route bbox, in kilometers")]
[arg("text_location", long="text-location", help="Optional panel location")]
[arg("text_stats", long="text-stats", help="Optional panel stats. Supports VALUE||LABEL and ';;' separator")]
[arg("text_subtitle", long="text-subtitle", help="Optional panel subtitle")]
[arg("text_title", long="text-title", help="Optional panel title")]
[arg("format", long="format", help="Output format: png, pdf, svg")]
[arg("dpi", long="dpi", help="Resolution in DPI")]
[arg("text_units", long="text-units", help="Route stat units: auto, metric, imperial")]
build-gpx gpx scheme width="24" height="24" dpi="600" format="png" buffer_km="5" text_title="" text_subtitle="" text_location="" text_stats="" text_units="auto":
    @just _build-map-gpx "{{ gpx }}" "{{ scheme }}" "{{ width }}" "{{ height }}" "{{ dpi }}" "{{ format }}" "{{ buffer_km }}" "{{ text_title }}" "{{ text_subtitle }}" "{{ text_location }}" "{{ text_stats }}" "{{ text_units }}"

# List available color schemes
schemes:
    {{ python }} scripts/generate-config.py --list-schemes

# Show help
help:
    @echo "Map Artistry - Dynamic Map Generation"
    @echo ""
    @echo "Usage:"
    @echo "  just build [--width 24] [--height 24] [--dpi 600] [--format png] [--buffer-km N] REGION SCHEME"
    @echo "  just build-route [--width 24] [--height 24] [--dpi 600] [--format png] [--buffer-km N] [--text-title ...] [--text-subtitle ...] [--text-location ...] [--text-stats ...] [--text-units auto] REGION GPX SCHEME"
    @echo "  just build-gpx [--width 24] [--height 24] [--dpi 600] [--format png] [--buffer-km 20] [--text-title ...] [--text-subtitle ...] [--text-location ...] [--text-stats ...] [--text-units auto] GPX SCHEME"
    @echo ""
    @echo "Examples:"
    @echo '  just build "Edmonton, AB" coral'
    @echo '  just build --width 36 --height 24 "Vancouver Island, BC" natural'
    @echo '  just build --width 36 --height 24 --dpi 600 "Canada" lava'
    @echo '  just build --buffer-km 20 "Victoria, BC" natural'
    @echo '  just build-route "Edmonton, AB" downloads/cycling-routes/my-ride.gpx coral'
    @echo '  just build-route --text-title "EDMONTON LOOP" --text-subtitle "SUMMER TRAINING RIDE" --text-stats "94 KM||DISTANCE;;800 M||ELEV GAIN" "Edmonton, AB" downloads/cycling-routes/my-ride.gpx coral'
    @echo '  just build-gpx downloads/cycling-routes/my-ride.gpx coral'
    @echo '  just build-gpx --text-title "RIVER VALLEY LOOP" --text-subtitle "GPX-DERIVED REGION" --text-stats "64 KM||DISTANCE;;530 M||ELEV GAIN" downloads/cycling-routes/my-ride.gpx coral'
    @echo ""
    @echo "Parameters:"
    @echo "  --width          Map width in inches (default: 24)"
    @echo "  --height         Map height in inches (default: 24)"
    @echo "  --dpi            Resolution in DPI (default: 600)"
    @echo "  --format         Output format: png, pdf, svg (default: png)"
    @echo "  --buffer-km      Extra distance around the region/route boundary in km (build/build-route: auto-calculated; build-gpx: default 5)"
    @echo "  --text-title     Stats panel title (build-route / build-gpx only)"
    @echo "  --text-subtitle  Stats panel subtitle (build-route / build-gpx only)"
    @echo "  --text-location  Stats panel location label (build-route / build-gpx only)"
    @echo "  --text-stats     Stats panel metrics: VALUE||LABEL pairs separated by ;; (build-route / build-gpx only)"
    @echo "  --text-units     Route stat units: auto, metric, imperial (default: auto)"
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
    @echo "  • Route context diagnostics (when GPX is supplied)"

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
    CONFIG_BASE="$CONFIG_DIR/${LOCATION}-${SCHEME}-base.yaml"
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
        --format "$FORMAT" \
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

# Build orchestration for region + GPX route map
_build-map-route region gpx scheme width height dpi format buffer text_title text_subtitle text_location text_stats text_units:
    #!/usr/bin/env bash
    set -euo pipefail

    REGION="{{ region }}"
    GPX_PATH="{{ gpx }}"
    SCHEME="{{ scheme }}"
    WIDTH={{ width }}
    HEIGHT={{ height }}
    DPI={{ dpi }}
    FORMAT={{ format }}
    USER_BUFFER="{{ buffer }}"
    TEXT_TITLE="{{ text_title }}"
    TEXT_SUBTITLE="{{ text_subtitle }}"
    TEXT_LOCATION="{{ text_location }}"
    TEXT_STATS="{{ text_stats }}"
    TEXT_UNITS="{{ text_units }}"

    if [ ! -f "$GPX_PATH" ]; then
        echo "❌ GPX file not found: $GPX_PATH"
        exit 1
    fi

    LOCATION=$(echo "$REGION" | tr '[:upper:]' '[:lower:]' | sed 's/[, ]/-/g' | sed 's/--*/-/g')
    ROUTE_NAME=$(basename "$GPX_PATH" .gpx | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g')
    DATA_DIR="downloads/regions/$LOCATION"
    OUTPUT_DIR="output/${LOCATION}-route-${ROUTE_NAME}-${SCHEME}"
    CONFIG_DIR="configs"

    echo "🗺️  Building route map: $REGION ($SCHEME scheme)"
    echo "   GPX: $GPX_PATH"
    echo "   Output: $OUTPUT_DIR"
    echo ""

    mkdir -p "$DATA_DIR/layers"
    mkdir -p "$OUTPUT_DIR"
    mkdir -p "$CONFIG_DIR"

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

    echo "📍 Step 2: Downloading boundary..."
    ASPECT=$({{ python }} -c "print(round(${WIDTH} / ${HEIGHT}, 3))")

    {{ python }} scripts/download-geojson.py "$REGION" \
        --buffer "$BUFFER" \
        --aspect-ratio "$ASPECT" \
        --output "$DATA_DIR/area.geojson"

    {{ python }} scripts/validate-geojson.py "$DATA_DIR/area.geojson"
    echo "   ✓ Boundary saved (aspect ratio: $ASPECT)"
    echo ""

    echo "🧭 Step 3: Route context diagnostics..."
    CONTEXT_JSON=$({{ python }} scripts/analyze-route-context.py \
        --gpx "$GPX_PATH" \
        --boundary "$DATA_DIR/area.geojson" \
        --samples 15 \
        --retries 2 \
        --timeout 4.0 \
        --json || echo '{"status":"warn"}')
    echo "$CONTEXT_JSON" | {{ python }} -c "import sys, json; r=json.load(sys.stdin); print('🧭 Route Context'); print('   {} Reverse geocode: {}/{} successful'.format('✓' if r.get('status')=='ok' else '⚠', r.get('success_count', 0), r.get('sample_count_used', 0))); br=r.get('best_region'); print('   {} Best region: {}'.format('✓' if br else '⚠', br if br else 'Unknown (continuing)')); bc=r.get('best_country_code'); print('   {} Best country: {}'.format('✓' if bc else '⚠', bc if bc else 'Unknown (metric fallback)'))"
    ROUTE_COUNTRY_CODE=$(echo "$CONTEXT_JSON" | {{ python }} -c "import sys, json; r=json.load(sys.stdin); print((r.get('best_country_code') or '').strip().upper())")
    echo ""

    echo "🧠 Step 4: Calculating resource strategy..."
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

    echo "🌊 Step 5: Preparing optional ocean layer..."
    OCEAN_SHP="downloads/ocean-boundaries/World_Seas_IHO_v3.shp"
    if [ -f "$OCEAN_SHP" ]; then
        echo "   ✓ Ocean boundary source available"
    else
        echo "   ℹ️  Ocean boundary source not installed - continuing without ocean layer"
    fi
    echo ""

    echo "📦 Step 6: Preparing data..."
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
    echo "$NEW_CHECKSUM" > "$CHECKSUM_FILE"

    if [ ! -f "$DATA_DIR/dem.tif" ]; then
        echo "   ⛰️  Downloading DEM (${DEM_SOURCE})..."
        if ! {{ python }} scripts/download-dem.py --boundary "$DATA_DIR/area.geojson" --output "$DATA_DIR/dem.tif" --source "$DEM_SOURCE"; then
            if [ "$DEM_SOURCE" = "cop90" ] || [ "$DEM_SOURCE" = "gmted2010" ]; then
                echo "   ⚠️  COP90 failed, falling back to SRTM..."
                DEM_SOURCE="srtm"
                {{ python }} scripts/download-dem.py --boundary "$DATA_DIR/area.geojson" --output "$DATA_DIR/dem.tif" --source "$DEM_SOURCE"
            elif [ "$DEM_SOURCE" = "srtm" ]; then
                echo "   ⚠️  SRTM failed, falling back to ETOPO1..."
                DEM_SOURCE="etopo1"
                {{ python }} scripts/download-dem.py --boundary "$DATA_DIR/area.geojson" --output "$DATA_DIR/dem.tif" --source "$DEM_SOURCE"
            else
                echo "   ❌ DEM download failed"
                exit 1
            fi
        fi
    else
        echo "   ✓ DEM exists"
    fi

    if ! ls "$DATA_DIR/layers"/*.gpkg 1> /dev/null 2>&1; then
        echo "   🗺️  Downloading layers (${OSM_SOURCE})..."
        {{ python }} scripts/download-osm-layers.py --geojson "$DATA_DIR/area.geojson" --output-dir "$DATA_DIR/layers" --source "$OSM_SOURCE"
    else
        echo "   ✓ Layers exist"
    fi

    if [ ! -f "$DATA_DIR/satellite.tif" ]; then
        echo "   🛰️  Downloading satellite imagery (zoom ${SAT_ZOOM})..."
        {{ python }} scripts/download-satellite-image.py --geojson "$DATA_DIR/area.geojson" --output "$DATA_DIR/satellite.tif" --zoom "$SAT_ZOOM" --dpi "$DPI"
    else
        echo "   ✓ Satellite imagery exists"
    fi

    if [ -f "$OCEAN_SHP" ] && [ ! -f "$DATA_DIR/layers/ocean.gpkg" ]; then
        echo "   🌊 Preparing ocean layer..."
        {{ python }} scripts/prepare-ocean-layer.py --boundary "$DATA_DIR/area.geojson" --ocean-boundaries "$OCEAN_SHP" --output "$DATA_DIR/layers/ocean.gpkg"
    fi

    if ! ls "$DATA_DIR/layers"/*.gpkg 1> /dev/null 2>&1; then
        echo "   ❌ No vector layers were prepared"
        exit 1
    fi
    echo "   ✅ Data ready"
    echo ""

    echo "⚙️  Step 7: Generating map configuration..."
    CONFIG_BASE="$CONFIG_DIR/${LOCATION}-route-${ROUTE_NAME}-${SCHEME}-base.yaml"
    CONFIG_OVERLAY="$CONFIG_DIR/${LOCATION}-route-${ROUTE_NAME}-${SCHEME}-overlay.yaml"
    CONFIG_FINAL="$CONFIG_DIR/${LOCATION}-route-${ROUTE_NAME}-${SCHEME}-final.yaml"

    CONFIG_ARGS=(
        "--gpx" "$GPX_PATH"
        "--enable-text"
    )

    if [ -n "$TEXT_TITLE" ]; then CONFIG_ARGS+=("--text-title" "$TEXT_TITLE"); fi
    if [ -n "$TEXT_SUBTITLE" ]; then CONFIG_ARGS+=("--text-subtitle" "$TEXT_SUBTITLE"); fi
    if [ -n "$TEXT_LOCATION" ]; then CONFIG_ARGS+=("--text-location" "$TEXT_LOCATION"); fi
    if [ -n "$TEXT_STATS" ]; then CONFIG_ARGS+=("--text-stats" "$TEXT_STATS"); fi

    {{ python }} scripts/generate-config.py \
        "$DATA_DIR/layers"/*.gpkg \
        --geojson "$DATA_DIR/area.geojson" \
        --output "$CONFIG_BASE" \
        --scheme "$SCHEME" \
        --dem "$DATA_DIR/dem.tif" \
        --satellite "$DATA_DIR/satellite.tif" \
        "${CONFIG_ARGS[@]}"

    if [ -f "$CONFIG_OVERLAY" ]; then
        echo "   ✓ Applying overlay: $CONFIG_OVERLAY"
        {{ python }} scripts/merge-config.py "$CONFIG_BASE" "$CONFIG_OVERLAY" "$CONFIG_FINAL"
    else
        echo "   ℹ️  No overlay found (create with: configs/${LOCATION}-route-${ROUTE_NAME}-${SCHEME}-overlay.yaml)"
        cp "$CONFIG_BASE" "$CONFIG_FINAL"
    fi

    echo "🎨 Step 8: Rendering map..."
    OUTPUT_FILE="$OUTPUT_DIR/${LOCATION}-route-${ROUTE_NAME}-${SCHEME}.${FORMAT}"

    {{ python }} scripts/generate-map.py \
        "$CONFIG_FINAL" \
        --geojson "$DATA_DIR/area.geojson" \
        --output "$OUTPUT_FILE" \
        --format "$FORMAT" \
        --route-units "$TEXT_UNITS" \
        --route-country-code "$ROUTE_COUNTRY_CODE" \
        -W "$WIDTH" \
        -H "$HEIGHT" \
        --dpi "$DPI"

    echo ""
    echo "✅ Route map complete: $OUTPUT_FILE"

# Build orchestration for GPX-only route map (region derived from GPX bbox)
_build-map-gpx gpx scheme width height dpi format buffer text_title text_subtitle text_location text_stats text_units:
    #!/usr/bin/env bash
    set -euo pipefail

    GPX_PATH="{{ gpx }}"
    SCHEME="{{ scheme }}"
    WIDTH={{ width }}
    HEIGHT={{ height }}
    DPI={{ dpi }}
    FORMAT={{ format }}
    BUFFER="{{ buffer }}"
    TEXT_TITLE="{{ text_title }}"
    TEXT_SUBTITLE="{{ text_subtitle }}"
    TEXT_LOCATION="{{ text_location }}"
    TEXT_STATS="{{ text_stats }}"
    TEXT_UNITS="{{ text_units }}"

    if [ ! -f "$GPX_PATH" ]; then
        echo "❌ GPX file not found: $GPX_PATH"
        exit 1
    fi

    ROUTE_NAME=$(basename "$GPX_PATH" .gpx | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g')
    LOCATION="route-${ROUTE_NAME}"
    DATA_DIR="downloads/routes/$ROUTE_NAME"
    OUTPUT_DIR="output/${ROUTE_NAME}-${SCHEME}"
    CONFIG_DIR="configs"

    echo "🗺️  Building GPX-derived route map ($SCHEME scheme)"
    echo "   GPX: $GPX_PATH"
    echo "   Output: $OUTPUT_DIR"
    echo ""

    mkdir -p "$DATA_DIR/layers"
    mkdir -p "$OUTPUT_DIR"
    mkdir -p "$CONFIG_DIR"

    echo "📍 Step 1: Deriving boundary from GPX..."
    ASPECT=$({{ python }} -c "print(round(${WIDTH} / ${HEIGHT}, 3))")
    {{ python }} scripts/download-geojson.py \
        --gpx "$GPX_PATH" \
        --buffer "$BUFFER" \
        --aspect-ratio "$ASPECT" \
        --output "$DATA_DIR/area.geojson"

    {{ python }} scripts/validate-geojson.py "$DATA_DIR/area.geojson"
    echo "   ✓ Boundary saved (aspect ratio: $ASPECT, buffer: ${BUFFER}km)"
    echo ""

    echo "🧭 Step 2: Route context diagnostics..."
    CONTEXT_JSON=$({{ python }} scripts/analyze-route-context.py \
        --gpx "$GPX_PATH" \
        --boundary "$DATA_DIR/area.geojson" \
        --samples 15 \
        --retries 2 \
        --timeout 4.0 \
        --json || echo '{"status":"warn"}')
    echo "$CONTEXT_JSON" | {{ python }} -c "import sys, json; r=json.load(sys.stdin); print('🧭 Route Context'); print('   {} Reverse geocode: {}/{} successful'.format('✓' if r.get('status')=='ok' else '⚠', r.get('success_count', 0), r.get('sample_count_used', 0))); br=r.get('best_region'); print('   {} Best region: {}'.format('✓' if br else '⚠', br if br else 'Unknown (continuing)')); bc=r.get('best_country_code'); print('   {} Best country: {}'.format('✓' if bc else '⚠', bc if bc else 'Unknown (metric fallback)'))"
    ROUTE_COUNTRY_CODE=$(echo "$CONTEXT_JSON" | {{ python }} -c "import sys, json; r=json.load(sys.stdin); print((r.get('best_country_code') or '').strip().upper())")
    echo ""

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

    echo "📦 Step 4: Preparing data..."
    if [ ! -f "$DATA_DIR/dem.tif" ]; then
        echo "   ⛰️  Downloading DEM (${DEM_SOURCE})..."
        {{ python }} scripts/download-dem.py --boundary "$DATA_DIR/area.geojson" --output "$DATA_DIR/dem.tif" --source "$DEM_SOURCE"
    else
        echo "   ✓ DEM exists"
    fi

    if ! ls "$DATA_DIR/layers"/*.gpkg 1> /dev/null 2>&1; then
        echo "   🗺️  Downloading layers (${OSM_SOURCE})..."
        {{ python }} scripts/download-osm-layers.py --geojson "$DATA_DIR/area.geojson" --output-dir "$DATA_DIR/layers" --source "$OSM_SOURCE"
    else
        echo "   ✓ Layers exist"
    fi

    if [ ! -f "$DATA_DIR/satellite.tif" ]; then
        echo "   🛰️  Downloading satellite imagery (zoom ${SAT_ZOOM})..."
        {{ python }} scripts/download-satellite-image.py --geojson "$DATA_DIR/area.geojson" --output "$DATA_DIR/satellite.tif" --zoom "$SAT_ZOOM" --dpi "$DPI"
    else
        echo "   ✓ Satellite imagery exists"
    fi
    echo ""

    echo "⚙️  Step 5: Generating map configuration..."
    CONFIG_BASE="$CONFIG_DIR/${LOCATION}-${SCHEME}-base.yaml"
    CONFIG_OVERLAY="$CONFIG_DIR/${LOCATION}-${SCHEME}-overlay.yaml"
    CONFIG_FINAL="$CONFIG_DIR/${LOCATION}-${SCHEME}-final.yaml"

    CONFIG_ARGS=(
        "--gpx" "$GPX_PATH"
        "--enable-text"
    )

    if [ -n "$TEXT_TITLE" ]; then CONFIG_ARGS+=("--text-title" "$TEXT_TITLE"); fi
    if [ -n "$TEXT_SUBTITLE" ]; then CONFIG_ARGS+=("--text-subtitle" "$TEXT_SUBTITLE"); fi
    if [ -n "$TEXT_LOCATION" ]; then CONFIG_ARGS+=("--text-location" "$TEXT_LOCATION"); fi
    if [ -n "$TEXT_STATS" ]; then CONFIG_ARGS+=("--text-stats" "$TEXT_STATS"); fi

    {{ python }} scripts/generate-config.py \
        "$DATA_DIR/layers"/*.gpkg \
        --geojson "$DATA_DIR/area.geojson" \
        --output "$CONFIG_BASE" \
        --scheme "$SCHEME" \
        --dem "$DATA_DIR/dem.tif" \
        --satellite "$DATA_DIR/satellite.tif" \
        "${CONFIG_ARGS[@]}"

    if [ -f "$CONFIG_OVERLAY" ]; then
        echo "   ✓ Applying overlay: $CONFIG_OVERLAY"
        {{ python }} scripts/merge-config.py "$CONFIG_BASE" "$CONFIG_OVERLAY" "$CONFIG_FINAL"
    else
        cp "$CONFIG_BASE" "$CONFIG_FINAL"
    fi

    echo "🎨 Step 6: Rendering map..."
    OUTPUT_FILE="$OUTPUT_DIR/${ROUTE_NAME}-${SCHEME}.${FORMAT}"

    {{ python }} scripts/generate-map.py \
        "$CONFIG_FINAL" \
        --geojson "$DATA_DIR/area.geojson" \
        --output "$OUTPUT_FILE" \
        --format "$FORMAT" \
        --route-units "$TEXT_UNITS" \
        --route-country-code "$ROUTE_COUNTRY_CODE" \
        -W "$WIDTH" \
        -H "$HEIGHT" \
        --dpi "$DPI"

    echo ""
    echo "✅ GPX route map complete: $OUTPUT_FILE"
