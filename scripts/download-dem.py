#!/usr/bin/env python3
"""
download-dem.py

Pure-Python DEM acquisition and processing:
 1. Read GeoJSON boundary
 2. Determine required 1°×1° tiles (SRTM or Copernicus)
 3. Download tiles (SRTM .hgt.gz or Copernicus COG)
 4. Load tiles into rasterio
 5. Mosaic via rasterio.merge
 6. Reproject if needed
 7. Clip to boundary geometry
 8. Write GeoTIFF to disk

Usage:
  python scripts/download-dem.py \
      -b downloads/regions/edmonton/area.geojson \
      -o dem/edmonton_dem.tif \
      --source srtm  # or copernicus

DEM Sources:
  - srtm: SRTM 1-arc-second (~30m) from AWS elevation-tiles
  - copernicus: Copernicus DEM GLO-30 (30m) from AWS

Requirements:
  requests, geopandas, rasterio
"""
import argparse
import gzip
import math
import tempfile
from pathlib import Path

import requests
import geopandas as gpd
import rasterio
from rasterio.io import MemoryFile
from rasterio.merge import merge
from rasterio import warp
from rasterio.enums import Resampling
from rasterio.mask import mask
from shapely.geometry import mapping
import numpy as np


def get_tile_prefixes(minx, miny, maxx, maxy):
    """Get SRTM tile prefixes (NxxWyyy format) for the bounding box."""
    # SRTM tiles are named NxxWyyy etc, covering integer degree squares
    lats = range(math.floor(miny), math.ceil(maxy))
    lons = range(math.floor(minx), math.ceil(maxx))
    prefixes = []
    for lat in lats:
        for lon in lons:
            ns = "N" if lat >= 0 else "S"
            ew = "E" if lon >= 0 else "W"
            lat_s = f"{ns}{abs(lat):02d}"
            lon_s = f"{ew}{abs(lon):03d}"
            prefixes.append((lat_s, lon_s))
    return prefixes


def get_copernicus_tile_names(minx, miny, maxx, maxy):
    """Get Copernicus DEM tile names for the bounding box."""
    # Copernicus tiles: Copernicus_DSM_COG_10_N53_00_W114_00_DEM.tif
    # Tiles cover 1°×1° with SW corner naming
    lats = range(math.floor(miny), math.ceil(maxy))
    lons = range(math.floor(minx), math.ceil(maxx))
    tiles = []
    for lat in lats:
        for lon in lons:
            ns = "N" if lat >= 0 else "S"
            ew = "E" if lon >= 0 else "W"
            lat_str = f"{ns}{abs(lat):02d}_00"
            lon_str = f"{ew}{abs(lon):03d}_00"
            tile_name = f"Copernicus_DSM_COG_10_{lat_str}_{lon_str}_DEM.tif"
            tiles.append((tile_name, lat, lon))
    return tiles


