#!/usr/bin/env python3
"""
download-geojson.py

Geocode a place name or address, buffer its bounding box by a given distance,
and output a GeoJSON polygon.

Dependencies:
    pip install geopy shapely
"""
import argparse
import json
import math
from geopy.geocoders import Nominatim
from shapely.geometry import box, mapping


def geocode_bbox(place):
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


def write_geojson(south, north, west, east, output_path, properties=None):
    """
    Create a GeoJSON FeatureCollection with one polygon feature.
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
    args = parser.parse_args()

    south, north, west, east = geocode_bbox(args.place)
    if args.buffer:
        south, north, west, east = buffer_bbox(south, north, west, east, args.buffer)

    props = {
        "query": args.place,
        "buffer_km": args.buffer,
        "bbox": [south, north, west, east],
    }
    write_geojson(south, north, west, east, args.output, props)


if __name__ == "__main__":
    main()
