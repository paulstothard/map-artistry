# ============================================================================
# Map Artistry - Dynamic Map Generation
# Copyright (c) 2026 Paul Stothard
# ============================================================================
#
# Usage:
#   just build "Edmonton, AB" coral
#   just build --width 36 --height 24 "Vancouver Island, BC" natural
#   just build --buffer-km 20 "Victoria, BC" natural
#   just build --output-dir my-maps "Edmonton, AB" coral
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
# Configuration - Portable Workspace System
# ============================================================================
# For portable use: Set MAP_ARTISTRY_REPO to the absolute path of the repo
# Default: assume justfile is in the repo root

repo_dir := env_var_or_default('MAP_ARTISTRY_REPO', justfile_directory())

# Workspace: where downloads/configs/output are stored
# Default: user/ subfolder in the repo (for personal maps)
# Override with WORKSPACE_DIR env var (e.g., for examples: WORKSPACE_DIR=examples)

workspace_dir := env_var_or_default('WORKSPACE_DIR', repo_dir / "user")

# ============================================================================
# Global Paths - Repo paths (immutable - where code lives)
# ============================================================================

scripts_dir := repo_dir / "scripts"
schemes_dir := repo_dir / "schemes"

# ============================================================================
# Global Paths - Workspace paths (where data is stored)
# ============================================================================

downloads_dir := workspace_dir / "downloads"
regions_dir := workspace_dir / "downloads" / "regions"
routes_dir := workspace_dir / "downloads" / "routes"
natural_earth_cache_dir := workspace_dir / "downloads" / "natural-earth"
ocean_boundaries_dir := repo_dir / "ocean-boundaries"
configs_dir := workspace_dir / "configs"
output_dir := workspace_dir / "output"
cache_dir := workspace_dir / "cache"
publish_dir := workspace_dir / "publish"
examples_dir := workspace_dir
examples_full_dir := workspace_dir / "full"
examples_thumb_dir := workspace_dir / "thumbnails"

# ============================================================================
# Main Commands
# ============================================================================

# Build a map for any region with automatic settings
[arg("height", long="height", help="Map height in inches")]
[arg("width", long="width", help="Map width in inches")]
[arg("buffer_km", long="buffer-km", help="Optional extra distance around the region boundary, in kilometers")]
[arg("text_location", long="text-location", help="Optional panel location")]
[arg("text_stats", long="text-stats", help="Optional panel stats. Supports VALUE||LABEL and ';;' separator")]
[arg("text_subtitle", long="text-subtitle", help="Optional panel subtitle")]
[arg("text_title", long="text-title", help="Optional panel title")]
[arg("output_dir", long="output-dir", help="Output folder for generated images")]
[arg("format", long="format", help="Output format: png, pdf, svg")]
[arg("dpi", long="dpi", help="Resolution in DPI")]
build region scheme width="24" height="24" dpi="300" format="png" buffer_km="" text_title="" text_subtitle="" text_location="" text_stats="" output_dir=output_dir:
    @just _build-map "{{ region }}" "{{ scheme }}" "{{ width }}" "{{ height }}" "{{ dpi }}" "{{ format }}" "{{ buffer_km }}" "{{ text_title }}" "{{ text_subtitle }}" "{{ text_location }}" "{{ text_stats }}" "{{ output_dir }}"

# Build a route map from region + GPX (region boundary with GPX route overlay)
[arg("height", long="height", help="Map height in inches")]
[arg("width", long="width", help="Map width in inches")]
[arg("buffer_km", long="buffer-km", help="Optional extra distance around the region boundary, in kilometers")]
[arg("text_location", long="text-location", help="Optional panel location")]
[arg("text_stats", long="text-stats", help="Optional panel stats. Supports VALUE||LABEL and ';;' separator")]
[arg("text_subtitle", long="text-subtitle", help="Optional panel subtitle")]
[arg("text_title", long="text-title", help="Optional panel title")]
[arg("output_dir", long="output-dir", help="Output folder for generated images")]
[arg("format", long="format", help="Output format: png, pdf, svg")]
[arg("dpi", long="dpi", help="Resolution in DPI")]
[arg("text_units", long="text-units", help="Route stat units: auto, metric, imperial")]
build-route region gpx scheme width="24" height="24" dpi="300" format="png" buffer_km="" text_title="" text_subtitle="" text_location="" text_stats="" text_units="auto" output_dir=output_dir:
    @just _build-map-route "{{ region }}" "{{ gpx }}" "{{ scheme }}" "{{ width }}" "{{ height }}" "{{ dpi }}" "{{ format }}" "{{ buffer_km }}" "{{ text_title }}" "{{ text_subtitle }}" "{{ text_location }}" "{{ text_stats }}" "{{ text_units }}" "{{ output_dir }}"

