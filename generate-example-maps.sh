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
DPI=600
FORMAT="png"
FULL_WIDTH=1200
THUMBNAIL_WIDTH=400
DETAIL_WIDTH=1200
DETAIL_THUMB_WIDTH=400
FORCE=false
DETAIL_REGION="Edmonton, AB"
DETAIL_SCHEME="river_runs_red"

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

# Get schemes dynamically
SCHEMES=$(just schemes 2>/dev/null)

echo "Checking existing maps..."
echo ""

# Pre-flight check: determine what needs to be generated
TOTAL=0
EXISTING=0
NEEDED=0
declare -a NEEDED_MAPS

for region in "${REGIONS[@]}"; do
  location=$(echo "$region" | tr '[:upper:]' '[:lower:]' | sed 's/[, ]/-/g' | sed 's/--*/-/g')
  for scheme in $SCHEMES; do
    TOTAL=$((TOTAL + 1))
    output_file="output/${location}-${scheme}/${location}-${scheme}.${FORMAT}"

    if [ -f "$output_file" ]; then
      EXISTING=$((EXISTING + 1))
      if [ "$FORCE" = true ]; then
        NEEDED=$((NEEDED + 1))
        NEEDED_MAPS+=("$region|$scheme")
      fi
    else
      NEEDED=$((NEEDED + 1))
      NEEDED_MAPS+=("$region|$scheme")
    fi
  done
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
    IFS='|' read -r region scheme <<<"$entry"
    echo "  • $region — $scheme"
  done

  echo ""
  echo "  Settings: ${WIDTH}x${HEIGHT} inches @ ${DPI} DPI, format: $FORMAT"
  echo "  Force assets : $FORCE"
  echo "  Data downloads : downloads/regions/"
  echo "  Configs        : configs/"
  echo "  Maps           : output/"
  echo ""
  echo "See README.md for more information."
  echo ""
  read -p "Proceed with generating $NEEDED maps? (y/N) " -n 1 -r
  echo

  if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""

    for region in "${REGIONS[@]}"; do
      location=$(echo "$region" | tr '[:upper:]' '[:lower:]' | sed 's/[, ]/-/g' | sed 's/--*/-/g')
      for scheme in $SCHEMES; do
        output_file="output/${location}-${scheme}/${location}-${scheme}.${FORMAT}"

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
echo "📤 Publishing maps to publish/ (incremental)..."
mkdir -p publish

PUBLISH_COPIED=0
PUBLISH_SKIPPED=0

while IFS= read -r map_file; do
  [ -f "$map_file" ] || continue
  basename_file=$(basename "$map_file")
  publish_target="publish/$basename_file"

  if [ "$FORCE" = true ] || [ ! -f "$publish_target" ]; then
    cp "$map_file" "$publish_target"
    echo "  ✓ $basename_file"
    PUBLISH_COPIED=$((PUBLISH_COPIED + 1))
  else
    PUBLISH_SKIPPED=$((PUBLISH_SKIPPED + 1))
  fi
done < <(find output -type f \( -name "*.png" -o -name "*.pdf" \) | sort)

echo "  Copied: $PUBLISH_COPIED"
echo "  Skipped existing: $PUBLISH_SKIPPED"

echo ""
echo "📸 Creating examples for GitHub README (incremental)..."
mkdir -p examples/full examples/thumbnails

EXAMPLES_UPDATED=0
EXAMPLES_SKIPPED=0

while IFS= read -r publish_png; do
  [ -f "$publish_png" ] || continue
  basename_file=$(basename "$publish_png")
  full_target="examples/full/$basename_file"
  thumb_target="examples/thumbnails/$basename_file"

  need_full=false
  need_thumb=false

  if [ "$FORCE" = true ] || [ ! -f "$full_target" ]; then
    need_full=true
  fi
  if [ "$FORCE" = true ] || [ ! -f "$thumb_target" ]; then
    need_thumb=true
  fi

  if [ "$need_full" = false ] && [ "$need_thumb" = false ]; then
    EXAMPLES_SKIPPED=$((EXAMPLES_SKIPPED + 1))
    continue
  fi

  temp_input_dir=$(mktemp -d)
  cp "$publish_png" "$temp_input_dir/$basename_file"

  if [ "$need_full" = true ]; then
    "$PYTHON_BIN" scripts/resize-images.py \
      --input "$temp_input_dir" \
      --output examples/full \
      --width "$FULL_WIDTH" \
      --crop-pattern "*" \
      --crop-bottom 2.5 >/dev/null
  fi

  if [ "$need_thumb" = true ]; then
    "$PYTHON_BIN" scripts/resize-images.py \
      --input "$temp_input_dir" \
      --output examples/thumbnails \
      --width "$THUMBNAIL_WIDTH" \
      --crop-pattern "*" \
      --crop-bottom 2.5 >/dev/null
  fi

  rm -rf "$temp_input_dir"

  echo "  ✓ $basename_file"
  EXAMPLES_UPDATED=$((EXAMPLES_UPDATED + 1))
