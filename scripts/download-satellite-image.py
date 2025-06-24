#!/usr/bin/env python3
"""
download-satellite-image.py

Download high-resolution satellite imagery (from Esri World Imagery)
for a polygon defined by a GeoJSON file or a place name.

Usage:
    ./download-satellite-image.py --geojson area.geojson
    ./download-satellite-image.py --place "Edmonton, AB" --zoom 18 --format png
"""

import argparse
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import contextily as ctx
import rasterio
from rasterio.transform import from_bounds
import numpy as np
import os
import osmnx as ox

def main():
    parser = argparse.ArgumentParser(description="Download satellite imagery from a place name or GeoJSON polygon.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--geojson", help="Path to GeoJSON file (must contain a polygon).")
    group.add_argument("--place", help="Place name to geocode, e.g. 'Downtown Edmonton, AB'")
    parser.add_argument("--output", default="satellite.tif", help="Output path (default: satellite.tif)")
    parser.add_argument("--format", choices=["geotiff", "png"], default="geotiff", help="Output format")
    parser.add_argument("--zoom", type=int, default=17, help="Zoom level for satellite imagery (default: 17)")
    args = parser.parse_args()

    # Get polygon from geojson or place
    if args.place:
        gdf = ox.geocode_to_gdf(args.place)
        gdf = gdf.to_crs("EPSG:4326")
    else:
        gdf = gpd.read_file(args.geojson)
        if gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")

    gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])]
    if gdf.empty:
        print("No valid polygon features found.")
        return
    poly = gdf.geometry.union_all()

    # Project to Web Mercator
    gdf_web = gdf.to_crs(epsg=3857)
    bounds = gdf_web.total_bounds  # [minx, miny, maxx, maxy]

    # Create figure and plot with contextily basemap
    fig, ax = plt.subplots(figsize=(10, 10), dpi=256)
    gdf_web.boundary.plot(ax=ax, edgecolor='none')
    ax.set_xlim(bounds[0], bounds[2])
    ax.set_ylim(bounds[1], bounds[3])
    ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, zoom=args.zoom)
    ax.axis('off')

    # Convert to image array
    fig.canvas.draw()
    img = np.asarray(fig.canvas.get_renderer().buffer_rgba()).copy()[..., :3]
    height, width, _ = img.shape
    plt.close(fig)

    # Calculate transform
    transform = from_bounds(*bounds, width=width, height=height)

    # Output
    if args.format == "geotiff":
        with rasterio.open(
            args.output, 'w',
            driver="GTiff",
            height=height,
            width=width,
            count=3,
            dtype=img.dtype,
            crs="EPSG:3857",
            transform=transform
        ) as dst:
            dst.write(np.moveaxis(img, 2, 0))
        print(f"✓ Saved GeoTIFF to {args.output}")
    else:
        import imageio
        imageio.imwrite(args.output, img)
        print(f"✓ Saved PNG to {args.output}")

if __name__ == "__main__":
    main()