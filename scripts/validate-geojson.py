#!/usr/bin/env python3
# Copyright (c) 2026 Paul Stothard
# SPDX-License-Identifier: MIT
"""
validate-geojson.py

Validate a boundary GeoJSON before downstream processing.

Checks:
  - file is readable by GeoPandas
  - at least one feature exists
  - no empty geometries
  - all geometries are valid
  - bounds are within EPSG:4326 longitude/latitude limits
"""

import argparse
import geopandas as gpd
from shapely.validation import explain_validity


def validate_geojson(path):
    gdf = gpd.read_file(path, engine="pyogrio", use_arrow=True)

    if gdf.empty:
        raise ValueError(f"GeoJSON has no features: {path}")

    if gdf.geometry.is_empty.any():
        raise ValueError(f"GeoJSON contains empty geometry: {path}")

    invalid_mask = ~gdf.geometry.is_valid
    if invalid_mask.any():
        first_invalid = gdf.geometry[invalid_mask].iloc[0]
        reason = explain_validity(first_invalid)
        raise ValueError(f"GeoJSON contains invalid geometry: {reason}")

    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)

    minx, miny, maxx, maxy = gdf.total_bounds

    if minx < -180.0 - 1e-6 or maxx > 180.0 + 1e-6:
        raise ValueError(
            f"Longitude out of range: [{minx}, {maxx}] (expected within [-180, 180])"
        )

    if miny < -90.0 - 1e-6 or maxy > 90.0 + 1e-6:
        raise ValueError(
            f"Latitude out of range: [{miny}, {maxy}] (expected within [-90, 90])"
        )


def main():
    parser = argparse.ArgumentParser(description="Validate a GeoJSON boundary file")
    parser.add_argument("geojson", help="Path to GeoJSON file")
    args = parser.parse_args()

    validate_geojson(args.geojson)
    print(f"✓ GeoJSON validation passed: {args.geojson}")


if __name__ == "__main__":
    main()
