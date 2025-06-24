#!/usr/bin/env python3
"""
download-shapefiles.py

Given a place name, download intersecting OSM layers as ESRI Shapefiles.
Also auto-detects & saves any 'sea' (ocean) polygons in the area.

Usage:
    ./download-shapefiles.py --place "Edmonton, AB" \
        --output-dir shapefiles \
        --layers highway building waterway landuse

Dependencies:
    pip install geopandas osmnx shapely fiona
"""
import sys
from pathlib import Path
import os
import argparse
import geopandas as gpd
import osmnx as ox
import zipfile
import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, module="pyogrio.raw")

# default tag mappings for OSMnx.geometries_from_polygon
TAG_MAP = {
    "highway":   {"highway": True},
    "building":  {"building": True},
    "waterway":  {"waterway": True},
    "landuse":   {"landuse": True},
    "water":     {"natural": "water"},
    # you can add more: `"railway": {"railway": True}`, etc.
}

def download_layer(poly, key, tags, outdir):
    print(f"> Downloading layer '{key}' …")
    gdf = ox.features_from_polygon(poly, tags)
    # Remove null, invalid, or duplicate geometries
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.is_valid]
    gdf = gdf.drop_duplicates(subset="geometry")

    # Clip to input polygon to limit extraneous geometry
    gdf = gpd.clip(gdf, poly)

    # Explode multipart geometries
    gdf = gdf.explode(index_parts=True, ignore_index=True)

    # Filter supported geometry types
    supported_types = ["Polygon", "MultiPolygon"]
    gdf = gdf[gdf.geometry.type.isin(supported_types)]

    # Print feature and memory summary
    print(f"  → {len(gdf)} features in '{key}' layer")
    print(f"  → estimated memory: {gdf.memory_usage(deep=True).sum() / 1e6:.2f} MB")

    if "geometry" not in gdf or gdf.geometry.isnull().all():
        print(f"  – no valid geometry column for {key}")
        return
    if gdf.empty:
        print(f"  – no polygonal features for {key}")
        return

    # Define minimal attribute sets per layer
    layer_column_map = {
        "building": ["geometry", "building"],
        "landuse": ["geometry", "landuse"],
        "natural": ["geometry", "natural"],
        "places": ["geometry", "name", "place"],
        "pois": ["geometry", "name", "amenity"],
        "railway": ["geometry", "railway"],
        "road": ["geometry", "highway"],
        "traffic": ["geometry"],
        "transport": ["geometry", "route"],
        "water": ["geometry", "water"],
        "waterway": ["geometry", "waterway"],
    }

    # Reduce columns if known
    if key in layer_column_map:
        keep_cols = [col for col in layer_column_map[key] if col in gdf.columns]
        gdf = gdf[keep_cols]

    path = os.path.join(outdir, f"{key}.shp")
    gdf.to_file(path)
    print(f"  ✓ saved {path}")

def main():
    p = argparse.ArgumentParser(
        description="Download intersecting shapefiles for a named place or GeoJSON polygon."
    )
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--place",
        help="Place name to geocode and fetch polygon for."
    )
    group.add_argument(
        "--geojson",
        help="Path to a GeoJSON file containing polygon(s)."
    )
    p.add_argument(
        "-o", "--output-dir",
        default="shapefiles",
        help="Directory to write *.shp files into."
    )
    p.add_argument(
        "--layers", nargs="+",
        default=["highway","building","waterway","landuse","water"],
        help="Which OSM layer keys to fetch (must be in TAG_MAP)."
    )
    args = p.parse_args()

    if args.place:
        poly = ox.geocode_to_gdf(args.place).geometry.union_all()
    else:
        gdf = gpd.read_file(args.geojson)
        if gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])]
        poly = gdf.geometry.union_all()

    # sanity check
    print(f"Using bounding box: {poly.bounds}")

    os.makedirs(args.output_dir, exist_ok=True)

    # Clean the output directory (guarded and safe)
    output_dir = os.path.abspath(args.output_dir)
    trusted_base = os.path.abspath("output/shp")

    if os.path.commonpath([output_dir, trusted_base]) != trusted_base:
        print(f"⚠️ Refusing to clean unexpected directory: {output_dir}")
        return
    SHAPE_EXTS = {".shp", ".shx", ".dbf", ".prj", ".cpg", ".zip"}
    for f in os.listdir(args.output_dir):
        fpath = os.path.join(args.output_dir, f)
        if os.path.isfile(fpath) and Path(f).suffix.lower() in SHAPE_EXTS:
            os.remove(fpath)

    # download each requested layer
    for key in args.layers:
        if key not in TAG_MAP:
            print(f"⚠️  unknown layer '{key}', skipping")
            continue
        download_layer(poly, key, TAG_MAP[key], args.output_dir)

    # now auto-detect any ocean/sea polygons
    print("> Checking for ocean/sea polygons …")
    sea_tags = {"natural": "water", "water": "sea"}
    try:
        ocean = ox.features_from_polygon(poly, sea_tags)
        if not ocean.empty:
            path = os.path.join(args.output_dir, "ocean.shp")
            ocean.to_file(path)
            print(f"  ✓ saved ocean polygons to {path}")
        else:
            print(" - no ocean/sea features found in this area")
    except ox._errors.InsufficientResponseError:
        print(" - no ocean/sea features found in this area (query returned nothing)")

    # Create a single archive with all shapefiles
    zip_path = os.path.join(args.output_dir, "shapefiles.zip")
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for fname in os.listdir(args.output_dir):
            fpath = os.path.join(args.output_dir, fname)
            if fname != "shapefiles.zip" and os.path.isfile(fpath):
                zf.write(fpath, arcname=fname)
                os.remove(fpath)
    print(f"  ✓ created unified archive {zip_path}")

if __name__ == "__main__":
    main()