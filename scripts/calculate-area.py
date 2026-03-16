#!/usr/bin/env python3
# Copyright (c) 2026 Paul Stothard
# SPDX-License-Identifier: MIT
"""
calculate-area.py

Calculate the area of a GeoJSON boundary and recommend resource selection strategy.
Can also estimate area from a place name to recommend buffer size.

Usage:
    # From existing GeoJSON:
    ./calculate-area.py area.geojson

    # From place name (estimates buffer):
    ./calculate-area.py --place "Edmonton, AB"

Output: JSON with area size, recommendations for DEM source, satellite zoom, OSM source, and buffer.

Dependencies:
    pip install geopandas pyproj geopy
"""
import sys
import json
import argparse
import geopandas as gpd
from shapely.ops import transform
from shapely.geometry import box
import pyproj


def calculate_area_km2(gdf):
    """Calculate area of GeoDataFrame in square kilometers."""
    # Reproject to World Azimuthal Equidistant (preserves area)
    # Center on the centroid of the geometry
    centroid = gdf.geometry.iloc[0].centroid

    # Create equal area projection centered on geometry
    proj_string = f"+proj=aeqd +lat_0={centroid.y} +lon_0={centroid.x} +x_0=0 +y_0=0 +datum=WGS84 +units=m"

    gdf_projected = gdf.to_crs(proj_string)
    area_m2 = gdf_projected.geometry.area.sum()
    area_km2 = area_m2 / 1_000_000

    return area_km2


def estimate_area_from_place(place_name):
    """Estimate area from place name using geocoding."""
    from geopy.geocoders import Nominatim

    geolocator = Nominatim(user_agent="map-artistry")
    location = geolocator.geocode(place_name, exactly_one=True)

    if not location:
        raise ValueError(f"Could not geocode location: {place_name}")

    # Get bounding box if available
    if location.raw.get("boundingbox"):
        bbox = location.raw["boundingbox"]
        # bbox format: [min_lat, max_lat, min_lon, max_lon]
        min_lat, max_lat, min_lon, max_lon = map(float, bbox)

        # Create GeoDataFrame from bbox
        geom = box(min_lon, min_lat, max_lon, max_lat)
        gdf = gpd.GeoDataFrame([{"geometry": geom}], crs="EPSG:4326")

        return calculate_area_km2(gdf)
    else:
        # No bounding box - estimate based on place type
        place_type = location.raw.get("type", "")
        osm_class = location.raw.get("class", "")

        # Rough estimates
        if place_type in ["city", "town", "village"] or osm_class == "place":
            return 1000  # ~1000 km² for cities
        elif place_type in ["state", "province"]:
            return 500000  # ~500k km² for provinces/states
        elif place_type == "country":
            return 5000000  # ~5M km² for countries
        else:
            return 10000  # Default medium size


def determine_buffer(area_km2):
    """Determine appropriate buffer size based on estimated area."""
    if area_km2 < 1000:
        # Small city
        return 5
    elif area_km2 < 10_000:
        # Large city/metro
        return 5
    elif area_km2 < 100_000:
        # Region/island
        return 50
    elif area_km2 < 1_000_000:
        # Province/state
        return 100
    else:
        # Country/continent
        return 200


def determine_strategy(area_km2):
    """Determine optimal data source strategy based on area size."""

    # Define thresholds and recommendations
    if area_km2 < 10_000:
        # City scale: < 10,000 km² (e.g., Edmonton ~7000 km²)
        tier = "city"
        dem_source = "copernicus"
        sat_zoom = 12
        osm_source = "osm"
    elif area_km2 < 100_000:
        # Region scale: 10k-100k km² (e.g., Vancouver Island ~32,000 km²)
        tier = "region"
        dem_source = "srtm"
        sat_zoom = 9
        osm_source = "osm"
    elif area_km2 < 1_000_000:
        # Country scale: 100k-1M km² (e.g., Alberta ~660,000 km²)
        tier = "country"
        dem_source = "cop90"
        sat_zoom = 8
        osm_source = "natural-earth"
    else:
        # Continent scale: > 1M km² (e.g., Canada ~10M km²)
        tier = "continent"
        dem_source = "etopo1"
        sat_zoom = 6
        osm_source = "natural-earth"

    buffer = determine_buffer(area_km2)

    return {
        "area_km2": round(area_km2, 2),
        "tier": tier,
        "buffer_km": buffer,
        "recommendations": {
            "dem_source": dem_source,
            "sat_zoom": sat_zoom,
            "osm_source": osm_source,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Calculate area and recommend map generation strategy."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("geojson", nargs="?", help="Path to GeoJSON file")
    group.add_argument("--place", help="Place name to geocode and estimate")

    args = parser.parse_args()

    if args.place:
        # Estimate from place name
        area_km2 = estimate_area_from_place(args.place)
    else:
        # Calculate from GeoJSON
        gdf = gpd.read_file(args.geojson, engine="pyogrio", use_arrow=True)
        area_km2 = calculate_area_km2(gdf)

    # Determine strategy
    strategy = determine_strategy(area_km2)

    # Output JSON
    print(json.dumps(strategy, indent=2))


if __name__ == "__main__":
    main()