def main():
    parser = argparse.ArgumentParser(
        description="Pure-Python DEM prep for a GeoJSON boundary."
    )
    parser.add_argument(
        "-b", "--boundary", type=Path, required=True, help="Input GeoJSON boundary"
    )
    parser.add_argument(
        "-o", "--output", type=Path, required=True, help="Output clipped DEM GeoTIFF"
    )
    parser.add_argument(
        "--source",
        type=str,
        default="srtm",
        choices=["srtm", "copernicus"],
        help="DEM source: srtm (default) or copernicus",
    )
    args = parser.parse_args()

    # Load boundary
    gdf = gpd.read_file(args.boundary)
    orig_crs = gdf.crs or "EPSG:4326"
    # Make a 4326 copy for tile logic
    gdf4326 = gdf.to_crs(epsg=4326)
    minx, miny, maxx, maxy = gdf4326.total_bounds

    print(
        f"[ ] Determining tiles for bounds: {minx:.4f},{miny:.4f} — {maxx:.4f},{maxy:.4f}"
    )

    if args.source == "copernicus":
        print(f"[ ] Using Copernicus DEM GLO-30 (30m resolution)")
        tiles = get_copernicus_tile_names(minx, miny, maxx, maxy)
        print(f"[ ] Downloading and opening {len(tiles)} tiles...")
        srcs = []
        with tempfile.TemporaryDirectory() as tmpdir:
            for tile_name, lat, lon in tiles:
                # Copernicus tiles are organized by latitude bands
                ns = "N" if lat >= 0 else "S"
                ew = "E" if lon >= 0 else "W"
                lat_str = f"{ns}{abs(lat):02d}_00"
                lon_str = f"{ew}{abs(lon):03d}_00"

                # AWS S3 path structure
                url = f"https://copernicus-dem-30m.s3.amazonaws.com/{tile_name}"
                try:
                    print(f"    Downloading {tile_name}...")
                    r = requests.get(url, stream=True)
                    r.raise_for_status()
                    tile_path = Path(tmpdir) / tile_name
                    with open(tile_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                    src = rasterio.open(tile_path)
                    srcs.append(src)
                except Exception as e:
                    print(f"    Warning: failed to load tile {tile_name}: {e}")
            if not srcs:
                raise RuntimeError("No DEM tiles could be loaded.")

            print(f"[ ] Mosaicking tiles...")
            mosaic, trans = merge(srcs)
            src_crs = srcs[0].crs
    else:  # srtm
        print(f"[ ] Using SRTM 1-arc-second (~30m resolution)")
        prefixes = get_tile_prefixes(minx, miny, maxx, maxy)
        print(f"[ ] Downloading and opening {len(prefixes)} tiles...")
        srcs = []
        with tempfile.TemporaryDirectory() as tmpdir:
            for lat_s, lon_s in prefixes:
                url = f"https://s3.amazonaws.com/elevation-tiles-prod/skadi/{lat_s}/{lat_s}{lon_s}.hgt.gz"
                try:
                    r = requests.get(url)
                    r.raise_for_status()
                    data = gzip.decompress(r.content)
                    tile_path = Path(tmpdir) / f"{lat_s}{lon_s}.hgt"
                    tile_path.write_bytes(data)
                    src = rasterio.open(tile_path)
                    srcs.append(src)
                except Exception as e:
                    print(f"    Warning: failed to load tile {lat_s}{lon_s}: {e}")
            if not srcs:
                raise RuntimeError("No DEM tiles could be loaded.")

            print(f"[ ] Mosaicking tiles...")
            mosaic, trans = merge(srcs)
            src_crs = srcs[0].crs

    # Reproject if needed
    if orig_crs != src_crs:
        print(f"[ ] Reprojecting DEM to {orig_crs}")
        dst_transform, dst_width, dst_height = warp.calculate_default_transform(
            src_crs,
            orig_crs,
            mosaic.shape[2],
            mosaic.shape[1],
            *(minx, miny, maxx, maxy),
        )
        with MemoryFile() as mem:
            with mem.open(
                driver="GTiff",
                height=dst_height,
                width=dst_width,
                count=1,
                dtype=mosaic.dtype,
                crs=orig_crs,
                transform=dst_transform,
            ) as dst_mosaic:
                warp.reproject(
                    source=mosaic,
                    destination=rasterio.band(dst_mosaic, 1),
                    src_transform=trans,
                    src_crs=src_crs,
                    dst_transform=dst_transform,
                    dst_crs=orig_crs,
                    resampling=Resampling.bilinear,
                )
                mosaic = dst_mosaic.read(1)
                trans = dst_transform

    # Flatten to 2D if mosaic has a shape like (1, H, W)
    if hasattr(mosaic, "ndim") and mosaic.ndim == 3 and mosaic.shape[0] == 1:
        mosaic = mosaic[0]

    # Clip to polygon
    print(f"[ ] Clipping DEM to boundary shape...")
    shapes = [mapping(geom) for geom in gdf.to_crs(orig_crs).geometry]
    # Prepare in-memory dataset with correct dimensions
    height, width = mosaic.shape
    with MemoryFile() as mem2:
        with mem2.open(
            driver="GTiff",
            crs=orig_crs,
            transform=trans,
            height=height,
            width=width,
            count=1,
            dtype=mosaic.dtype,
        ) as tmp_ds:
            tmp_ds.write(mosaic, 1)
            clipped, clipped_trans = mask(tmp_ds, shapes, crop=True)

    # Write the clipped data (first band only)
    out_meta = {
        "driver": "GTiff",
        "height": clipped.shape[1],
        "width": clipped.shape[2],
        "count": 1,
        "dtype": clipped.dtype,
        "crs": orig_crs,
        "transform": clipped_trans,
    }
    print(f"[ ] Writing output to {args.output}")
    with rasterio.open(args.output, "w", **out_meta) as dst:
        dst.write(clipped[0], 1)

    print(f"[✓] DEM written to {args.output}")


if __name__ == "__main__":
    main()
