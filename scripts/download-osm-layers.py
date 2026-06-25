#!/usr/bin/env python3
# Copyright (c) 2026 Paul Stothard
# SPDX-License-Identifier: MIT
"""
download-osm-layers.py

Given a place name or GeoJSON, download intersecting OSM layers as GeoPackage (.gpkg) files.
Also auto-detects and saves any 'sea' (ocean) polygons in the area.

Sources:
    - osm (default): OpenStreetMap via Overpass API (detailed, city/region scale)
    - natural-earth: Natural Earth Data (simplified, country/continent scale)

Usage:
    ./download-osm-layers.py --place "Edmonton, AB" \
        --output-dir layers \
        --layers highway building waterway landuse \
        --source osm

Dependencies:
    pip install geopandas osmnx shapely fiona
"""
import os
import argparse
import json
import geopandas as gpd
import osmnx as ox
import warnings
import time
import requests
from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
from geojson_bounds import apply_primary_segment_clip

warnings.filterwarnings("ignore", category=RuntimeWarning, module="pyogrio.raw")

ox.settings.use_cache = True
ox.settings.log_console = True

NATURAL_EARTH_CDN_BASE = "https://naciscdn.org/naturalearth/10m"

# default tag mappings for OSMnx.geometries_from_polygon
TAG_MAP = {
    "highway": {"highway": True},
    "building": {"building": True},
    "waterway": {"waterway": True},
    "landuse": {"landuse": True},
    "water": {"natural": "water"},
    "natural": {
        "natural": [
            "wood",
            "wetland",
            "scrub",
            "heath",
            "beach",
            "cliff",
            "peak",
            "ridge",
            "valley",
            "glacier",
            "rock",
        ]
    },
    "pois": {"amenity": True},
    "places": {"place": True},
    "railway": {"railway": True},
    "traffic": {"traffic_calming": True},
    "transport": {"route": True},
}


# Natural Earth dataset URLs (10m scale for good detail at country scale)
NATURAL_EARTH_DATASETS = {
    "highway": {
        "url": f"{NATURAL_EARTH_CDN_BASE}/cultural/ne_10m_roads.zip",
        "layer": "ne_10m_roads",
        "rename": "road",
    },
    "road": {
        "url": f"{NATURAL_EARTH_CDN_BASE}/cultural/ne_10m_roads.zip",
        "layer": "ne_10m_roads",
        "rename": "road",
    },
    "waterway": {
        "url": f"{NATURAL_EARTH_CDN_BASE}/physical/ne_10m_rivers_lake_centerlines.zip",
        "layer": "ne_10m_rivers_lake_centerlines",
        "rename": "waterway",
    },
    "water": {
        "url": f"{NATURAL_EARTH_CDN_BASE}/physical/ne_10m_lakes.zip",
        "layer": "ne_10m_lakes",
        "rename": "water",
    },
    "landuse": {
        "url": f"{NATURAL_EARTH_CDN_BASE}/cultural/ne_10m_urban_areas.zip",
        "layer": "ne_10m_urban_areas",
        "rename": "landuse",
    },
    "natural": {
        "url": f"{NATURAL_EARTH_CDN_BASE}/physical/ne_10m_geography_regions_polys.zip",
        "layer": "ne_10m_geography_regions_polys",
        "rename": "natural",
    },
    "places": {
        "url": f"{NATURAL_EARTH_CDN_BASE}/cultural/ne_10m_populated_places.zip",
        "layer": "ne_10m_populated_places",
        "rename": "places",
    },
}


def download_and_cache_natural_earth(dataset_info, cache_dir):
    """Download and cache Natural Earth dataset."""
    os.makedirs(cache_dir, exist_ok=True)

    layer_name = dataset_info["layer"]
    cache_path = Path(cache_dir) / f"{layer_name}.gpkg"

    # Return cached version if exists
    if cache_path.exists():
        print(f"    Using cached Natural Earth data: {cache_path}")
        return gpd.read_file(cache_path, engine="pyogrio", use_arrow=True)

    # Download and extract
    print(f"    Downloading Natural Earth data from {dataset_info['url'][:50]}...")
    response = requests.get(dataset_info["url"], timeout=60)
    response.raise_for_status()

    # Extract shapefile from zip
    with ZipFile(BytesIO(response.content)) as zf:
        # Find the .shp file
        shp_files = [f for f in zf.namelist() if f.endswith(".shp")]
        if not shp_files:
            raise ValueError(f"No shapefile found in {dataset_info['url']}")

        # Extract all files to temp location
        temp_dir = Path(cache_dir) / "temp"
        os.makedirs(temp_dir, exist_ok=True)
        zf.extractall(temp_dir)

        # Read shapefile
        shp_path = temp_dir / shp_files[0]
        gdf = gpd.read_file(shp_path, engine="pyogrio", use_arrow=True)

        # Cache as GeoPackage for faster future access
        gdf.to_file(cache_path, driver="GPKG")

        # Clean up temp files
        import shutil

        shutil.rmtree(temp_dir)

        print(f"    ✓ Cached Natural Earth data to {cache_path}")
        return gdf


