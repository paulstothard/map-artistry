#!/usr/bin/env bash
set -euo pipefail

REGIONS=(
  "Banff, AB"
  "British Columbia"
  "Cape Town, South Africa"
  "Edmonton, AB"
  "Iceland"
  "Oahu, HI"
  "Patagonia"
  "San Francisco, CA"
  "Vancouver, BC"
  "Vancouver Island, BC"
  "Vestland, Norway"
)

WIDTH=24
HEIGHT=24
DPI=150
FORMAT="png"
FULL_WIDTH=1200
THUMBNAIL_WIDTH=400
FORCE=false

# Route example definitions (grouped for readability)
EDMONTON_ROUTE_REGION="Edmonton, AB"
EDMONTON_ROUTE_GPX_FILE="edmonton-110km.gpx"
EDMONTON_ROUTE_TEXT_TITLE="EDMONTON LOOP"
EDMONTON_ROUTE_TEXT_SUBTITLE="SUMMER TRAINING RIDE"
EDMONTON_ROUTE_TEXT_STATS="108 KM||DISTANCE;;715 M||ELEV GAIN"

GPX_ONLY_ROUTE_GPX_FILE="edmonton-50km.gpx"
GPX_ONLY_TEXT_TITLE="RIVER VALLEY LOOP"
GPX_ONLY_TEXT_SUBTITLE="GPX-DERIVED REGION"
GPX_ONLY_TEXT_STATS="48 KM||DISTANCE;;326 M||ELEV GAIN"

ALKI_ROUTE_GPX_FILE="Alki_Three_Tree_Point_Normandy_Park_Lake_Washington.gpx"
ALKI_ROUTE_TEXT_TITLE="ALKI, THREE TREE POINT, NORMANDY PARK, LAKE WASHINGTON"
ALKI_ROUTE_TEXT_SUBTITLE="PUGET SOUND COASTAL LOOP"
ALKI_ROUTE_TEXT_STATS="51.0 MI||DISTANCE;;2,690 FT||ELEV GAIN"

BOSTON_ROUTE_GPX_FILE="Boston-Emerald_Necklace_Bicycle_Adventure.gpx"
BOSTON_ROUTE_TEXT_TITLE="BOSTON-EMERALD NECKLACE BICYCLE ADVENTURE"
BOSTON_ROUTE_TEXT_SUBTITLE="OLMSTED PARKS TOUR"
BOSTON_ROUTE_TEXT_STATS="38.5 MI||DISTANCE;;1,260 FT||ELEV GAIN"

usage() {
  cat <<'EOF'
Usage: ./generate-example-maps.sh [options]

Options:
  -f, --force    Re-render maps and rebuild publish/examples assets
  -h, --help     Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -f | --force)
      FORCE=true
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
  shift
done

[ -d "venv" ] && source venv/bin/activate

PYTHON_BIN="python3"
[ -x "venv/bin/python" ] && PYTHON_BIN="venv/bin/python"

get_just_var() {
  local var_name="$1"
  local fallback="$2"
  local value

  value=$(just --evaluate "$var_name" 2>/dev/null || true)
  if [ -z "${value//[[:space:]]/}" ]; then
    echo "$fallback"
  else
    echo "$value"
  fi
}

SCRIPTS_DIR=$(get_just_var "scripts_dir" "scripts")
DOWNLOADS_DIR=$(get_just_var "downloads_dir" "downloads")
REGIONS_DIR=$(get_just_var "regions_dir" "$DOWNLOADS_DIR/regions")
ROUTES_DIR=$(get_just_var "routes_dir" "$DOWNLOADS_DIR/routes")
CONFIGS_DIR=$(get_just_var "configs_dir" "configs")
OUTPUT_DIR=$(get_just_var "output_dir" "output")

PUBLISH_DIR="publish"
EXAMPLES_DIR="examples"
EXAMPLES_FULL_DIR="$EXAMPLES_DIR/full"
EXAMPLES_THUMB_DIR="$EXAMPLES_DIR/thumbnails"
CYCLING_ROUTES_DIR="$DOWNLOADS_DIR/cycling-routes"

EDMONTON_ROUTE_GPX="$CYCLING_ROUTES_DIR/$EDMONTON_ROUTE_GPX_FILE"
GPX_ONLY_ROUTE_GPX="$CYCLING_ROUTES_DIR/$GPX_ONLY_ROUTE_GPX_FILE"
ALKI_ROUTE_GPX="$CYCLING_ROUTES_DIR/$ALKI_ROUTE_GPX_FILE"
BOSTON_ROUTE_GPX="$CYCLING_ROUTES_DIR/$BOSTON_ROUTE_GPX_FILE"