# Build a route map from GPX only (derive region boundary from GPX bbox)
[arg("height", long="height", help="Map height in inches")]
[arg("width", long="width", help="Map width in inches")]
[arg("buffer_km", long="buffer-km", help="Optional extra distance around the route bbox, in kilometers")]
[arg("text_location", long="text-location", help="Optional panel location")]
[arg("text_stats", long="text-stats", help="Optional panel stats. Supports VALUE||LABEL and ';;' separator")]
[arg("text_subtitle", long="text-subtitle", help="Optional panel subtitle")]
[arg("text_title", long="text-title", help="Optional panel title")]
[arg("output_dir", long="output-dir", help="Output folder for generated images")]
[arg("format", long="format", help="Output format: png, pdf, svg")]
[arg("dpi", long="dpi", help="Resolution in DPI")]
[arg("text_units", long="text-units", help="Route stat units: auto, metric, imperial")]
build-gpx gpx scheme width="24" height="24" dpi="300" format="png" buffer_km="5" text_title="" text_subtitle="" text_location="" text_stats="" text_units="auto" output_dir=output_dir:
    @just _build-map-gpx "{{ gpx }}" "{{ scheme }}" "{{ width }}" "{{ height }}" "{{ dpi }}" "{{ format }}" "{{ buffer_km }}" "{{ text_title }}" "{{ text_subtitle }}" "{{ text_location }}" "{{ text_stats }}" "{{ text_units }}" "{{ output_dir }}"

# Build all color schemes for a region
[arg("height", long="height", help="Map height in inches")]
[arg("width", long="width", help="Map width in inches")]
[arg("buffer_km", long="buffer-km", help="Optional extra distance around the region boundary, in kilometers")]
[arg("text_location", long="text-location", help="Optional panel location")]
[arg("text_stats", long="text-stats", help="Optional panel stats. Supports VALUE||LABEL and ';;' separator")]
[arg("text_subtitle", long="text-subtitle", help="Optional panel subtitle")]
[arg("text_title", long="text-title", help="Optional panel title")]
[arg("output_dir", long="output-dir", help="Output folder for generated images")]
[arg("format", long="format", help="Output format: png, pdf, svg")]
[arg("dpi", long="dpi", help="Resolution in DPI")]
build-all-schemes region width="24" height="24" dpi="300" format="png" buffer_km="" text_title="" text_subtitle="" text_location="" text_stats="" output_dir=output_dir:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🎨 Building all color schemes for region: {{ region }}"
    SCHEMES=$(just _get-scheme-names)
    for SCHEME in $SCHEMES; do
        echo "  → Processing scheme: $SCHEME"
        just build \
            --width "{{ width }}" \
            --height "{{ height }}" \
            --dpi "{{ dpi }}" \
            --format "{{ format }}" \
            --buffer-km "{{ buffer_km }}" \
            --text-title "{{ text_title }}" \
            --text-subtitle "{{ text_subtitle }}" \
            --text-location "{{ text_location }}" \
            --text-stats "{{ text_stats }}" \
            --output-dir "{{ output_dir }}" \
            "{{ region }}" "$SCHEME"
    done
    echo "✅ Completed all schemes for {{ region }}"

# Build all color schemes for a region + GPX route
[arg("height", long="height", help="Map height in inches")]
[arg("width", long="width", help="Map width in inches")]
[arg("buffer_km", long="buffer-km", help="Optional extra distance around the region boundary, in kilometers")]
[arg("text_location", long="text-location", help="Optional panel location")]
[arg("text_stats", long="text-stats", help="Optional panel stats. Supports VALUE||LABEL and ';;' separator")]
[arg("text_subtitle", long="text-subtitle", help="Optional panel subtitle")]
[arg("text_title", long="text-title", help="Optional panel title")]
[arg("output_dir", long="output-dir", help="Output folder for generated images")]
[arg("format", long="format", help="Output format: png, pdf, svg")]
[arg("dpi", long="dpi", help="Resolution in DPI")]
[arg("text_units", long="text-units", help="Route stat units: auto, metric, imperial")]
build-all-route-schemes region gpx width="24" height="24" dpi="300" format="png" buffer_km="" text_title="" text_subtitle="" text_location="" text_stats="" text_units="auto" output_dir=output_dir:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🎨 Building all color schemes for route: {{ region }} + {{ gpx }}"
    SCHEMES=$(just _get-scheme-names)
    for SCHEME in $SCHEMES; do
        echo "  → Processing scheme: $SCHEME"
        just build-route \
            --width "{{ width }}" \
            --height "{{ height }}" \
            --dpi "{{ dpi }}" \
            --format "{{ format }}" \
            --buffer-km "{{ buffer_km }}" \
            --text-title "{{ text_title }}" \
            --text-subtitle "{{ text_subtitle }}" \
            --text-location "{{ text_location }}" \
            --text-stats "{{ text_stats }}" \
            --text-units "{{ text_units }}" \
            --output-dir "{{ output_dir }}" \
            "{{ region }}" "{{ gpx }}" "$SCHEME"
    done
    echo "✅ Completed all schemes for route"

