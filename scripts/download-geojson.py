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
import xml.etree.ElementTree as ET
from pathlib import Path
from geopy.geocoders import Nominatim
from shapely.geometry import MultiPolygon, box, mapping
from shapely.validation import explain_validity


def geocode_bbox(place):
    """
    Use Nominatim to geocode a place name or address and return its bounding box.
    Returns (south, north, west, east, center_lat, center_lon) as floats.
    """
    geolocator = Nominatim(user_agent="map-artistry-download")
    loc = geolocator.geocode(place, exactly_one=True)
    if loc is None:
        raise ValueError(f"Could not geocode '{place}'")
    # boundingbox = [south_lat, north_lat, west_lon, east_lon] as strings
    south, north, west, east = map(float, loc.raw["boundingbox"])
    return south, north, west, east, float(loc.latitude), float(loc.longitude)


def _local_name(tag):
    """Return local XML tag name without namespace."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _longitude_interval_from_points(longitudes):
    """
    Compute the shortest longitude interval that contains all points.

    Returns
    -------
    (west, east)
        Unwrapped longitude bounds with east > west and span <= 360.
    """
    wrapped = [wrap_longitude(float(lon)) for lon in longitudes]
    if not wrapped:
        raise ValueError("No longitudes provided")

    direct_west = min(wrapped)
    direct_east = max(wrapped)
    direct_span = direct_east - direct_west

    shifted = [lon if lon >= 0 else lon + 360.0 for lon in wrapped]
    shifted_west = min(shifted)
    shifted_east = max(shifted)
    shifted_span = shifted_east - shifted_west

    if shifted_span < direct_span:
        west = shifted_west if shifted_west <= 180.0 else shifted_west - 360.0
        east = west + shifted_span
        return west, east

    return direct_west, direct_east


def gpx_bbox(gpx_path):
    """
    Read a GPX file and return bounding box and center.

    Returns (south, north, west, east, center_lat, center_lon) as floats.
    """
    gpx_file = Path(gpx_path)
    if not gpx_file.exists():
        raise FileNotFoundError(f"GPX file not found: {gpx_file}")

    tree = ET.parse(gpx_file)
    root = tree.getroot()

    points = []
    for elem in root.iter():
        name = _local_name(elem.tag)
        if name not in {"trkpt", "rtept", "wpt"}:
            continue
        lat = elem.attrib.get("lat")
        lon = elem.attrib.get("lon")
        if lat is None or lon is None:
            continue
        try:
            points.append((float(lat), float(lon)))
        except ValueError:
            continue

    if not points:
        raise ValueError(f"No route points found in GPX file: {gpx_file}")

    lats = [pt[0] for pt in points]
    lons = [pt[1] for pt in points]

    south = min(lats)
    north = max(lats)
    west, east = _longitude_interval_from_points(lons)

    center_lat = (south + north) / 2.0
    center_lon = wrap_longitude((west + east) / 2.0)

    return south, north, west, east, center_lat, center_lon


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


def wrap_longitude(lon):
    """Wrap longitude into [-180, 180] range."""
    while lon < -180.0:
        lon += 360.0
    while lon > 180.0:
        lon -= 360.0
    return lon


def shortest_longitude_interval(west, east):
    """
    Convert longitude bounds to the shortest unwrapped interval.

    Returns:
        (lon_min, lon_max) where lon_max >= lon_min and span <= 360
    """
    west = wrap_longitude(west)
    east = wrap_longitude(east)

    east_unwrapped = east
    while east_unwrapped < west:
        east_unwrapped += 360.0

    direct_span = east_unwrapped - west

    if direct_span >= 360.0 - 1e-9:
        return -180.0, 180.0

    if direct_span <= 180.0:
        return west, east_unwrapped

    return east_unwrapped, west + 360.0


def build_bbox_geometry(south, north, west, east):
    """Build a valid bbox geometry, splitting across antimeridian when needed."""
    if south >= north:
        raise ValueError(f"Invalid latitude bounds: south={south}, north={north}")

    lon_span = east - west
    if lon_span <= 0:
        raise ValueError(f"Invalid longitude bounds: west={west}, east={east}")

    if lon_span >= 360.0 - 1e-9:
        return box(-180.0, south, 180.0, north)

    while west < -180.0:
        west += 360.0
        east += 360.0
    while west > 180.0:
        west -= 360.0
        east -= 360.0

    if east <= 180.0:
        return box(west, south, east, north)

    left = box(west, south, 180.0, north)
    right = box(-180.0, south, east - 360.0, north)
    return MultiPolygon([left, right])


def validate_geometry(geom):
    """Validate geometry shape and coordinate ranges."""
    if geom.is_empty:
        raise ValueError("Generated geometry is empty")

    if not geom.is_valid:
        reason = explain_validity(geom)
        raise ValueError(f"Generated geometry is invalid: {reason}")

    minx, miny, maxx, maxy = geom.bounds
    if minx < -180.0 - 1e-6 or maxx > 180.0 + 1e-6:
        raise ValueError(f"Generated longitude bounds out of range: [{minx}, {maxx}]")
    if miny < -90.0 - 1e-6 or maxy > 90.0 + 1e-6:
        raise ValueError(f"Generated latitude bounds out of range: [{miny}, {maxy}]")


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

    # Calculate center point (longitude uses shortest interval to handle antimeridian)
    center_lat = (south + north) / 2.0
    lon_min, lon_max = shortest_longitude_interval(west, east)
    center_lon = (lon_min + lon_max) / 2.0

    # Current dimensions in degrees
    height_deg = north - south
    width_deg = lon_max - lon_min

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

    south = center_lat - half_height
    north = center_lat + half_height
    west = center_lon - half_width
    east = center_lon + half_width

    south = max(-90.0, south)
    north = min(90.0, north)

    if south >= north:
        raise ValueError(
            "Aspect-ratio adjustment produced invalid latitude bounds "
            f"(south={south}, north={north})"
        )

    return (south, north, west, east)


def write_geojson(south, north, west, east, output_path, properties=None):
    """
    Write a GeoJSON FeatureCollection containing one polygon feature
    representing the bounding box.
    """
    geom = build_bbox_geometry(south, north, west, east)
    validate_geometry(geom)
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
        description="Build a buffered GeoJSON bbox from either a place name or a GPX route"
    )
    parser.add_argument(
        "place",
        nargs="?",
        help="City name or full address to geocode (omit when using --gpx)",
    )
    parser.add_argument(
        "--gpx",
        type=str,
        default=None,
        help="Path to a GPX file to use as boundary source",
    )
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

    if bool(args.place) == bool(args.gpx):
        parser.error("Provide exactly one boundary source: either PLACE or --gpx")

    source_label = None
    if args.gpx:
        south, north, west, east, center_lat, center_lon = gpx_bbox(args.gpx)
        source_label = str(Path(args.gpx))
    else:
        south, north, west, east, center_lat, center_lon = geocode_bbox(args.place)
        source_label = args.place

    if args.buffer:
        south, north, west, east = buffer_bbox(south, north, west, east, args.buffer)

    # Adjust aspect ratio
    south, north, west, east = adjust_bbox_aspect_ratio(
        south, north, west, east, args.aspect_ratio
    )

    props = {
        "query": source_label,
        "source_type": "gpx" if args.gpx else "place",
        "buffer_km": args.buffer,
        "aspect_ratio": args.aspect_ratio,
        "bbox": [south, north, wrap_longitude(west), wrap_longitude(east)],
        "crosses_antimeridian": west < -180.0 or east > 180.0,
        "center_lat": center_lat,
        "center_lon": wrap_longitude(center_lon),
    }
    write_geojson(south, north, west, east, args.output, props)


if __name__ == "__main__":
    main()
