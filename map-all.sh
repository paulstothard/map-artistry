#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# map-all.sh – one-shot driver for the “artistic map” tool-chain
#
# Runs the artistic‑map pipeline using plain Bash with timestamp/existence checks.
# ---------------------------------------------------------------------------

set -euo pipefail

##### --- Defaults --------------------------------------------------------
DESIGN="coral"
BUFFER_KM=2
WIDTH_IN=12
HEIGHT_IN=12
DPI=300
FORMAT="png" # output image format (png, jpg, or pdf)
ZOOM=14      # satellite zoom level
# Which steps to run; comma‑separated list or "all"
RUN_STEPS="all"

##### --- CLI ---------------------------------------------------------------
usage() {
    cat <<EOF
Usage: $0 "PLACE NAME" [OUT_DIR] [options]

Positional args
  PLACE NAME      e.g. "Edmonton, AB"
  OUT_DIR         Folder to write results (default: output)
  STEPS           Optional: comma‑separated steps list
                  (geojson,dem,layers,satellite,config,map)

Optional flags
  -b, --buffer KM         Buffer distance around place   (default: $BUFFER_KM)
  -w, --width  INCHES     Output image width in inches   (default: $WIDTH_IN)
  -h, --height INCHES     Output image height in inches  (default: $HEIGHT_IN)
  -d, --dpi    DPI        Output resolution              (default: $DPI)
  -f, --format png|jpg|pdf    Output image format         (default: $FORMAT)
  -s, --scheme NAME       Colour scheme / design         (default: $DESIGN)
  -z, --zoom   LEVEL      Satellite zoom level           (default: $ZOOM)
  -t, --steps LIST        Comma‑sep list of steps to run
                          (geojson,dem,layers,satellite,config,map)
                          (default: all)
  --force                Re-run every step even if outputs exist
  --help                 Show this help text
EOF
    exit "${1:-0}"
}

# ---- tiny getopt helper ---------------------------------------------------
force=false
PLACE=""
DIR="output"

while [[ $# -gt 0 ]]; do
    case "$1" in
    -b | --buffer)
        BUFFER_KM="$2"
        shift 2
        ;;
    -w | --width)
        WIDTH_IN="$2"
        shift 2
        ;;
    -h | --height)
        HEIGHT_IN="$2"
        shift 2
        ;;
    -d | --dpi)
        DPI="$2"
        shift 2
        ;;
    -f | --format)
        FORMAT="$2"
        shift 2
        ;;
    -s | --scheme)
        DESIGN="$2"
        shift 2
        ;;
    -z | --zoom)
        ZOOM="$2"
        shift 2
        ;;
    -t | --steps)
        RUN_STEPS="$2"
        shift 2
        ;;
    --force)
        force=true
        shift
        ;;
    --help) usage 0 ;;
    --)
        shift
        break
        ;;
    --*)
        echo "Unknown option $1"
        usage 1
        ;;
    -*)
        echo "Unknown option $1"
        usage 1
        ;;
    *) # positional
        if [[ -z $PLACE ]]; then
            PLACE="$1" # first positional → PLACE
        elif [[ $DIR == "output" ]]; then
            DIR="$1" # second positional → OUT_DIR
        elif [[ $RUN_STEPS == "all" ]]; then
            RUN_STEPS="$1" # third positional → steps list
        else
            echo "Too many positional arguments"
            usage 1
        fi
        shift
        ;;
    esac
done

[[ -z $PLACE ]] && {
    echo "Error: PLACE is required"
    usage 1
}

echo "🗺️  Generating map for:  $PLACE"
echo "📂 Output directory:      $DIR"
echo "⚙️  Steps to run:         $RUN_STEPS"
mkdir -p "$DIR" "$DIR/layers"

##### --- Helpers -----------------------------------------------------------
run() {
    echo "+ $*"
    "$@"
}

skip() { echo "✔ $1 already exists – skipping"; }

# If \$force is true, always run; otherwise run only when \$output is missing
step() {
    local output="$1"
    shift
    if $force || [[ ! -e $output ]]; then
        "$@"
    else
        skip "$output"
    fi
}

# Return 0 (true) if the named step is requested in RUN_STEPS
should_run_step() {
    local step="$1"
    [[ $RUN_STEPS == "all" ]] && return 0
    IFS=',' read -ra sel <<<"$RUN_STEPS"
    for s in "${sel[@]}"; do
        [[ $s == "$step" ]] && return 0
    done
    return 1
}

##### --- 1. Boundary GeoJSON ----------------------------------------------
if should_run_step "geojson"; then
    step "$DIR/area.geojson" \
        run python scripts/download-geojson.py "$PLACE" \
        --buffer "$BUFFER_KM" \
        --output "$DIR/area.geojson"
fi

##### --- 2. DEM ------------------------------------------------------------
if should_run_step "dem"; then
    step "$DIR/dem.tif" \
        run python scripts/download-dem.py \
        --boundary "$DIR/area.geojson" \
        --output "$DIR/dem.tif"
fi

##### --- 3. OSM Layers -----------------------------------------------------
if should_run_step "layers"; then
    # At least one *.gpkg must be present to deem this step complete
    if $force || ! compgen -G "$DIR/layers/*.gpkg" >/dev/null; then
        run python scripts/download-osm-layers.py \
            --geojson "$DIR/area.geojson" \
            --output-dir "$DIR/layers"
    else
        skip "$DIR/layers/*.gpkg"
    fi
fi

##### --- 4. Satellite ------------------------------------------------------
if should_run_step "satellite"; then
    step "$DIR/satellite.tif" \
        run python scripts/download-satellite-image.py \
        --geojson "$DIR/area.geojson" \
        --output "$DIR/satellite.tif" \
        --zoom "$ZOOM" \
        --dpi "$DPI"
fi

##### --- 5. Config YAML ----------------------------------------------------
if should_run_step "config"; then
    step "$DIR/config.yaml" \
        run python scripts/generate-config.py "$DIR"/layers/*.gpkg \
        --output "$DIR/config.yaml" \
        --geojson "$DIR/area.geojson" \
        --satellite "$DIR/satellite.tif" \
        --dem "$DIR/dem.tif" \
        --scheme "$DESIGN"
fi

##### --- 6. Final Map ------------------------------------------------------
if should_run_step "map"; then
    step "$DIR/map.$FORMAT" \
        run python scripts/generate-map.py \
        -g "$DIR/area.geojson" \
        "$DIR/config.yaml" \
        --output "$DIR/map.$FORMAT" \
        --width "$WIDTH_IN" \
        --height "$HEIGHT_IN" \
        --dpi "$DPI" \
        --format "$FORMAT"
fi

echo "🎉 Done!  Map written to $DIR/map.$FORMAT"