# Build all color schemes for a GPX file
[arg("height", long="height", help="Map height in inches")]
[arg("width", long="width", help="Map width in inches")]
[arg("buffer_km", long="buffer-km", help="Optional extra distance around the route bbox, in kilometers")]
[arg("text_location", long="text-location", help="Optional panel location")]
[arg("text_stats", long="text-stats", help="Optional panel stats. Supports VALUE||LABEL and ';;' separator")]
[arg("text_subtitle", long="text-subtitle", help="Optional panel subtitle")]
[arg("text_title", long="text-title", help="Optional panel title")]
[arg("output_dir", long="output-dir", help="Output folder for generated images")]
[arg("format", long="format", help="Output format: png, pdf, svg")]
[arg("dpi", long="dpi", help="Resolution in DPI")]
[arg("text_units", long="text-units", help="Route stat units: auto, metric, imperial")]
build-all-gpx-schemes gpx width="24" height="24" dpi="300" format="png" buffer_km="5" text_title="" text_subtitle="" text_location="" text_stats="" text_units="auto" output_dir=output_dir:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🎨 Building all color schemes for GPX: {{ gpx }}"
    SCHEMES=$(just _get-scheme-names)
    for SCHEME in $SCHEMES; do
        echo "  → Processing scheme: $SCHEME"
        just build-gpx \
            --width "{{ width }}" \
            --height "{{ height }}" \
            --dpi "{{ dpi }}" \
            --format "{{ format }}" \
            --buffer-km "{{ buffer_km }}" \
            --text-title "{{ text_title }}" \
            --text-subtitle "{{ text_subtitle }}" \
            --text-location "{{ text_location }}" \
            --text-stats "{{ text_stats }}" \
            --text-units "{{ text_units }}" \
            --output-dir "{{ output_dir }}" \
            "{{ gpx }}" "$SCHEME"
    done
    echo "✅ Completed all schemes for GPX"

# List available color schemes
schemes:
    @{{ python }} "{{ scripts_dir }}/generate-config.py" --list-schemes --schemes-dir "{{ schemes_dir }}"

# Internal: Get scheme names only (one per line)
_get-scheme-names:
    @{{ python }} "{{ scripts_dir }}/generate-config.py" --list-scheme-names --schemes-dir "{{ schemes_dir }}"

# Show help
help:
    @echo "Map Artistry - Dynamic Map Generation"
    @echo ""
    @echo "Usage:"
    @echo "  just build [--width 24] [--height 24] [--dpi 300] [--format png] [--buffer-km N] [--text-title ...] [--text-subtitle ...] [--text-location ...] [--text-stats ...] [--output-dir output] REGION SCHEME"
    @echo "  just build-route [--width 24] [--height 24] [--dpi 300] [--format png] [--buffer-km N] [--text-title ...] [--text-subtitle ...] [--text-location ...] [--text-stats ...] [--text-units auto] [--output-dir output] REGION GPX SCHEME"
    @echo "  just build-gpx [--width 24] [--height 24] [--dpi 300] [--format png] [--buffer-km 20] [--text-title ...] [--text-subtitle ...] [--text-location ...] [--text-stats ...] [--text-units auto] [--output-dir output] GPX SCHEME"
    @echo "  just build-all-schemes [OPTIONS] REGION"
    @echo "  just build-all-route-schemes [OPTIONS] REGION GPX"
    @echo "  just build-all-gpx-schemes [OPTIONS] GPX"
    @echo ""
    @echo "Examples:"
    @echo '  just build "Edmonton, AB" coral'
    @echo '  just build --width 36 --height 24 "Vancouver Island, BC" natural'
    @echo '  just build --width 36 --height 24 --dpi 300 "Canada" lava'
    @echo '  just build --buffer-km 20 "Victoria, BC" natural'
    @echo '  just build --text-title "VICTORIA" --text-subtitle "BRITISH COLUMBIA" "Victoria, BC" natural'
    @echo '  just build-route "Edmonton, AB" downloads/cycling-routes/my-ride.gpx coral'
    @echo '  just build-route --text-title "EDMONTON LOOP" --text-subtitle "SUMMER TRAINING RIDE" --text-stats "94 KM||DISTANCE;;800 M||ELEV GAIN" "Edmonton, AB" downloads/cycling-routes/my-ride.gpx coral'
    @echo '  just build-gpx downloads/cycling-routes/my-ride.gpx coral'
    @echo '  just build-gpx --text-title "RIVER VALLEY LOOP" --text-subtitle "GPX-DERIVED REGION" --text-stats "64 KM||DISTANCE;;530 M||ELEV GAIN" downloads/cycling-routes/my-ride.gpx coral'
    @echo '  just build-all-schemes "Iceland"'
    @echo '  just build-all-schemes --width 36 --height 24 "Vancouver Island, BC"'
    @echo '  just build-all-route-schemes "Boston, MA" downloads/cycling-routes/boston-loop.gpx'
    @echo ""
    @echo "Parameters:"
    @echo "  --width          Map width in inches (default: 24)"
    @echo "  --height         Map height in inches (default: 24)"
    @echo "  --dpi            Resolution in DPI (default: 300)"
    @echo "  --format         Output format: png, pdf, svg (default: png)"
    @echo "  --buffer-km      Extra distance around the region/route boundary in km (build/build-route: auto-calculated; build-gpx: default 5)"
    @echo "  --text-title     Stats panel title"
    @echo "  --text-subtitle  Stats panel subtitle"
    @echo "  --text-location  Stats panel location label"
    @echo "  --text-stats     Stats panel metrics: VALUE||LABEL pairs separated by ;; (route maps can derive distance from GPX)"
    @echo "  --text-units     Route stat units: auto, metric, imperial (default: auto; build-route / build-gpx only)"
    @echo "  --output-dir     Output folder for generated images (default: output)"
    @echo ""
    @echo "Image Processing Tools:"
    @echo "  just publish [--input-dir output] [--output-dir publish] [--force true]"
    @echo "      Smart copy images (only copies if newer or missing)"
    @echo "  just create-examples [--full-width 1200] [--thumb-width 400] [--force true]"
    @echo "      Create resized examples (full + thumbnails) with timestamp checking"
    @echo "  just resize INPUT_DIR OUTPUT_DIR [--width 1200]"
    @echo "      Batch resize images to specified width"
    @echo "  just add-labels INPUT_DIR OUTPUT_DIR [--label-pattern \"{scheme}\"]"
    @echo "      Add text labels to images (default: scheme name in upper-right)"
    @echo "  just create-montage INPUT_DIR OUTPUT_FILE [--cols 4|auto] [--spacing 10] [--add-labels true] [--pattern \"*\"]"
    @echo "      Create grid layout of images with optional labels (use --cols auto for optimal layout)"
    @echo "  just create-pdf INPUT_DIR OUTPUT_FILE [--dpi 150] [--page-size letter]"
    @echo "      Create multi-page PDF (one image per page)"
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

