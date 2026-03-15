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
    - cop90: Copernicus Global DSM 90m via OpenTopography for country-scale
    - gmted2010: Legacy alias that maps to cop90
  - etopo1: ETOPO1 1 arc-minute (~2km) for continent-scale

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


def download_opentopography_globaldem(demtype, minx, miny, maxx, maxy, tmpdir, output_name):
    """Download a Global DEM subset via OpenTopography API."""
    print(f"    Requesting {demtype} via OpenTopography API...")

    url = "https://portal.opentopography.org/API/globaldem"
    params = {
        "demtype": demtype,
        "south": miny,
        "north": maxy,
        "west": minx,
        "east": maxx,
        "outputFormat": "GTiff",
        "API_Key": "demoapikeyot2022",  # Demo key - users should get their own
    }

    response = requests.get(url, params=params, stream=True)
    
    if response.status_code != 200:
        error_msg = f"OpenTopography API error: {response.status_code}"
        try:
            error_msg += f" - {response.text[:200]}"
        except:
            pass
        raise RuntimeError(
            error_msg
            + "\n    Note: Check the dataset name, request bounds, and API key. The demo key is rate limited."
        )
    
    response.raise_for_status()

    tile_path = Path(tmpdir) / output_name
    with open(tile_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    return rasterio.open(tile_path)


def download_cop90(minx, miny, maxx, maxy, tmpdir):
    """Download Copernicus Global DSM 90m via OpenTopography API."""
    return download_opentopography_globaldem(
        "COP90", minx, miny, maxx, maxy, tmpdir, "cop90.tif"
    )


def download_gmted2010(minx, miny, maxx, maxy, tmpdir):
    """Backward-compatible alias for the retired GMTED2010 source."""
    print("    GMTED2010 is no longer available in OpenTopography; using COP90 instead...")
    return download_cop90(minx, miny, maxx, maxy, tmpdir)


def download_etopo1(minx, miny, maxx, maxy, tmpdir):
    """Download ETOPO 2022 (successor to ETOPO1) as Cloud Optimized GeoTIFF subset."""
    print("    Requesting ETOPO 2022 global relief data...")

    # ETOPO 2022 60-arc-second ice-surface GeoTIFF from NOAA.
    # The older THREDDS fileServer path now returns 404; use the direct data path.
    url = "https://www.ngdc.noaa.gov/mgg/global/relief/ETOPO2022/data/60s/60s_surface_elev_gtif/ETOPO_2022_v1_60s_N90W180_surface.tif"

    # For COG, we can use rasterio's virtual warping to read just our bbox
    # Open with rasterio's VRT capabilities
    print("    Opening ETOPO 2022 COG (this may take a moment)...")
    with rasterio.open(url) as src:
        # Read window for our bbox
        window = src.window(minx, miny, maxx, maxy)
        data = src.read(1, window=window)
        transform = src.window_transform(window)

        # Write to temp file
        tile_path = Path(tmpdir) / "etopo2022.tif"
        with rasterio.open(
            tile_path,
            "w",
            driver="GTiff",
            height=data.shape[0],
            width=data.shape[1],
            count=1,
            dtype=data.dtype,
            crs=src.crs,
            transform=transform,
        ) as dst:
            dst.write(data, 1)

        return rasterio.open(tile_path)


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
        choices=["srtm", "copernicus", "cop90", "gmted2010", "etopo1"],
        help="DEM source: srtm (default), copernicus, cop90, etopo1, or gmted2010 (legacy alias)",
    )
    args = parser.parse_args()

    # Load boundary
    gdf = gpd.read_file(args.boundary, engine="pyogrio", use_arrow=True)
    orig_crs = gdf.crs or "EPSG:4326"
    # Make a 4326 copy for tile logic
    gdf4326 = gdf.to_crs(epsg=4326)
    minx, miny, maxx, maxy = gdf4326.total_bounds

    print(
        f"[ ] Determining tiles for bounds: {minx:.4f},{miny:.4f} — {maxx:.4f},{maxy:.4f}"
    )

    if args.source == "cop90":
        print(f"[ ] Using Copernicus Global DSM 90m via OpenTopography")
        with tempfile.TemporaryDirectory() as tmpdir:
            src = download_cop90(minx, miny, maxx, maxy, tmpdir)
            srcs = [src]
            mosaic, trans = merge(srcs)
            src_crs = srcs[0].crs
    elif args.source == "gmted2010":
        print(f"[ ] GMTED2010 retired upstream; using COP90 via OpenTopography")
        with tempfile.TemporaryDirectory() as tmpdir:
            src = download_gmted2010(minx, miny, maxx, maxy, tmpdir)
            srcs = [src]
            mosaic, trans = merge(srcs)
            src_crs = srcs[0].crs
    elif args.source == "etopo1":
        print(f"[ ] Using ETOPO 2022 (~2km resolution)")
        with tempfile.TemporaryDirectory() as tmpdir:
            src = download_etopo1(minx, miny, maxx, maxy, tmpdir)
            srcs = [src]
            mosaic, trans = merge(srcs)
            src_crs = srcs[0].crs
    elif args.source == "copernicus":
        print(f"[ ] Using Copernicus DEM GLO-30 (30m resolution)")
        tiles = get_copernicus_tile_names(minx, miny, maxx, maxy)
        print(f"[ ] Downloading and opening {len(tiles)} tiles...")
        srcs = []
        with tempfile.TemporaryDirectory() as tmpdir:
            for tile_name, lat, lon in tiles:
                # AWS S3 path structure: tiles are in directories named after the tile
                # e.g., .../Copernicus_DSM_COG_10_N50_00_W115_00_DEM/Copernicus_DSM_COG_10_N50_00_W115_00_DEM.tif
                tile_base = tile_name.replace(".tif", "")
                url = f"https://copernicus-dem-30m.s3.amazonaws.com/{tile_base}/{tile_name}"
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
