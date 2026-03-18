#!/usr/bin/env bash
set -euo pipefail

REGIONS=(
  "Banff, AB"
  "British Columbia"
  "Cape Town, South Africa"
  "Crete, Greece"
  "Edmonton, AB"
  "Hokkaido, Japan"
  "Iceland"
  "New Zealand"
  "Oahu, HI"
  "Patagonia"
  "San Francisco, CA"
  "Scotland"
  "Vancouver, BC"
  "Vancouver Island, BC"
  "Vestland, Norway"
)

WIDTH=24
HEIGHT=24
DPI=600
FORMAT="png"

# calculate-area.py (determine_buffer) will usually recommend 100km for New Zealand
# from place estimation. We use a larger fixed buffer for the example script so
# both islands stay comfortably in frame on square outputs.
NEW_ZEALAND_BUFFER_KM=200

[ -d "venv" ] && source venv/bin/activate

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
echo ""

if [ $NEEDED -eq 0 ]; then
  echo "✅ All maps already exist. Nothing to generate."
  echo ""
  echo "To regenerate maps, delete files from output/ directory."
  exit 0
fi

echo "Maps to generate:"
for entry in "${NEEDED_MAPS[@]}"; do
  IFS='|' read -r region scheme <<<"$entry"
  echo "  • $region — $scheme"
done

echo ""
echo "  Settings: ${WIDTH}x${HEIGHT} inches @ ${DPI} DPI, format: $FORMAT"
echo "  New Zealand buffer override: ${NEW_ZEALAND_BUFFER_KM}km"
echo "  Data downloads : downloads/regions/"
echo "  Configs        : configs/"
echo "  Maps           : output/"
echo ""
echo "See README.md for more information."
echo ""
read -p "Proceed with generating $NEEDED maps? (y/N) " -n 1 -r
echo
[[ $REPLY =~ ^[Yy]$ ]] || exit 0
echo ""

for region in "${REGIONS[@]}"; do
  location=$(echo "$region" | tr '[:upper:]' '[:lower:]' | sed 's/[, ]/-/g' | sed 's/--*/-/g')
  for scheme in $SCHEMES; do
    output_file="output/${location}-${scheme}/${location}-${scheme}.${FORMAT}"

    if [ -f "$output_file" ]; then
      echo "⏭ $region — $scheme"
      echo "   Skipping existing output: $output_file"
      continue
    fi

    echo "▶ $region — $scheme"

    build_args=(--width "$WIDTH" --height "$HEIGHT" --dpi "$DPI" --format "$FORMAT")
    if [ "$region" = "New Zealand" ]; then
      build_args+=(--buffer-km "$NEW_ZEALAND_BUFFER_KM")
    fi

    just build "${build_args[@]}" "$region" "$scheme"
  done
done

echo ""
echo "✅ All maps complete"
echo ""

just publish

echo ""

just publish-examples