# ============================================================================
# Internal Recipes (prefixed with _)
# ============================================================================

# Main build orchestration
_build-map region scheme width height dpi format buffer text_title text_subtitle text_location text_stats output_dir:
    #!/usr/bin/env bash
    set -euo pipefail

    REGION="{{ region }}"
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

    if [ -z "${SCHEME//[[:space:]]/}" ]; then
        echo "❌ Color scheme is required and cannot be empty"
        echo "   Usage: just build \"Region\" <scheme>"
        exit 1
    fi

    # Sanitize region name for filesystem (replace spaces, slashes, etc.)
    LOCATION=$(echo "$REGION" | tr '[:upper:]' '[:lower:]' | sed 's/[, ]/-/g' | sed 's/--*/-/g')
    DATA_DIR="{{ regions_dir }}/$LOCATION"
    OUTPUT_DIR="{{ output_dir }}/${LOCATION}-${SCHEME}"
    CONFIG_DIR="{{ configs_dir }}"

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
        ESTIMATE_JSON=$({{ python }} "{{ scripts_dir }}/calculate-area.py" --place "$REGION")
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

    {{ python }} "{{ scripts_dir }}/download-geojson.py" "$REGION" \
        --buffer "$BUFFER" \
        --aspect-ratio "$ASPECT" \
        --output "$DATA_DIR/area.geojson"

    {{ python }} "{{ scripts_dir }}/validate-geojson.py" "$DATA_DIR/area.geojson"

    echo "   ✓ Boundary saved (aspect ratio: $ASPECT)"
    echo ""

    # ========================================================================
    # Step 3: Calculate strategy from actual buffered area
    # ========================================================================
    echo "🧠 Step 3: Calculating resource strategy..."
    STRATEGY_JSON=$({{ python }} "{{ scripts_dir }}/calculate-area.py" "$DATA_DIR/area.geojson")
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
    OCEAN_SHP="{{ ocean_boundaries_dir }}/World_Seas_IHO_v3.shp"
    if [ -f "$OCEAN_SHP" ]; then
        echo "   ✓ Ocean boundary source available: $OCEAN_SHP"
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
        if ! {{ python }} "{{ scripts_dir }}/download-dem.py" \
            --boundary "$DATA_DIR/area.geojson" \
            --output "$DATA_DIR/dem.tif" \
            --source "$DEM_SOURCE"; then

            # Fallback strategy if primary source fails
            if [ "$DEM_SOURCE" = "cop90" ] || [ "$DEM_SOURCE" = "gmted2010" ]; then
                echo "   ⚠️  COP90 failed, falling back to SRTM..."
                DEM_SOURCE="srtm"
                {{ python }} "{{ scripts_dir }}/download-dem.py" \
                    --boundary "$DATA_DIR/area.geojson" \
                    --output "$DATA_DIR/dem.tif" \
                    --source "$DEM_SOURCE"
            elif [ "$DEM_SOURCE" = "srtm" ]; then
                echo "   ⚠️  SRTM failed, falling back to ETOPO1..."
                DEM_SOURCE="etopo1"
                {{ python }} "{{ scripts_dir }}/download-dem.py" \
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
        {{ python }} "{{ scripts_dir }}/download-osm-layers.py" \
            --geojson "$DATA_DIR/area.geojson" \
            --output-dir "$DATA_DIR/layers" \
            --cache-dir "{{ cache_dir }}" \
            --natural-earth-cache-dir "{{ natural_earth_cache_dir }}" \
            --source "$OSM_SOURCE"
    else
        echo "   ✓ Layers exist"
    fi

    # Download satellite imagery
    if [ ! -f "$DATA_DIR/satellite.tif" ]; then
        echo "   🛰️  Downloading satellite imagery (zoom ${SAT_ZOOM})..."
        {{ python }} "{{ scripts_dir }}/download-satellite-image.py" \
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
        {{ python }} "{{ scripts_dir }}/prepare-ocean-layer.py" \
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

    # Build config args array for text options
    CONFIG_ARGS=()
    if [ -n "$TEXT_TITLE" ] || [ -n "$TEXT_SUBTITLE" ] || [ -n "$TEXT_LOCATION" ] || [ -n "$TEXT_STATS" ]; then
        CONFIG_ARGS+=("--enable-text")
        if [ -n "$TEXT_TITLE" ]; then CONFIG_ARGS+=("--text-title" "$TEXT_TITLE"); fi
        if [ -n "$TEXT_SUBTITLE" ]; then CONFIG_ARGS+=("--text-subtitle" "$TEXT_SUBTITLE"); fi
        if [ -n "$TEXT_LOCATION" ]; then CONFIG_ARGS+=("--text-location" "$TEXT_LOCATION"); fi
        if [ -n "$TEXT_STATS" ]; then CONFIG_ARGS+=("--text-stats" "$TEXT_STATS"); fi
    fi

    # Generate base config
    {{ python }} "{{ scripts_dir }}/generate-config.py" \
        "$DATA_DIR/layers"/*.gpkg \
        --geojson "$DATA_DIR/area.geojson" \
        --output "$CONFIG_BASE" \
        --schemes-dir "{{ schemes_dir }}" \
        --scheme "$SCHEME" \
        --dem "$DATA_DIR/dem.tif" \
        --satellite "$DATA_DIR/satellite.tif" \
        "${CONFIG_ARGS[@]}"

    # Apply overlay if exists
    if [ -f "$CONFIG_OVERLAY" ]; then
        echo "   ✓ Applying overlay: $CONFIG_OVERLAY"
        {{ python }} "{{ scripts_dir }}/merge-config.py" \
            "$CONFIG_BASE" \
            "$CONFIG_OVERLAY" \
            "$CONFIG_FINAL"
    else
        echo "   ℹ️  No overlay found (create with: {{ configs_dir }}/${LOCATION}-${SCHEME}-overlay.yaml)"
        cp "$CONFIG_BASE" "$CONFIG_FINAL"
    fi

    echo "   ✓ Configuration ready: $CONFIG_FINAL"
    echo ""

    # ========================================================================
    # Step 7: Generate map
    # ========================================================================
    echo "🎨 Step 7: Rendering map..."
    OUTPUT_FILE="$OUTPUT_DIR/${LOCATION}-${SCHEME}.${FORMAT}"

    {{ python }} "{{ scripts_dir }}/generate-map.py" \
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
_build-map-route region gpx scheme width height dpi format buffer text_title text_subtitle text_location text_stats text_units output_dir:
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

    if [ -z "${SCHEME//[[:space:]]/}" ]; then
        echo "❌ Color scheme is required and cannot be empty"
        echo "   Usage: just build-route \"Region\" path/to/route.gpx <scheme>"
        exit 1
    fi

    if [ ! -f "$GPX_PATH" ]; then
        echo "❌ GPX file not found: $GPX_PATH"
        exit 1
    fi

    LOCATION=$(echo "$REGION" | tr '[:upper:]' '[:lower:]' | sed 's/[, ]/-/g' | sed 's/--*/-/g')
    ROUTE_NAME=$(basename "$GPX_PATH" .gpx | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g')
    DATA_DIR="{{ regions_dir }}/$LOCATION"
    OUTPUT_DIR="{{ output_dir }}/${LOCATION}-route-${ROUTE_NAME}-${SCHEME}"
    CONFIG_DIR="{{ configs_dir }}"

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
        ESTIMATE_JSON=$({{ python }} "{{ scripts_dir }}/calculate-area.py" --place "$REGION")
        BUFFER=$(echo "$ESTIMATE_JSON" | {{ python }} -c "import sys, json; print(json.load(sys.stdin)['buffer_km'])")
        echo "   Recommended buffer: ${BUFFER}km"
    fi
    echo ""

    echo "📍 Step 2: Downloading boundary..."
    ASPECT=$({{ python }} -c "print(round(${WIDTH} / ${HEIGHT}, 3))")

    {{ python }} "{{ scripts_dir }}/download-geojson.py" "$REGION" \
        --buffer "$BUFFER" \
        --aspect-ratio "$ASPECT" \
        --output "$DATA_DIR/area.geojson"

    {{ python }} "{{ scripts_dir }}/validate-geojson.py" "$DATA_DIR/area.geojson"
    echo "   ✓ Boundary saved (aspect ratio: $ASPECT)"
    echo ""

    echo "🧭 Step 3: Route context diagnostics..."
    CONTEXT_JSON=$({{ python }} "{{ scripts_dir }}/analyze-route-context.py" \
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
    STRATEGY_JSON=$({{ python }} "{{ scripts_dir }}/calculate-area.py" "$DATA_DIR/area.geojson")
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
    OCEAN_SHP="{{ ocean_boundaries_dir }}/World_Seas_IHO_v3.shp"
    if [ -f "$OCEAN_SHP" ]; then
        echo "   ✓ Ocean boundary source available: $OCEAN_SHP"
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
        if ! {{ python }} "{{ scripts_dir }}/download-dem.py" --boundary "$DATA_DIR/area.geojson" --output "$DATA_DIR/dem.tif" --source "$DEM_SOURCE"; then
            if [ "$DEM_SOURCE" = "cop90" ] || [ "$DEM_SOURCE" = "gmted2010" ]; then
                echo "   ⚠️  COP90 failed, falling back to SRTM..."
                DEM_SOURCE="srtm"
                {{ python }} "{{ scripts_dir }}/download-dem.py" --boundary "$DATA_DIR/area.geojson" --output "$DATA_DIR/dem.tif" --source "$DEM_SOURCE"
            elif [ "$DEM_SOURCE" = "srtm" ]; then
                echo "   ⚠️  SRTM failed, falling back to ETOPO1..."
                DEM_SOURCE="etopo1"
                {{ python }} "{{ scripts_dir }}/download-dem.py" --boundary "$DATA_DIR/area.geojson" --output "$DATA_DIR/dem.tif" --source "$DEM_SOURCE"
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
        {{ python }} "{{ scripts_dir }}/download-osm-layers.py" --geojson "$DATA_DIR/area.geojson" --output-dir "$DATA_DIR/layers" --cache-dir "{{ cache_dir }}" --natural-earth-cache-dir "{{ natural_earth_cache_dir }}" --source "$OSM_SOURCE"
    else
        echo "   ✓ Layers exist"
    fi

    if [ ! -f "$DATA_DIR/satellite.tif" ]; then
        echo "   🛰️  Downloading satellite imagery (zoom ${SAT_ZOOM})..."
        {{ python }} "{{ scripts_dir }}/download-satellite-image.py" --geojson "$DATA_DIR/area.geojson" --output "$DATA_DIR/satellite.tif" --zoom "$SAT_ZOOM" --dpi "$DPI"
    else
        echo "   ✓ Satellite imagery exists"
    fi

    if [ -f "$OCEAN_SHP" ] && [ ! -f "$DATA_DIR/layers/ocean.gpkg" ]; then
        echo "   🌊 Preparing ocean layer..."
        {{ python }} "{{ scripts_dir }}/prepare-ocean-layer.py" --boundary "$DATA_DIR/area.geojson" --ocean-boundaries "$OCEAN_SHP" --output "$DATA_DIR/layers/ocean.gpkg"
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

    {{ python }} "{{ scripts_dir }}/generate-config.py" \
        "$DATA_DIR/layers"/*.gpkg \
        --geojson "$DATA_DIR/area.geojson" \
        --output "$CONFIG_BASE" \
        --schemes-dir "{{ schemes_dir }}" \
        --scheme "$SCHEME" \
        --dem "$DATA_DIR/dem.tif" \
        --satellite "$DATA_DIR/satellite.tif" \
        "${CONFIG_ARGS[@]}"

    if [ -f "$CONFIG_OVERLAY" ]; then
        echo "   ✓ Applying overlay: $CONFIG_OVERLAY"
        {{ python }} "{{ scripts_dir }}/merge-config.py" "$CONFIG_BASE" "$CONFIG_OVERLAY" "$CONFIG_FINAL"
    else
        echo "   ℹ️  No overlay found (create with: {{ configs_dir }}/${LOCATION}-route-${ROUTE_NAME}-${SCHEME}-overlay.yaml)"
        cp "$CONFIG_BASE" "$CONFIG_FINAL"
    fi

    echo "🎨 Step 8: Rendering map..."
    OUTPUT_FILE="$OUTPUT_DIR/${LOCATION}-route-${ROUTE_NAME}-${SCHEME}.${FORMAT}"

    {{ python }} "{{ scripts_dir }}/generate-map.py" \
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
_build-map-gpx gpx scheme width height dpi format buffer text_title text_subtitle text_location text_stats text_units output_dir:
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

    if [ -z "${SCHEME//[[:space:]]/}" ]; then
        echo "❌ Color scheme is required and cannot be empty"
        echo "   Usage: just build-gpx path/to/route.gpx <scheme>"
        exit 1
    fi

    if [ ! -f "$GPX_PATH" ]; then
        echo "❌ GPX file not found: $GPX_PATH"
        exit 1
    fi

    ROUTE_NAME=$(basename "$GPX_PATH" .gpx | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g')
    LOCATION="route-${ROUTE_NAME}"
    DATA_DIR="{{ routes_dir }}/$ROUTE_NAME"
    OUTPUT_DIR="{{ output_dir }}/${ROUTE_NAME}-${SCHEME}"
    CONFIG_DIR="{{ configs_dir }}"

    echo "🗺️  Building GPX-derived route map ($SCHEME scheme)"
    echo "   GPX: $GPX_PATH"
    echo "   Output: $OUTPUT_DIR"
    echo ""

    mkdir -p "$DATA_DIR/layers"
    mkdir -p "$OUTPUT_DIR"
    mkdir -p "$CONFIG_DIR"

    echo "📍 Step 1: Deriving boundary from GPX..."
    ASPECT=$({{ python }} -c "print(round(${WIDTH} / ${HEIGHT}, 3))")
    {{ python }} "{{ scripts_dir }}/download-geojson.py" \
        --gpx "$GPX_PATH" \
        --buffer "$BUFFER" \
        --aspect-ratio "$ASPECT" \
        --output "$DATA_DIR/area.geojson"

    {{ python }} "{{ scripts_dir }}/validate-geojson.py" "$DATA_DIR/area.geojson"
    echo "   ✓ Boundary saved (aspect ratio: $ASPECT, buffer: ${BUFFER}km)"
    echo ""

    echo "🧭 Step 2: Route context diagnostics..."
    CONTEXT_JSON=$({{ python }} "{{ scripts_dir }}/analyze-route-context.py" \
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
    STRATEGY_JSON=$({{ python }} "{{ scripts_dir }}/calculate-area.py" "$DATA_DIR/area.geojson")
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
        {{ python }} "{{ scripts_dir }}/download-dem.py" --boundary "$DATA_DIR/area.geojson" --output "$DATA_DIR/dem.tif" --source "$DEM_SOURCE"
    else
        echo "   ✓ DEM exists"
    fi

    if ! ls "$DATA_DIR/layers"/*.gpkg 1> /dev/null 2>&1; then
        echo "   🗺️  Downloading layers (${OSM_SOURCE})..."
        {{ python }} "{{ scripts_dir }}/download-osm-layers.py" --geojson "$DATA_DIR/area.geojson" --output-dir "$DATA_DIR/layers" --cache-dir "{{ cache_dir }}" --natural-earth-cache-dir "{{ natural_earth_cache_dir }}" --source "$OSM_SOURCE"
    else
        echo "   ✓ Layers exist"
    fi

    if [ ! -f "$DATA_DIR/satellite.tif" ]; then
        echo "   🛰️  Downloading satellite imagery (zoom ${SAT_ZOOM})..."
        {{ python }} "{{ scripts_dir }}/download-satellite-image.py" --geojson "$DATA_DIR/area.geojson" --output "$DATA_DIR/satellite.tif" --zoom "$SAT_ZOOM" --dpi "$DPI"
    else
        echo "   ✓ Satellite imagery exists"
    fi

    OCEAN_SHP="{{ ocean_boundaries_dir }}/World_Seas_IHO_v3.shp"
    if [ -f "$OCEAN_SHP" ] && [ ! -f "$DATA_DIR/layers/ocean.gpkg" ]; then
        echo "   🌊 Preparing ocean layer..."
        {{ python }} "{{ scripts_dir }}/prepare-ocean-layer.py" --boundary "$DATA_DIR/area.geojson" --ocean-boundaries "$OCEAN_SHP" --output "$DATA_DIR/layers/ocean.gpkg"
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

    {{ python }} "{{ scripts_dir }}/generate-config.py" \
        "$DATA_DIR/layers"/*.gpkg \
        --geojson "$DATA_DIR/area.geojson" \
        --output "$CONFIG_BASE" \
        --schemes-dir "{{ schemes_dir }}" \
        --scheme "$SCHEME" \
        --dem "$DATA_DIR/dem.tif" \
        --satellite "$DATA_DIR/satellite.tif" \
        "${CONFIG_ARGS[@]}"

    if [ -f "$CONFIG_OVERLAY" ]; then
        echo "   ✓ Applying overlay: $CONFIG_OVERLAY"
        {{ python }} "{{ scripts_dir }}/merge-config.py" "$CONFIG_BASE" "$CONFIG_OVERLAY" "$CONFIG_FINAL"
    else
        cp "$CONFIG_BASE" "$CONFIG_FINAL"
    fi

    echo "🎨 Step 6: Rendering map..."
    OUTPUT_FILE="$OUTPUT_DIR/${ROUTE_NAME}-${SCHEME}.${FORMAT}"

    {{ python }} "{{ scripts_dir }}/generate-map.py" \
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

# ============================================================================
# Image Processing Tools
# ============================================================================

# Smart publish images (only copy if newer or missing)
[arg("pattern", long="pattern", help="File pattern to match (default: *.png)")]
[arg("force", long="force", help="Force copy all files (ignore timestamps)")]
publish input_dir=output_dir output_dir=publish_dir pattern="*.png" force="":
    #!/usr/bin/env bash
    set -euo pipefail
    echo "📤 Publishing images from {{ input_dir }} to {{ output_dir }}..."
    FORCE_ARG=""
    if [ "{{ force }}" = "true" ]; then
        FORCE_ARG="--force"
    fi
    {{ python }} "{{ scripts_dir }}/smart-publish-images.py" \
        --input "{{ input_dir }}" \
        --output "{{ output_dir }}" \
        --pattern "{{ pattern }}" \
        $FORCE_ARG

# Create resized examples for documentation
[arg("force", long="force", help="Force recreate all examples (ignore timestamps)")]
[arg("full_width", long="full-width", help="Width for full examples (default: 1200)")]
[arg("thumb_width", long="thumb-width", help="Width for thumbnails (default: 400)")]
create-examples input_dir=publish_dir examples_dir=workspace_dir full_width="1200" thumb_width="400" force="":
    #!/usr/bin/env bash
    set -euo pipefail
    echo "📸 Creating examples from {{ input_dir }}..."
    mkdir -p "{{ examples_dir }}/full" "{{ examples_dir }}/thumbnails"

    FULL_DIR="{{ examples_dir }}/full"
    THUMB_DIR="{{ examples_dir }}/thumbnails"

    UPDATED=0
    SKIPPED=0
    FORCE_FLAG="{{ force }}"

    while IFS= read -r src_file; do
        [ -f "$src_file" ] || continue
        basename_file=$(basename "$src_file")
        full_target="$FULL_DIR/$basename_file"
        thumb_target="$THUMB_DIR/$basename_file"

        need_full=false
        need_thumb=false

        if [ "$FORCE_FLAG" = "true" ] || [ ! -f "$full_target" ]; then
            need_full=true
        else
            # Check if source is newer
            src_mtime=$(stat -f%m "$src_file" 2>/dev/null || stat -c%Y "$src_file")
            full_mtime=$(stat -f%m "$full_target" 2>/dev/null || stat -c%Y "$full_target")
            if [ "$src_mtime" -gt "$full_mtime" ]; then
                need_full=true
            fi
        fi

        if [ "$FORCE_FLAG" = "true" ] || [ ! -f "$thumb_target" ]; then
            need_thumb=true
        else
            # Check if source is newer
            src_mtime=$(stat -f%m "$src_file" 2>/dev/null || stat -c%Y "$src_file")
            thumb_mtime=$(stat -f%m "$thumb_target" 2>/dev/null || stat -c%Y "$thumb_target")
            if [ "$src_mtime" -gt "$thumb_mtime" ]; then
                need_thumb=true
            fi
        fi

        if [ "$need_full" = false ] && [ "$need_thumb" = false ]; then
            SKIPPED=$((SKIPPED + 1))
            continue
        fi

        temp_dir=$(mktemp -d)
        cp "$src_file" "$temp_dir/$basename_file"

        if [ "$need_full" = true ]; then
            {{ python }} "{{ scripts_dir }}/resize-images.py" \
                --input "$temp_dir" \
                --output "$FULL_DIR" \
                --width {{ full_width }} >/dev/null
        fi

        if [ "$need_thumb" = true ]; then
            {{ python }} "{{ scripts_dir }}/resize-images.py" \
                --input "$temp_dir" \
                --output "$THUMB_DIR" \
                --width {{ thumb_width }} >/dev/null
        fi

        rm -rf "$temp_dir"
        echo "  ✓ $basename_file"
        UPDATED=$((UPDATED + 1))
    done < <(find "{{ input_dir }}" -maxdepth 1 -type f -name "*.png" | sort)

    echo ""
    echo "✓ Examples created successfully"
    echo "  Updated: $UPDATED"
    echo "  Skipped (up-to-date): $SKIPPED"
    echo "  Full examples: $FULL_DIR/"
    echo "  Thumbnails: $THUMB_DIR/"

# Resize images to specific width
[arg("width", long="width", help="Target width in pixels")]
resize input_dir output_dir width="1200":
    @echo "🔄 Resizing images from {{ input_dir }} to {{ width }}px wide..."
    @{{ python }} "{{ scripts_dir }}/resize-images.py" \
        --input "{{ input_dir }}" \
        --output "{{ output_dir }}" \
        --width {{ width }}

# Add text labels to images
[arg("background", long="background", help="Background color (e.g., white, #ffffff, or none for transparent)")]
[arg("label", long="label", help="Fixed label text for all images")]
[arg("label_pattern", long="label-pattern", help="Label pattern with {scheme} or {filename}")]
[arg("position", long="position", help="Label position: upper-right, upper-left, lower-right, lower-left")]
[arg("text_color", long="text-color", help="Text color (default: black)")]
add-labels input_dir output_dir label="" label_pattern="{scheme}" position="upper-right" background="white" text_color="black":
    @echo "🏷️  Adding labels to images..."
    @{{ python }} "{{ scripts_dir }}/add-image-label.py" \
        --input "{{ input_dir }}" \
        --output "{{ output_dir }}" \
        {{ if label != "" { "--label \"" + label + "\"" } else { "" } }} \
        {{ if label_pattern != "" { "--label-pattern \"" + label_pattern + "\"" } else { "" } }} \
        --position "{{ position }}" \
        --background "{{ background }}" \
        --text-color "{{ text_color }}"

# Create a montage grid from images
[arg("add_labels", long="add-labels", help="Add labels to each image (use 'true')")]
[arg("pattern", long="pattern", help="Glob pattern to filter images (e.g., 'maple-ridge-bc-*')")]
[arg("label_pattern", long="label-pattern", help="Label pattern with {scheme} or {filename}")]
[arg("cols", long="cols", help="Number of columns or 'auto' for optimal layout")]
[arg("spacing", long="spacing", help="Spacing between images in pixels")]
create-montage input_dir output_file cols="4" spacing="10" add_labels="" label_pattern="{scheme}" pattern="*":
    @echo "🖼️  Creating montage from {{ input_dir }}..."
    @{{ python }} "{{ scripts_dir }}/create-image-montage.py" \
        --input "{{ input_dir }}" \
        --output "{{ output_file }}" \
        --cols {{ cols }} \
        --spacing {{ spacing }} \
        {{ if add_labels == "true" { "--add-labels" } else { "" } }} \
        {{ if label_pattern != "" { "--label-pattern \"" + label_pattern + "\"" } else { "" } }} \
        --pattern "{{ pattern }}"

# Create a multi-page PDF from images
[arg("fit_mode", long="fit-mode", help="How to fit images: contain, fill, actual")]
[arg("page_size", long="page-size", help="Page size: letter, legal, tabloid, a4, a3")]
[arg("dpi", long="dpi", help="Resolution in DPI (150-300 recommended, default: 150)")]
create-pdf input_dir output_file dpi="150" page_size="letter" fit_mode="contain":
    @echo "📄 Creating PDF from {{ input_dir }}..."
    @{{ python }} "{{ scripts_dir }}/create-pdf-from-images.py" \
        --input "{{ input_dir }}" \
        --output "{{ output_file }}" \
        --dpi {{ dpi }} \
        --page-size "{{ page_size }}" \
        --fit-mode "{{ fit_mode }}"