done < <(find publish -maxdepth 1 -type f -name "*.png" | sort)

echo "  Updated: $EXAMPLES_UPDATED"
echo "  Skipped existing: $EXAMPLES_SKIPPED"

echo ""
echo "🔎 Creating detail view (crop-first)..."

DETAIL_UPDATED=0
DETAIL_SKIPPED=0

detail_location=$(echo "$DETAIL_REGION" | tr '[:upper:]' '[:lower:]' | sed 's/[, ]/-/g' | sed 's/--*/-/g')
detail_publish_png="publish/${detail_location}-${DETAIL_SCHEME}.png"

if [ ! -f "$detail_publish_png" ]; then
  echo "  ⚠ Detail source missing: $detail_publish_png"
  echo "    Skipping detail-view generation"
else
  basename_file=$(basename "$detail_publish_png")
  detail_name="${basename_file%.png}-detail.png"
  full_detail_target="examples/full/$detail_name"
  thumb_detail_target="examples/thumbnails/$detail_name"

  need_full_detail=false
  need_thumb_detail=false

  if [ "$FORCE" = true ] || [ ! -f "$full_detail_target" ]; then
    need_full_detail=true
  fi
  if [ "$FORCE" = true ] || [ ! -f "$thumb_detail_target" ]; then
    need_thumb_detail=true
  fi

  if [ "$need_full_detail" = false ] && [ "$need_thumb_detail" = false ]; then
    DETAIL_SKIPPED=$((DETAIL_SKIPPED + 1))
  else
    "$PYTHON_BIN" - "$detail_publish_png" "$full_detail_target" "$thumb_detail_target" "$need_full_detail" "$need_thumb_detail" "$DETAIL_WIDTH" "$DETAIL_THUMB_WIDTH" <<'PY'
import sys
from pathlib import Path
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

source_png = Path(sys.argv[1])
full_target = Path(sys.argv[2])
thumb_target = Path(sys.argv[3])
need_full = sys.argv[4].lower() == "true"
need_thumb = sys.argv[5].lower() == "true"
detail_width = int(sys.argv[6])
thumb_width = int(sys.argv[7])

full_target.parent.mkdir(parents=True, exist_ok=True)
thumb_target.parent.mkdir(parents=True, exist_ok=True)

with Image.open(source_png) as source_img:
    src_w, src_h = source_img.size
    crop_side = min(src_w, src_h, detail_width)
    left = (src_w - crop_side) // 2
    top = (src_h - crop_side) // 2
    right = left + crop_side
    bottom = top + crop_side

    detail_img = source_img.crop((left, top, right, bottom))

    if need_full:
        detail_img.save(full_target, optimize=True)

if need_thumb:
    if need_full:
        with Image.open(full_target) as full_img:
            thumb_img = full_img.resize((thumb_width, thumb_width), Image.LANCZOS)
            thumb_img.save(thumb_target, optimize=True)
    else:
        with Image.open(full_target) as full_img:
            thumb_img = full_img.resize((thumb_width, thumb_width), Image.LANCZOS)
            thumb_img.save(thumb_target, optimize=True)

print(f"  detail: {source_png.name} -> {full_target.name}, {thumb_target.name}")
PY

    DETAIL_UPDATED=$((DETAIL_UPDATED + 1))
  fi
fi

echo "  Updated: $DETAIL_UPDATED"
echo "  Skipped existing: $DETAIL_SKIPPED"

echo ""
echo "✅ All steps complete"
echo "  Publish folder      : publish/"
echo "  Full examples       : examples/full/"
echo "  Thumbnail examples  : examples/thumbnails/"