def download_natural_earth_layer(poly, key, outdir, natural_earth_cache_dir):
    """Download and clip Natural Earth layer to polygon boundary.
    Returns True if successful, False if no features found."""
    print(f"> Downloading Natural Earth layer '{key}' …")

    if key not in NATURAL_EARTH_DATASETS:
        print(f"  ⚠️  Natural Earth does not provide '{key}' layer")
        return False

    dataset_info = NATURAL_EARTH_DATASETS[key]

    try:
        # Download/load Natural Earth data
        gdf = download_and_cache_natural_earth(dataset_info, natural_earth_cache_dir)

        # Ensure same CRS
        if gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")

        # Clip to boundary
        print(f"    Clipping to boundary...")
        boundary_gdf = gpd.GeoDataFrame([{"geometry": poly}], crs="EPSG:4326")
        clipped = gpd.clip(gdf, boundary_gdf)

        if clipped.empty:
            print(f"  – no features in '{key}' within boundary")
            return False

        print(f"  → {len(clipped)} features in '{key}' layer")

        # Save with output name
        output_name = dataset_info["rename"]
        path = os.path.join(outdir, f"{output_name}.gpkg")
        clipped.to_file(path, driver="GPKG")
        print(f"  ✓ saved {path}")
        return True

    except Exception as e:
        print(f"  ⚠️  Error downloading Natural Earth '{key}': {e}")
        return False


def remove_layer_outputs(outdir, key):
    """Remove possible outputs for one requested layer before retrying it."""
    output_names = {key}
    dataset_info = NATURAL_EARTH_DATASETS.get(key)
    if dataset_info:
        output_names.add(dataset_info["rename"])

    for output_name in output_names:
        path = Path(outdir) / f"{output_name}.gpkg"
        if path.exists():
            path.unlink()


def download_layer(poly, key, tags, outdir):
    print(f"> Downloading layer '{key}' …")
    attempts = 3
    for attempt in range(attempts):
        try:
            # Use features_from_polygon for all layers to preserve original OSM tags
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


def download_requested_layer(poly, key, args):
    """Download one requested layer, with optional Natural Earth fallback."""
    return download_requested_layer_from_source(poly, key, args, args.source)


