#!/usr/bin/env python3
"""
download-dem.py

Pure-Python DEM acquisition and processing with automatic fallback:
 1. Read GeoJSON boundary
 2. Determine required 1°×1° tiles
 3. Try high-res sources (Copernicus), fall back to SRTM
 4. Download and decompress tiles
 5. Load tiles into rasterio
 6. Mosaic via rasterio.merge
 7. Reproject if needed
 8. Clip to boundary geometry
 9. Write GeoTIFF to disk

Usage:
  python scripts/download-dem.py \
      -b data/edmonton.map.geojson \
      -o dem/edmonton_dem.tif
  
  # Use specific source only:
  python scripts/download-dem.py \
      -b data/edmonton.map.geojson \
      -o dem/edmonton_dem.tif \
      --sources srtm

Requirements:
  requests, geopandas, rasterio
"""
import argparse
import gzip
import math
import tempfile
from pathlib import Path
from typing import Optional, List

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
    # Tiles are named NxxWyyy etc, covering integer degree squares
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


def download_copernicus_tile(lat_s: str, lon_s: str, tmpdir: Path) -> Optional[rasterio.DatasetReader]:
    """
    Try to download a tile from Copernicus DEM GLO-30 (30m resolution, better quality than SRTM).
    Returns an open rasterio dataset or None if failed.
    """
    # Extract numeric values
    lat_num = int(lat_s[1:])
    lon_num = int(lon_s[1:])
    if lat_s[0] == 'S':
        lat_num = -lat_num
    if lon_s[0] == 'W':
        lon_num = -lon_num
    
    # Copernicus naming: Copernicus_DSM_COG_10_N53_00_W114_00_DEM.tif
    lat_cop = f"{'N' if lat_num >= 0 else 'S'}{abs(lat_num):02d}_00"
    lon_cop = f"{'E' if lon_num >= 0 else 'W'}{abs(lon_num):03d}_00"
    
    # Copernicus GLO-30 public URL (via AWS)
    url = f"https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_{lat_cop}_{lon_cop}_DEM/Copernicus_DSM_COG_10_{lat_cop}_{lon_cop}_DEM.tif"
    
    try:
        print(f"    Trying Copernicus DEM: {lat_s}{lon_s}")
        r = requests.get(url, timeout=30, stream=True)
        r.raise_for_status()
        
        tile_path = tmpdir / f"{lat_s}{lon_s}_copernicus.tif"
        with open(tile_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        
        src = rasterio.open(tile_path)
        print(f"    ✓ Copernicus: {lat_s}{lon_s}")
        return src
    except Exception as e:
        print(f"    ✗ Copernicus unavailable: {lat_s}{lon_s}")
        return None


def download_srtm_tile(lat_s: str, lon_s: str, tmpdir: Path) -> Optional[rasterio.DatasetReader]:
    """
    Download a tile from SRTM via AWS S3 (30m resolution, fallback source).
    Returns an open rasterio dataset or None if failed.
    """
    url = f"https://s3.amazonaws.com/elevation-tiles-prod/skadi/{lat_s}/{lat_s}{lon_s}.hgt.gz"
    try:
        print(f"    Trying SRTM: {lat_s}{lon_s}")
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = gzip.decompress(r.content)
        tile_path = tmpdir / f"{lat_s}{lon_s}.hgt"
        tile_path.write_bytes(data)
        src = rasterio.open(tile_path)
        print(f"    ✓ SRTM: {lat_s}{lon_s}")
        return src
    except Exception as e:
        print(f"    ✗ SRTM unavailable: {lat_s}{lon_s}")
        return None


def download_tile_with_fallback(
    lat_s: str, 
    lon_s: str, 
    tmpdir: Path, 
    sources: List[str]
) -> Optional[rasterio.DatasetReader]:
    """
    Try downloading a tile from multiple sources in order.
    Returns the first successful download or None if all fail.
    
    Args:
        lat_s: Latitude string (e.g., 'N53')
        lon_s: Longitude string (e.g., 'W114')
        tmpdir: Temporary directory for downloads
        sources: List of source names to try in order ('copernicus', 'srtm')
    """
    for source in sources:
        if source == 'copernicus':
            result = download_copernicus_tile(lat_s, lon_s, tmpdir)
        elif source == 'srtm':
            result = download_srtm_tile(lat_s, lon_s, tmpdir)
        else:
            continue
        
        if result is not None:
            return result
    
    return None


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
        "--sources",
        type=str,
        default="copernicus,srtm",
        help="Comma-separated list of DEM sources to try in order (default: copernicus,srtm)"
    )
    args = parser.parse_args()
    
    # Parse sources list
    source_list = [s.strip() for s in args.sources.split(',')]

    # Load boundary
    gdf = gpd.read_file(args.boundary)
    orig_crs = gdf.crs or "EPSG:4326"
    # Make a 4326 copy for tile logic
    gdf4326 = gdf.to_crs(epsg=4326)
    minx, miny, maxx, maxy = gdf4326.total_bounds

    print(
        f"[ ] Determining tiles for bounds: {minx:.4f},{miny:.4f} — {maxx:.4f},{maxy:.4f}"
    )
    prefixes = get_tile_prefixes(minx, miny, maxx, maxy)

    print(f"[ ] Downloading and opening {len(prefixes)} tiles (sources: {', '.join(source_list)})...")
    srcs = []
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        for lat_s, lon_s in prefixes:
            src = download_tile_with_fallback(lat_s, lon_s, tmpdir_path, source_list)
            if src:
                srcs.append(src)
            else:
                print(f"    Warning: All sources failed for tile {lat_s}{lon_s}")
        if not srcs:
            raise RuntimeError("No DEM tiles could be loaded from any source.")

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
