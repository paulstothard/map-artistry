#!/usr/bin/env python3
# Copyright (c) 2026 Paul Stothard
# SPDX-License-Identifier: MIT
"""
download-geojson.py

Geocode a place name or address, apply an optional buffer to its bounding box,
and write the result as a GeoJSON polygon.

Dependencies:
    pip install geopy shapely requests
"""
import argparse
import json
import math
from geopy.geocoders import Nominatim
from shapely.geometry import box, mapping


def geocode_bbox(place):
    """
    Use Nominatim to geocode a place name or address and return its bounding box.
    Returns (south, north, west, east) as floats.
    """
    geolocator = Nominatim(user_agent="map-artistry-download")
    loc = geolocator.geocode(place, exactly_one=True)
    if loc is None:
        raise ValueError(f"Could not geocode '{place}'")
    # boundingbox = [south_lat, north_lat, west_lon, east_lon] as strings
    south, north, west, east = map(float, loc.raw["boundingbox"])
    return south, north, west, east


def buffer_bbox(south, north, west, east, buffer_km):
    """
    Expand the bbox by buffer_km in each direction.
    Approximates 1° lat ≈ 111.32 km; 1° lon ≈ 111.32*cos(lat) km.
    """
    # center latitude for longitude scaling
    center_lat = (south + north) / 2.0
    km_per_deg_lat = 111.32
    km_per_deg_lon = km_per_deg_lat * math.cos(math.radians(center_lat))

    delta_lat = buffer_km / km_per_deg_lat
    delta_lon = buffer_km / km_per_deg_lon if km_per_deg_lon != 0 else 0

    return (
        south - delta_lat,
        north + delta_lat,
        west - delta_lon,
        east + delta_lon,
    )


def adjust_bbox_aspect_ratio(south, north, west, east, aspect_ratio):
    """
    Adjust bounding box to match desired aspect ratio (width:height).
    Expands from center point to maintain aspect_ratio while keeping all original area.

    Args:
        south, north, west, east: Bounding box coordinates
        aspect_ratio: Desired width:height ratio (e.g., 2.0 for twice as wide as tall)

    Returns:
        Adjusted (south, north, west, east) tuple
    """
    if aspect_ratio <= 0:
        raise ValueError("Aspect ratio must be positive")

    # Calculate center point
    center_lat = (south + north) / 2.0
    center_lon = (west + east) / 2.0

    # Current dimensions in degrees
    height_deg = north - south
    width_deg = east - west

    # Approximate conversion to kilometers for aspect ratio calculation
    km_per_deg_lat = 111.32
    km_per_deg_lon = km_per_deg_lat * math.cos(math.radians(center_lat))

    height_km = height_deg * km_per_deg_lat
    width_km = width_deg * km_per_deg_lon

    # Current aspect ratio
    current_aspect = width_km / height_km if height_km > 0 else 1.0

    # Adjust to match desired aspect ratio (expand the smaller dimension)
    if current_aspect < aspect_ratio:
        # Need to widen
        width_km = height_km * aspect_ratio
        width_deg = width_km / km_per_deg_lon if km_per_deg_lon != 0 else width_deg
    else:
        # Need to make taller
        height_km = width_km / aspect_ratio
        height_deg = height_km / km_per_deg_lat

    # Recalculate bounds from center
    half_height = height_deg / 2.0
    half_width = width_deg / 2.0

    return (
        center_lat - half_height,  # south
        center_lat + half_height,  # north
        center_lon - half_width,  # west
        center_lon + half_width,  # east
    )


def write_geojson(south, north, west, east, output_path, properties=None):
    """
    Write a GeoJSON FeatureCollection containing one polygon feature
    representing the bounding box.
    """
    geom = box(west, south, east, north)
    feature = {
        "type": "Feature",
        "geometry": mapping(geom),
        "properties": properties or {},
    }
    fc = {"type": "FeatureCollection", "features": [feature]}

    with open(output_path, "w") as f:
        json.dump(fc, f, indent=2)
    print(f"Wrote buffered bbox GeoJSON to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Download (and buffer) a GeoJSON bbox for a place name or address"
    )
    parser.add_argument("place", help="City name or full address to geocode")
    parser.add_argument(
        "-b",
        "--buffer",
        type=float,
        default=0.0,
        help="Buffer in kilometers to expand the bbox (default: 0)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="bbox.geojson",
        help="Output GeoJSON filename (default: bbox.geojson)",
    )
    parser.add_argument(
        "-a",
        "--aspect-ratio",
        type=float,
        default=1.0,
        help="Desired width:height aspect ratio (default: 1.0 for square)",
    )
    args = parser.parse_args()

    south, north, west, east = geocode_bbox(args.place)
    if args.buffer:
        south, north, west, east = buffer_bbox(south, north, west, east, args.buffer)

    # Adjust aspect ratio
    south, north, west, east = adjust_bbox_aspect_ratio(
        south, north, west, east, args.aspect_ratio
    )

    props = {
        "query": args.place,
        "buffer_km": args.buffer,
        "aspect_ratio": args.aspect_ratio,
        "bbox": [south, north, west, east],
    }
    write_geojson(south, north, west, east, args.output, props)


if __name__ == "__main__":
    main()