# Get schemes dynamically
SCHEMES=$(just schemes 2>/dev/null)

slugify_region() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | sed 's/[, ]/-/g' | sed 's/--*/-/g'
}

slugify_route() {
  basename "$1" .gpx | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g'
}

if [ ! -f "$EDMONTON_ROUTE_GPX" ]; then
  echo "❌ Missing GPX for Edmonton route examples: $EDMONTON_ROUTE_GPX"
  exit 1
fi

if [ ! -f "$GPX_ONLY_ROUTE_GPX" ]; then
  echo "❌ Missing GPX for GPX-only examples: $GPX_ONLY_ROUTE_GPX"
  exit 1
fi

if [ ! -f "$ALKI_ROUTE_GPX" ]; then
  echo "❌ Missing GPX for Alki route examples: $ALKI_ROUTE_GPX"
  exit 1
fi

if [ ! -f "$BOSTON_ROUTE_GPX" ]; then
  echo "❌ Missing GPX for Boston route examples: $BOSTON_ROUTE_GPX"
  exit 1
fi

EDMONTON_ROUTE_REGION_SLUG=$(slugify_region "$EDMONTON_ROUTE_REGION")
EDMONTON_ROUTE_SLUG=$(slugify_route "$EDMONTON_ROUTE_GPX")
GPX_ONLY_ROUTE_SLUG=$(slugify_route "$GPX_ONLY_ROUTE_GPX")
ALKI_ROUTE_SLUG=$(slugify_route "$ALKI_ROUTE_GPX")
BOSTON_ROUTE_SLUG=$(slugify_route "$BOSTON_ROUTE_GPX")

echo "Checking existing maps..."
echo ""

# Pre-flight check: determine what needs to be generated
TOTAL=0
EXISTING=0
NEEDED=0
declare -a NEEDED_MAPS

# 1) Standard region examples
for region in "${REGIONS[@]}"; do
  location=$(slugify_region "$region")
  for scheme in $SCHEMES; do
    TOTAL=$((TOTAL + 1))
    output_file="$OUTPUT_DIR/${location}-${scheme}/${location}-${scheme}.${FORMAT}"

    if [ -f "$output_file" ]; then
      EXISTING=$((EXISTING + 1))
      if [ "$FORCE" = true ]; then
        NEEDED=$((NEEDED + 1))
        NEEDED_MAPS+=("region|$region|$scheme")
      fi
    else
      NEEDED=$((NEEDED + 1))
      NEEDED_MAPS+=("region|$region|$scheme")
    fi
  done
done

# 2) Edmonton + longest GPX route examples (all schemes)
for scheme in $SCHEMES; do
  TOTAL=$((TOTAL + 1))
  output_file="$OUTPUT_DIR/${EDMONTON_ROUTE_REGION_SLUG}-route-${EDMONTON_ROUTE_SLUG}-${scheme}/${EDMONTON_ROUTE_REGION_SLUG}-route-${EDMONTON_ROUTE_SLUG}-${scheme}.${FORMAT}"

  if [ -f "$output_file" ]; then
    EXISTING=$((EXISTING + 1))
    if [ "$FORCE" = true ]; then
      NEEDED=$((NEEDED + 1))
      NEEDED_MAPS+=("route-region|$EDMONTON_ROUTE_REGION|$EDMONTON_ROUTE_GPX|$scheme")
    fi
  else
    NEEDED=$((NEEDED + 1))
    NEEDED_MAPS+=("route-region|$EDMONTON_ROUTE_REGION|$EDMONTON_ROUTE_GPX|$scheme")
  fi
done

# 3) GPX-only route examples (all schemes)
for scheme in $SCHEMES; do
  TOTAL=$((TOTAL + 1))
  output_file="$OUTPUT_DIR/${GPX_ONLY_ROUTE_SLUG}-${scheme}/${GPX_ONLY_ROUTE_SLUG}-${scheme}.${FORMAT}"

  if [ -f "$output_file" ]; then
    EXISTING=$((EXISTING + 1))
    if [ "$FORCE" = true ]; then
      NEEDED=$((NEEDED + 1))
      NEEDED_MAPS+=("route-gpx-only|$GPX_ONLY_ROUTE_GPX|$scheme")
    fi
  else
    NEEDED=$((NEEDED + 1))
    NEEDED_MAPS+=("route-gpx-only|$GPX_ONLY_ROUTE_GPX|$scheme")
  fi
done

