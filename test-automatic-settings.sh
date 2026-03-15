#!/usr/bin/env bash
#
# test-automatic-settings.sh
#
# Test script to generate maps for regions of various sizes to verify
# automatic setting calculations (buffer, DEM source, zoom, ocean detection, etc.)
#
# This creates a diverse set of maps demonstrating the system's ability to
# handle everything from small cities to entire continents.
#

set -euo pipefail

echo "============================================================================"
echo "Map Artistry - Automatic Settings Test Suite"
echo "============================================================================"
echo ""
echo "This script will generate maps for regions of different sizes:"
echo "  • Small city (Edmonton)"
echo "  • Medium city (Vancouver)"
echo "  • Large region/island (Vancouver Island)"
echo "  • Province (British Columbia)"
echo "  • Country (Iceland - smaller country)"
echo ""
echo "Each map uses automatic settings based on region size."
echo "All schemes will use 'coral' for consistency."
echo ""
read -p "Press Enter to start or Ctrl+C to cancel..."
echo ""

# Activate venv if available
if [ -d "venv" ]; then
  echo "Activating virtual environment..."
  source venv/bin/activate
fi

# --------------------------------------------------------------------------
# Test 1: Small City (Edmonton, AB)
# Expected: city tier, copernicus DEM, zoom 11, OSM, ~10km buffer
# --------------------------------------------------------------------------
echo "============================================================================"
echo "Test 1: Small City - Edmonton, AB"
echo "============================================================================"
just build "Edmonton, AB" coral 18 18
echo ""
echo "✅ Edmonton complete"
echo ""
sleep 2

# --------------------------------------------------------------------------
# Test 2: Medium City (Vancouver, BC)
# Expected: city tier, copernicus DEM, zoom 11, OSM, ~10-20km buffer
# --------------------------------------------------------------------------
echo "============================================================================"
echo "Test 2: Medium City - Vancouver, BC"
echo "============================================================================"
just build "Vancouver, BC" coral 18 18
echo ""
echo "✅ Vancouver complete"
echo ""
sleep 2

# --------------------------------------------------------------------------
# Test 3: Large Region/Island (Vancouver Island, BC)
# Expected: region tier, SRTM DEM, zoom 9, OSM, ~50km buffer, coastal
# --------------------------------------------------------------------------
echo "============================================================================"
echo "Test 3: Large Region - Vancouver Island, BC"
echo "============================================================================"
just build "Vancouver Island, BC" natural 24 24
echo ""
echo "✅ Vancouver Island complete"
echo ""
sleep 2

# --------------------------------------------------------------------------
# Test 4: Province (British Columbia)
# Expected: continent tier, ETOPO1 DEM, zoom 5, Natural Earth, ~200km buffer, coastal
# --------------------------------------------------------------------------
echo "============================================================================"
echo "Test 4: Province - British Columbia"
echo "============================================================================"
just build "British Columbia" lava 24 24
echo ""
echo "✅ British Columbia complete"
echo ""
sleep 2

# --------------------------------------------------------------------------
# Test 5: Small Country (Iceland)
# Expected: country tier, COP90 DEM, zoom 7, Natural Earth, ~100km buffer, coastal
# --------------------------------------------------------------------------
echo "============================================================================"
echo "Test 5: Small Country - Iceland"
echo "============================================================================"
just build "Iceland" river_runs_red 24 24
echo ""
echo "✅ Iceland complete"
echo ""
sleep 2

# --------------------------------------------------------------------------
# Test 6: Large Country (Canada) - OPTIONAL, commented out by default
# This will take a LONG time and generate very large files
# Uncomment only if you want to test continent-scale settings
# --------------------------------------------------------------------------
# echo "============================================================================"
# echo "Test 6: Large Country - Canada (WARNING: This will take hours!)"
# echo "============================================================================"
# read -p "Really build Canada? This will download gigabytes of data. (y/N) " -n 1 -r
# echo
# if [[ $REPLY =~ ^[Yy]$ ]]; then
#     just build "Canada" coral --width 48 --height 36
#     echo ""
#     echo "✅ Canada complete"
# else
#     echo "Skipped Canada"
# fi
# echo ""

# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------
echo "============================================================================"
echo "Test Suite Complete!"
echo "============================================================================"
echo ""
echo "Generated maps:"
ls -lh output/*/

echo ""
echo "Summary of automatic settings applied:"
echo "  Edmonton:          city tier → Copernicus DEM, zoom 11, OSM"
echo "  Vancouver:         city tier → Copernicus DEM, zoom 11, OSM"
echo "  Vancouver Island:  region tier → SRTM DEM, zoom 9, OSM + ocean"
echo "  British Columbia:  continent tier → ETOPO1 DEM, zoom 5, Natural Earth + ocean"
echo "  Iceland:           country tier → COP90 DEM, zoom 7, Natural Earth + ocean"
echo ""
echo "Check output/ directories for results!"
echo ""