def write_completion_manifest(args, final_source):
    """Record that this layer directory was prepared by a complete command."""
    path = Path(args.output_dir) / ".layers-complete.json"
    payload = {
        "requested_layers": args.layers,
        "source": args.source,
        "final_source": final_source,
        "fallback_to_natural_earth": bool(args.fallback_to_natural_earth),
        "fallback_to_osm": bool(args.fallback_to_osm),
        "completed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def clear_completion_manifest(outdir):
    """Remove the completion marker before starting a layer-prep command."""
    path = Path(outdir) / ".layers-complete.json"
    if path.exists():
        path.unlink()


def clear_requested_layer_outputs(outdir, layers):
    """Remove prior outputs for the requested layer set before a fresh run."""
    for key in layers:
        remove_layer_outputs(outdir, key)


def download_requested_layer_from_source(poly, key, args, source):
    """Download one requested layer from a selected source."""
    if source == "natural-earth":
        if key not in NATURAL_EARTH_DATASETS:
            print(f"⚠️  Natural Earth does not provide '{key}' layer, skipping")
            return None

        start = time.time()
        success = download_natural_earth_layer(
            poly, key, args.output_dir, args.natural_earth_cache_dir
        )
        if success:
            elapsed = time.time() - start
            print(f"✅ Completed '{key}' from Natural Earth in {elapsed:.1f} seconds")
            return True

        if args.fallback_to_osm and key in NATURAL_EARTH_DATASETS and key in TAG_MAP:
            print(f"🔄 Falling back to OSM for '{key}'...")
            start = time.time()
            download_layer(poly, key, TAG_MAP[key], args.output_dir)
            elapsed = time.time() - start
            print(f"✅ Completed '{key}' from OSM fallback in {elapsed:.1f} seconds")
            return True

        return False

    if key not in TAG_MAP:
        print(f"⚠️  Unknown layer '{key}', skipping")
        return False

    start = time.time()
    print(f"⏳ Downloading '{key}' from OSM...")
    try:
        download_layer(poly, key, TAG_MAP[key], args.output_dir)
        elapsed = time.time() - start
        print(f"✅ Completed '{key}' in {elapsed:.1f} seconds")
        return True
    except Exception as e:
        print(f"❌ Error while downloading '{key}' from OSM: {e}")
        if not args.fallback_to_natural_earth:
            return False

    if key not in NATURAL_EARTH_DATASETS:
        print(f"⚠️  Natural Earth does not provide '{key}' layer, skipping")
        remove_layer_outputs(args.output_dir, key)
        return "fallback"

    print(f"🔄 Falling back to Natural Earth for '{key}'...")
    remove_layer_outputs(args.output_dir, key)
    start = time.time()
    success = download_natural_earth_layer(
        poly, key, args.output_dir, args.natural_earth_cache_dir
    )
    if success:
        elapsed = time.time() - start
        print(
            f"✅ Completed '{key}' from Natural Earth fallback in {elapsed:.1f} seconds"
        )
        return "fallback"

    print(f"❌ Natural Earth fallback did not provide '{key}'")
    return False


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
        default=[
            "highway",
            "building",
            "waterway",
            "landuse",
            "water",
            "pois",
            "natural",
        ],
        help="Which OSM layer keys to fetch (must be in TAG_MAP).",
    )
    p.add_argument(
        "--source",
        type=str,
        default="osm",
        choices=["osm", "natural-earth"],
        help="Data source: osm (detailed, default) or natural-earth (simplified for large areas)",
    )
    p.add_argument(
        "--fallback-to-osm",
        action="store_true",
        help="When using natural-earth source, fallback to OSM for layers with no features",
    )
    p.add_argument(
        "--fallback-to-natural-earth",
        action="store_true",
        help="When using OSM source, retry failed layers from Natural Earth when available.",
    )
    p.add_argument(
        "--fail-on-layer-error",
        action="store_true",
        help="Exit non-zero when a requested layer cannot be downloaded.",
    )
    p.add_argument(
        "--cache-dir",
        type=str,
        default="cache",
        help="Cache directory for OSMnx/Overpass requests",
    )
    p.add_argument(
        "--natural-earth-cache-dir",
        type=str,
        default="downloads/natural-earth",
        help="Cache directory for downloaded Natural Earth datasets",
    )
    args = p.parse_args()

    ox.settings.cache_folder = args.cache_dir
    os.makedirs(args.cache_dir, exist_ok=True)

    if args.place:
        boundary_gdf = ox.geocode_to_gdf(args.place)
    else:
        boundary_gdf = gpd.read_file(args.geojson, engine="pyogrio", use_arrow=True)

    if boundary_gdf.crs is None:
        boundary_gdf = boundary_gdf.set_crs("EPSG:4326")
    else:
        boundary_gdf = boundary_gdf.to_crs("EPSG:4326")

    boundary_gdf = boundary_gdf[
        boundary_gdf.geometry.type.isin(["Polygon", "MultiPolygon"])
    ]
    boundary_gdf = boundary_gdf[boundary_gdf.geometry.notnull()]
    boundary_gdf = boundary_gdf[~boundary_gdf.is_empty]

    if boundary_gdf.empty:
        raise ValueError("No valid polygon features found in boundary input")

    boundary_gdf, primary_segment, antimeridian_clipped = apply_primary_segment_clip(
        boundary_gdf
    )
    if antimeridian_clipped:
        print(
            "[ ] Antimeridian boundary detected; "
            f"using primary segment bounds: {primary_segment}"
        )

    poly = boundary_gdf.geometry.union_all()

    # sanity check
    print(f"Using bounding box: {poly.bounds}")

    os.makedirs(args.output_dir, exist_ok=True)
    clear_completion_manifest(args.output_dir)
    clear_requested_layer_outputs(args.output_dir, args.layers)

    failed_layers = []

    current_source = args.source

    # download each requested layer
    for key in args.layers:
        print(f"\n🔍 Processing layer: {key}")
        previous_source = current_source
        result = download_requested_layer_from_source(poly, key, args, current_source)
        if previous_source == "osm" and result == "fallback":
            print(
                "⚠️  OSM layer download failed after retries; "
                "using Natural Earth for remaining compatible layers."
            )
            current_source = "natural-earth"
        if (
            result is False
            and previous_source == "osm"
            and args.fallback_to_natural_earth
        ):
            print(
                "⚠️  OSM layer download failed after retries; "
                "using Natural Earth for remaining compatible layers."
            )
            current_source = "natural-earth"
        if result is False and previous_source != "natural-earth":
            failed_layers.append(key)

    if args.fail_on_layer_error and failed_layers:
        raise SystemExit(
            "Failed to download requested layer(s): " + ", ".join(failed_layers)
        )

    write_completion_manifest(args, current_source)


if __name__ == "__main__":
    main()