# 4) Alki route examples (all schemes)
for scheme in $SCHEMES; do
  TOTAL=$((TOTAL + 1))
  output_file="$OUTPUT_DIR/${ALKI_ROUTE_SLUG}-${scheme}/${ALKI_ROUTE_SLUG}-${scheme}.${FORMAT}"

  if [ -f "$output_file" ]; then
    EXISTING=$((EXISTING + 1))
    if [ "$FORCE" = true ]; then
      NEEDED=$((NEEDED + 1))
      NEEDED_MAPS+=("route-gpx-only|$ALKI_ROUTE_GPX|$scheme")
    fi
  else
    NEEDED=$((NEEDED + 1))
    NEEDED_MAPS+=("route-gpx-only|$ALKI_ROUTE_GPX|$scheme")
  fi
done

# 5) Boston route examples (all schemes)
for scheme in $SCHEMES; do
  TOTAL=$((TOTAL + 1))
  output_file="$OUTPUT_DIR/${BOSTON_ROUTE_SLUG}-${scheme}/${BOSTON_ROUTE_SLUG}-${scheme}.${FORMAT}"

  if [ -f "$output_file" ]; then
    EXISTING=$((EXISTING + 1))
    if [ "$FORCE" = true ]; then
      NEEDED=$((NEEDED + 1))
      NEEDED_MAPS+=("route-gpx-only|$BOSTON_ROUTE_GPX|$scheme")
    fi
  else
    NEEDED=$((NEEDED + 1))
    NEEDED_MAPS+=("route-gpx-only|$BOSTON_ROUTE_GPX|$scheme")
  fi
done

echo "📊 Map Generation Summary:"
echo "   Total maps: $TOTAL"
echo "   Already exist: $EXISTING"
echo "   Need generation: $NEEDED"
echo "   Force mode: $FORCE"
echo ""

