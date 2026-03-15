#!/usr/bin/env python3
"""
prepare-ocean-layer.py

Create a region-specific ocean GeoPackage from the downloaded World Seas
boundary shapefile. The output is a derived layer artifact that can be passed
to generate-config.py alongside the other region layers.
"""

import argparse
import sys
from pathlib import Path

import geopandas as gpd


def read_boundary(boundary_path: Path) -> gpd.GeoDataFrame:
    boundary = gpd.read_file(boundary_path, engine="pyogrio", use_arrow=True)
    if boundary.empty:
        raise ValueError(f"Boundary file is empty: {boundary_path}")
    if boundary.crs is None:
        boundary = boundary.set_crs("EPSG:4326")
    return boundary.to_crs("EPSG:4326")


def read_ocean(
    ocean_path: Path, bbox: tuple[float, float, float, float]
) -> gpd.GeoDataFrame:
    try:
        ocean = gpd.read_file(
            ocean_path,
            engine="pyogrio",
            use_arrow=True,
            bbox=bbox,
        )
    except TypeError:
        ocean = gpd.read_file(ocean_path, engine="pyogrio", use_arrow=True)

    if ocean.empty:
        return ocean
    if ocean.crs is None:
        ocean = ocean.set_crs("EPSG:4326")
    return ocean.to_crs("EPSG:4326")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a clipped ocean GeoPackage for a region boundary"
    )
    parser.add_argument(
        "--boundary",
        type=Path,
        required=True,
        help="Path to the buffered region boundary GeoJSON",
    )
    parser.add_argument(
        "--ocean-boundaries",
        type=Path,
        required=True,
        help="Path to the World Seas shapefile",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output GeoPackage path, typically downloads/regions/.../layers/ocean.gpkg",
    )
    args = parser.parse_args()

    boundary = read_boundary(args.boundary)
    bbox = tuple(boundary.total_bounds)
    ocean = read_ocean(args.ocean_boundaries, bbox)

    if ocean.empty:
        print(f"[ ] No nearby ocean features for {args.boundary}; skipping ocean layer")
        return

    ocean = ocean[ocean.geometry.notnull()]
    ocean = ocean[ocean.geom_type.isin(["Polygon", "MultiPolygon"])]
    clipped = gpd.clip(ocean, boundary)
    clipped = clipped[clipped.geometry.notnull()]
    clipped = clipped[~clipped.is_empty]

    if clipped.empty:
        print(f"[ ] No ocean polygons overlap {args.boundary}; skipping ocean layer")
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        args.output.unlink()

    clipped.to_file(args.output, layer="ocean", driver="GPKG")
    print(f"[✓] Ocean layer written to {args.output}")


if __name__ == "__main__":
    main()
