#!/usr/bin/env bash
set -euo pipefail

REGIONS=(
  "Edmonton, AB"
  "Vancouver, BC"
  "Vancouver Island, BC"
  "British Columbia"
  "Iceland"
)

[ -d "venv" ] && source venv/bin/activate

# Get schemes dynamically
SCHEMES=$(just schemes 2>/dev/null | grep -oP '(?<=• )\S+')

echo "This script will generate all color schemes for each of the following regions:"
for r in "${REGIONS[@]}"; do echo "  • $r"; done
echo ""
echo "  Data downloads : downloads/regions/"
echo "  Configs        : configs/"
echo "  Maps           : output/"
echo "  Published maps : publish/"
echo "  README examples: examples/"
echo ""
echo "See README.md for more information."
echo ""
read -p "Proceed? (y/N) " -n 1 -r
echo
[[ $REPLY =~ ^[Yy]$ ]] || exit 0
echo ""

echo "Regions: ${#REGIONS[@]}  Schemes: $(echo "$SCHEMES" | wc -w | tr -d ' ')"
echo ""

for region in "${REGIONS[@]}"; do
  for scheme in $SCHEMES; do
    echo "▶ $region — $scheme"
    just build "$region" "$scheme" width=24 height=24 dpi=600
  done
done

echo ""
echo "✅ All maps complete"
echo ""

just publish

python scripts/resize-images.py --input publish/ --output examples/ --width 1200

echo ""
echo "✅ Examples saved to examples/"
