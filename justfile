# ============================================================================
# Map Artistry - Justfile
# ============================================================================
# Automated build recipes for generating artistic maps of cities using
# the map-pipeline.sh workflow. Supports multiple color schemes:
#   - coral: Warm coral/red background with white water features
#   - river_runs_red: Black background with red water features
#   - blue-yellow: Blue background with yellow water features
#   - natural: Natural earth tones with green/brown terrain
#   - moon: Lunar grayscale with no water (shows seafloor topology)
#   - satellite: Satellite imagery with terrain overlay
#
# Usage:
#   just                    # Build all maps for both cities
#   just edmonton-coral     # Build single map variant
#   just clean              # Remove all output
#   just publish            # Copy final maps to publish/ folder
# ============================================================================

# Map dimensions and settings for Edmonton
# -w, --width: Output map width in inches
# -h, --height: Output map height in inches
# -b, --buffer: Buffer distance around city center in kilometers
# -d, --dpi: Output resolution (dots per inch)
# -f, --format: Output file format (png, jpg, or pdf)
# -z, --zoom: Zoom level for terrain data (lower = broader area)
# -z (satellite): Higher zoom for satellite imagery (higher = more detail)

EDMONTON_W := "24"
EDMONTON_H := "24"
EDMONTON_B := "5"
EDMONTON_DPI := "600"
EDMONTON_FMT := "png"

EDMONTON_Z := "5"
EDMONTON_Z_SAT := "17"

# Map dimensions and settings for Victoria
VICTORIA_W := "24"
VICTORIA_H := "24"
VICTORIA_B := "55"
VICTORIA_DPI := "600"
VICTORIA_FMT := "png"

VICTORIA_Z := "5"
VICTORIA_Z_SAT := "16"

# ============================================================================
# Default Recipe - Build All Maps
# ============================================================================
# Generates all map variants for both Edmonton and Victoria.
# Builds in dependency order to reuse shared data (DEM, OSM layers).
#
# Build order:
#   1. Edmonton coral (downloads all base data)
#   2. Copy shared Edmonton data to other variant folders
#   3. Edmonton river_runs_red, blue-yellow, natural, moon, satellite (use shared data)
#   4. Victoria coral (downloads all base data)
#   5. Copy shared Victoria data
#   6. Victoria river_runs_red, natural, moon, satellite (use shared data)

all: edmonton-coral copy-edmonton-shared edmonton-river-runs-red edmonton-blue-yellow edmonton-natural edmonton-moon victoria-coral copy-victoria-shared victoria-river-runs-red victoria-natural victoria-moon edmonton-satellite victoria-satellite

# ============================================================================
# Edmonton Maps
# ============================================================================

# Generate Edmonton map with coral color scheme
# Downloads: boundary GeoJSON, DEM, OSM layers, satellite imagery
# Output: output/edmonton-coral/map.pdf
edmonton-coral:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-coral -s coral -b {{EDMONTON_B}} -w {{EDMONTON_W}} -h {{EDMONTON_H}} -z {{EDMONTON_Z}} -d {{EDMONTON_DPI}} -f {{EDMONTON_FMT}}

# Copy shared base data from coral to other Edmonton variants
# Copies: DEM, OSM layers, boundary data (excludes config.yaml, map.*, satellite.tif)
# This avoids re-downloading the same base data for each color scheme
copy-edmonton-shared:
    mkdir -p output/edmonton-river-runs-red output/edmonton-blue-yellow output/edmonton-natural output/edmonton-moon output/edmonton-satellite
    rsync -av --exclude='config.yaml' --exclude='map.*' --exclude='.DS_Store' output/edmonton-coral/ output/edmonton-river-runs-red/ output/edmonton-blue-yellow/ output/edmonton-natural/ output/edmonton-moon/
    rsync -av --exclude='config.yaml' --exclude='map.*' --exclude='satellite.tif' --exclude='.DS_Store' output/edmonton-coral/ output/edmonton-satellite/

# Generate Edmonton map with river_runs_red color scheme (black bg, red water)
# Uses shared data from edmonton-coral, only generates new config and map
edmonton-river-runs-red:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-river-runs-red -s river_runs_red -b {{EDMONTON_B}} -w {{EDMONTON_W}} -h {{EDMONTON_H}} -z {{EDMONTON_Z}} -d {{EDMONTON_DPI}} -f {{EDMONTON_FMT}}

# Generate Edmonton map with blue-yellow color scheme
# Uses shared data from edmonton-coral, only generates new config and map
edmonton-blue-yellow:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-blue-yellow -s blue-yellow -b {{EDMONTON_B}} -w {{EDMONTON_W}} -h {{EDMONTON_H}} -z {{EDMONTON_Z}} -d {{EDMONTON_DPI}} -f {{EDMONTON_FMT}}

# Generate Edmonton map with natural color scheme (earth tones)
# Uses shared data from edmonton-coral, only generates new config and map
edmonton-natural:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-natural -s natural -b {{EDMONTON_B}} -w {{EDMONTON_W}} -h {{EDMONTON_H}} -z {{EDMONTON_Z}} -d {{EDMONTON_DPI}} -f {{EDMONTON_FMT}}