if [ $NEEDED -gt 0 ]; then
  echo "Maps to generate:"
  for entry in "${NEEDED_MAPS[@]}"; do
    IFS='|' read -r mode a b c <<<"$entry"
    case "$mode" in
      region)
        echo "  • $a — $b"
        ;;
      route-region)
        echo "  • $a + $(basename "$b") — $c"
        ;;
      route-gpx-only)
        echo "  • GPX-only $(basename "$a") — $b"
        ;;
    esac
  done

  echo ""
  echo "  Settings: ${WIDTH}x${HEIGHT} inches @ ${DPI} DPI, format: $FORMAT"
  echo "  Force assets : $FORCE"
  echo "  Data downloads : $REGIONS_DIR + $ROUTES_DIR"
  echo "  Configs        : $CONFIGS_DIR/"
  echo "  Maps           : $OUTPUT_DIR/"
  echo ""
  echo "See README.md for more information."
  echo ""
  read -p "Proceed with generating $NEEDED maps? (y/N) " -n 1 -r
  echo

  if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""

    # 1) Standard region examples
    for region in "${REGIONS[@]}"; do
      location=$(slugify_region "$region")
      for scheme in $SCHEMES; do
        output_file="$OUTPUT_DIR/${location}-${scheme}/${location}-${scheme}.${FORMAT}"

        if [ "$FORCE" != true ] && [ -f "$output_file" ]; then
          echo "⏭ $region — $scheme"
          echo "   Skipping existing output: $output_file"
          continue
        fi

        echo "▶ $region — $scheme"

        build_args=(--width "$WIDTH" --height "$HEIGHT" --dpi "$DPI" --format "$FORMAT")
        just build "${build_args[@]}" "$region" "$scheme"
      done
    done

    # 2) Edmonton + longest GPX route examples
    for scheme in $SCHEMES; do
      output_file="$OUTPUT_DIR/${EDMONTON_ROUTE_REGION_SLUG}-route-${EDMONTON_ROUTE_SLUG}-${scheme}/${EDMONTON_ROUTE_REGION_SLUG}-route-${EDMONTON_ROUTE_SLUG}-${scheme}.${FORMAT}"

      if [ "$FORCE" != true ] && [ -f "$output_file" ]; then
        echo "⏭ ${EDMONTON_ROUTE_REGION} + $(basename "$EDMONTON_ROUTE_GPX") — $scheme"
        echo "   Skipping existing output: $output_file"
        continue
      fi

      echo "▶ ${EDMONTON_ROUTE_REGION} + $(basename "$EDMONTON_ROUTE_GPX") — $scheme"
      build_args=(--width "$WIDTH" --height "$HEIGHT" --dpi "$DPI" --format "$FORMAT")
      just build-route "${build_args[@]}" \
        --text-title "$EDMONTON_ROUTE_TEXT_TITLE" \
        --text-subtitle "$EDMONTON_ROUTE_TEXT_SUBTITLE" \
        --text-location "$EDMONTON_ROUTE_REGION" \
        --text-stats "$EDMONTON_ROUTE_TEXT_STATS" \
        "$EDMONTON_ROUTE_REGION" "$EDMONTON_ROUTE_GPX" "$scheme"
    done

    # 3) GPX-only route examples
    for scheme in $SCHEMES; do
      output_file="$OUTPUT_DIR/${GPX_ONLY_ROUTE_SLUG}-${scheme}/${GPX_ONLY_ROUTE_SLUG}-${scheme}.${FORMAT}"

      if [ "$FORCE" != true ] && [ -f "$output_file" ]; then
        echo "⏭ GPX-only $(basename "$GPX_ONLY_ROUTE_GPX") — $scheme"
        echo "   Skipping existing output: $output_file"
        continue
      fi

      echo "▶ GPX-only $(basename "$GPX_ONLY_ROUTE_GPX") — $scheme"
      build_args=(--width "$WIDTH" --height "$HEIGHT" --dpi "$DPI" --format "$FORMAT")
      just build-gpx "${build_args[@]}" \
        --buffer-km 1 \
        --text-title "$GPX_ONLY_TEXT_TITLE" \
        --text-subtitle "$GPX_ONLY_TEXT_SUBTITLE" \
        --text-stats "$GPX_ONLY_TEXT_STATS" \
        "$GPX_ONLY_ROUTE_GPX" "$scheme"
    done

    # 4) Alki route examples
    for scheme in $SCHEMES; do
      output_file="$OUTPUT_DIR/${ALKI_ROUTE_SLUG}-${scheme}/${ALKI_ROUTE_SLUG}-${scheme}.${FORMAT}"

      if [ "$FORCE" != true ] && [ -f "$output_file" ]; then
        echo "⏭ GPX-only $(basename "$ALKI_ROUTE_GPX") — $scheme"
        echo "   Skipping existing output: $output_file"
        continue
      fi

      echo "▶ GPX-only $(basename "$ALKI_ROUTE_GPX") — $scheme"
      build_args=(--width "$WIDTH" --height "$HEIGHT" --dpi "$DPI" --format "$FORMAT")
      just build-gpx "${build_args[@]}" \
        --buffer-km 5 \
        --text-title "$ALKI_ROUTE_TEXT_TITLE" \
        --text-subtitle "$ALKI_ROUTE_TEXT_SUBTITLE" \
        --text-stats "$ALKI_ROUTE_TEXT_STATS" \
        "$ALKI_ROUTE_GPX" "$scheme"
    done

    # 5) Boston route examples
    for scheme in $SCHEMES; do
      output_file="$OUTPUT_DIR/${BOSTON_ROUTE_SLUG}-${scheme}/${BOSTON_ROUTE_SLUG}-${scheme}.${FORMAT}"

      if [ "$FORCE" != true ] && [ -f "$output_file" ]; then
        echo "⏭ GPX-only $(basename "$BOSTON_ROUTE_GPX") — $scheme"
        echo "   Skipping existing output: $output_file"
        continue
      fi

      echo "▶ GPX-only $(basename "$BOSTON_ROUTE_GPX") — $scheme"
      build_args=(--width "$WIDTH" --height "$HEIGHT" --dpi "$DPI" --format "$FORMAT")
      just build-gpx "${build_args[@]}" \
        --buffer-km 5 \
        --text-title "$BOSTON_ROUTE_TEXT_TITLE" \
        --text-subtitle "$BOSTON_ROUTE_TEXT_SUBTITLE" \
        --text-stats "$BOSTON_ROUTE_TEXT_STATS" \
        "$BOSTON_ROUTE_GPX" "$scheme"
    done

    echo ""
    echo "✅ Map generation step complete"
  else
    echo ""
    echo "⏭ Skipping map generation by user choice"
  fi
else
  echo "✅ All maps already exist. Skipping map generation step."
fi

echo ""
echo "📤 Publishing maps to publish/ (smart copy with timestamp checking)..."
FORCE_ARG=""
if [ "$FORCE" = true ]; then
  FORCE_ARG="--force true"
fi

just publish $FORCE_ARG

echo ""
echo "📸 Creating examples for GitHub README (smart resize with timestamp checking)..."
FORCE_ARG=""
if [ "$FORCE" = true ]; then
  FORCE_ARG="--force true"
fi

just create-examples --full-width "$FULL_WIDTH" --thumb-width "$THUMBNAIL_WIDTH" $FORCE_ARG

echo ""
echo "✅ All steps complete"
echo "  Publish folder      : $PUBLISH_DIR/"
echo "  Full examples       : $EXAMPLES_FULL_DIR/"
echo "  Thumbnail examples  : $EXAMPLES_THUMB_DIR/"
