#!/usr/bin/env python3
"""
download-osm-layers.py

Given a place name or GeoJSON, download intersecting OSM layers as GeoPackage (.gpkg) files.
Also auto-detects and saves any 'sea' (ocean) polygons in the area.

Usage:
    ./download-osm-layers.py --place "Edmonton, AB" \
        --output-dir layers \
        --layers highway building waterway landuse

Dependencies:
    pip install geopandas osmnx shapely fiona
"""
import os
import argparse
import geopandas as gpd
import osmnx as ox
import warnings
import time
import requests

warnings.filterwarnings("ignore", category=RuntimeWarning, module="pyogrio.raw")

ox.settings.use_cache = True
ox.settings.cache_folder = "cache"
ox.settings.log_console = True

# default tag mappings for OSMnx.geometries_from_polygon
TAG_MAP = {
    "highway": {"highway": True},
    "building": {"building": True},
    "waterway": {"waterway": True},
    "landuse": {"landuse": True},
    "water": {"natural": "water"},
    # you can add more: `"railway": {"railway": True}`, etc.
}


def download_layer(poly, key, tags, outdir):
    print(f"> Downloading layer '{key}' …")
    attempts = 3
    for attempt in range(attempts):
        try:
            # use network API for roads, chunked Overpass for others
            if key == "highway":
                G = ox.graph_from_polygon(poly, network_type="drive")
                gdf = ox.graph_to_gdfs(G, nodes=False)
            else:
                gdf = ox.features_from_polygon(poly, tags)
            break  # success
        except requests.exceptions.RequestException as e:
            if attempt < attempts - 1:
                wait_time = 10 * (attempt + 1)
                print(
                    f"  ⚠️ Timeout/error fetching '{key}', retrying in {wait_time}s … ({e})"
                )
                time.sleep(wait_time)
            else:
                raise RuntimeError(
                    f"Failed to download '{key}' after {attempts} attempts."
                ) from e

    # Print feature summary
    print(f"  → {len(gdf)} features in '{key}' layer")

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

    # Drop known problematic fields like 'FIXME' if present
    if "FIXME" in gdf.columns:
        gdf = gdf.drop(columns="FIXME")

    path = os.path.join(outdir, f"{key}.gpkg")
    gdf.to_file(path, driver="GPKG")
    print(f"  ✓ saved {path}")


def main():
    p = argparse.ArgumentParser(
        description="Download intersecting OSM layers as GeoPackages for a place name or GeoJSON polygon."
    )
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--place", help="Place name to geocode and fetch polygon for.")
    group.add_argument(
        "--geojson", help="Path to a GeoJSON file containing polygon(s)."
    )
    p.add_argument(
        "-o",
        "--output-dir",
        default="shapefiles",
        help="Directory to write .gpkg files into.",
    )
    p.add_argument(
        "--layers",
        nargs="+",
        default=["highway", "building", "waterway", "landuse", "water"],
        help="Which OSM layer keys to fetch (must be in TAG_MAP).",
    )
    p.add_argument(
        "--include-extra",
        action="store_true",
        default=False,
        help="Include optional/extra layers like places, pois, traffic, transport, and railway.",
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

    # Layers that require --include-extra to download
    extra_layers = {"places", "pois", "traffic", "transport", "railway"}

    # download each requested layer
    for key in args.layers:
        print(f"\n🔍 Processing layer: {key}")
        if key not in TAG_MAP:
            print(f"⚠️  Unknown layer '{key}', skipping")
            continue
        if key in extra_layers and not args.include_extra:
            print(
                f"⏭️  Skipping optional layer '{key}' (use --include-extra to include)"
            )
            continue
        start = time.time()
        print(f"⏳ Downloading '{key}' ...")
        try:
            download_layer(poly, key, TAG_MAP[key], args.output_dir)
            elapsed = time.time() - start
            print(f"✅ Completed '{key}' in {elapsed:.1f} seconds")
        except Exception as e:
            print(f"❌ Error while downloading '{key}': {e}")


if __name__ == "__main__":
    main()