# Generate Edmonton map with moon color scheme (lunar grayscale, no water)
# Uses shared data from edmonton-coral, only generates new config and map
edmonton-moon:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-moon -s moon -b {{EDMONTON_B}} -w {{EDMONTON_W}} -h {{EDMONTON_H}} -z {{EDMONTON_Z}} -d {{EDMONTON_DPI}} -f {{EDMONTON_FMT}}

# Generate Edmonton map with satellite imagery
# Uses higher zoom level for satellite detail
edmonton-satellite:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-satellite -s satellite -b {{EDMONTON_B}} -w {{EDMONTON_W}} -h {{EDMONTON_H}} -z {{EDMONTON_Z_SAT}} -d {{EDMONTON_DPI}} -f {{EDMONTON_FMT}}

# ============================================================================
# Victoria Maps
# ============================================================================

# Generate Victoria map with coral color scheme
# Downloads: boundary GeoJSON, DEM, OSM layers, satellite imagery, ocean data
# Output: output/victoria-coral/map.pdf
# Note: Uses --with-ocean flag for coastal areas
victoria-coral:
    ./map-pipeline.sh "Victoria, BC" output/victoria-coral -s coral -b {{VICTORIA_B}} -w {{VICTORIA_W}} -h {{VICTORIA_H}} -z {{VICTORIA_Z}} -d {{VICTORIA_DPI}} -f {{VICTORIA_FMT}} --with-ocean

# Copy shared base data from coral to other Victoria variants
# Copies: DEM, OSM layers, ocean data, boundary data
# Excludes: config.yaml, map.*, satellite.tif
copy-victoria-shared:
    mkdir -p output/victoria-river-runs-red output/victoria-natural output/victoria-moon output/victoria-satellite
    rsync -av --exclude='config.yaml' --exclude='map.*' --exclude='.DS_Store' output/victoria-coral/ output/victoria-river-runs-red/ output/victoria-natural/ output/victoria-moon/
    rsync -av --exclude='config.yaml' --exclude='map.*' --exclude='satellite.tif' --exclude='.DS_Store' output/victoria-coral/ output/victoria-satellite/

# Generate Victoria map with river_runs_red color scheme
# Uses shared data from victoria-coral
victoria-river-runs-red:
    ./map-pipeline.sh "Victoria, BC" output/victoria-river-runs-red -s river_runs_red -b {{VICTORIA_B}} -w {{VICTORIA_W}} -h {{VICTORIA_H}} -z {{VICTORIA_Z}} -d {{VICTORIA_DPI}} -f {{VICTORIA_FMT}} --with-ocean

# Generate Victoria map with natural color scheme (earth tones)
# Uses shared data from victoria-coral
victoria-natural:
    ./map-pipeline.sh "Victoria, BC" output/victoria-natural -s natural -b {{VICTORIA_B}} -w {{VICTORIA_W}} -h {{VICTORIA_H}} -z {{VICTORIA_Z}} -d {{VICTORIA_DPI}} -f {{VICTORIA_FMT}} --with-ocean

# Generate Victoria map with moon color scheme (lunar grayscale, no water)
# Uses shared data from victoria-coral, shows seafloor topology
victoria-moon:
    ./map-pipeline.sh "Victoria, BC" output/victoria-moon -s moon -b {{VICTORIA_B}} -w {{VICTORIA_W}} -h {{VICTORIA_H}} -z {{VICTORIA_Z}} -d {{VICTORIA_DPI}} -f {{VICTORIA_FMT}} --with-ocean

# Generate Victoria map with satellite imagery
# Uses higher zoom level for satellite detail
victoria-satellite:
    ./map-pipeline.sh "Victoria, BC" output/victoria-satellite -s satellite -b {{VICTORIA_B}} -w {{VICTORIA_W}} -h {{VICTORIA_H}} -z {{VICTORIA_Z_SAT}} -d {{VICTORIA_DPI}} -f {{VICTORIA_FMT}} --with-ocean

# ============================================================================
# Utility Recipes
# ============================================================================

# Publish all generated maps to publish/ folder
# Finds all map.* files in output/ subdirectories and copies them
# to publish/ with folder name as prefix (e.g., edmonton-coral.pdf)
publish:
    mkdir -p publish
    find output -name "map.*" -type f | while read -r mapfile; do \
        folder=$(basename $(dirname "$mapfile")); \
        extension="${mapfile##*.}"; \
        cp "$mapfile" "publish/${folder}.${extension}"; \
    done
    @echo "Published maps to publish/ folder"

# Remove all output directories and generated files
# WARNING: This deletes all generated maps and downloaded data
clean:
    rm -rf output

# Remove only the final map images (map.*) from all output directories
# Keeps downloaded data (DEM, OSM layers, configs) for faster rebuilds
clean-maps:
    find output -type f \( -name "map.*" \) -delete

# Remove final maps and config files
# Keeps downloaded base data (DEM, OSM layers, satellite imagery)
# Use this to regenerate maps with different color schemes
clean-maps-and-configs:
    find output -type f \( -name "map.*" -o -name "config.yaml" \) -delete