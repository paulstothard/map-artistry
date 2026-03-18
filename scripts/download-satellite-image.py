#!/usr/bin/env python3
# Copyright (c) 2026 Paul Stothard
# SPDX-License-Identifier: MIT
"""
download-satellite-image.py

Download high-resolution satellite imagery from Esri World Imagery,
using a polygon from a GeoJSON file or a geocoded place name.

Usage:
    ./download-satellite-image.py --geojson area.geojson
    ./download-satellite-image.py --place "Edmonton, AB" --zoom 18 --format png

Output format:
    If --format geotiff (default), saves an EPSG:4326 (WGS84) GeoTIFF (reprojected output from Web Mercator).
    If --format png, saves a PNG in WGS84 (reprojected output).
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
from rasterio.warp import calculate_default_transform, reproject, Resampling
import os
import osmnx as ox
from geojson_bounds import apply_primary_segment_clip


def main():
    parser = argparse.ArgumentParser(
        description="Download satellite imagery from a place name or GeoJSON polygon."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--geojson", help="Path to GeoJSON file (must contain a polygon)."
    )
    group.add_argument(
        "--place", help="Place name to geocode, e.g. 'Downtown Edmonton, AB'"
    )
    parser.add_argument(
        "--output", default="satellite.tif", help="Output path (default: satellite.tif)"
    )
    parser.add_argument(
        "--format", choices=["geotiff", "png"], default="geotiff", help="Output format"
    )
    parser.add_argument(
        "--zoom",
        type=int,
        default=14,
        help="Zoom level for satellite tiles (e.g., 13–17)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="DPI for figure rendering (higher = more pixels). Default: 300",
    )
    args = parser.parse_args()

    # Get polygon from geojson or place
    if args.place:
        # Geocode the place name and convert to GeoDataFrame in EPSG:4326
        gdf = ox.geocode_to_gdf(args.place)
        gdf = gdf.to_crs("EPSG:4326")
    else:
        gdf = gpd.read_file(args.geojson, engine="pyogrio", use_arrow=True)
        if gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")

    gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])]
    if gdf.empty:
        print("No valid polygon features found.")
        return

    gdf = gdf[gdf.geometry.notnull()]
    gdf = gdf[~gdf.is_empty]
    if gdf.empty:
        print("No valid polygon features found.")
        return

    gdf, primary_segment, antimeridian_clipped = apply_primary_segment_clip(gdf)
    if antimeridian_clipped:
        print(
            "[ ] Antimeridian boundary detected; "
            f"using primary segment bounds: {primary_segment}"
        )

    # Project to Web Mercator
    gdf_web = gdf.to_crs(epsg=3857)
    bounds = gdf_web.total_bounds  # [minx, miny, maxx, maxy]

    # ------------------------------------------------------------------
    # Choose figure size that preserves the Mercator aspect ratio so we
    # don’t warp the raster (prevent “squeezed” overlay later).
    # ------------------------------------------------------------------
    span_x = bounds[2] - bounds[0]
    span_y = bounds[3] - bounds[1]
    mercator_aspect = span_x / span_y if span_y != 0 else 1.0

    # Base size (inches). 10 is fine because dpi is 256, giving plenty
    # of pixels; we scale the other dimension by the aspect ratio.
    BASE = 10
    if mercator_aspect >= 1.0:
        fig_w, fig_h = BASE, BASE / mercator_aspect
    else:
        fig_w, fig_h = BASE * mercator_aspect, BASE

    # Create figure and plot with contextily basemap
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=args.dpi)
    fig.patch.set_facecolor("black")
    ax.set_facecolor("black")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    gdf_web.boundary.plot(ax=ax, edgecolor="none")
    ax.set_xlim(bounds[0], bounds[2])
    ax.set_ylim(bounds[1], bounds[3])
    ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, zoom=args.zoom)
    ax.axis("off")

    # Convert to image array
    fig.canvas.draw()
    img = np.asarray(fig.canvas.get_renderer().buffer_rgba()).copy()[..., :3]
    plt.close(fig)

    # Auto-crop border
    from PIL import Image

    img_rgb = np.array(Image.fromarray(img).crop(Image.fromarray(img).getbbox()))

    height, width, _ = img_rgb.shape

    # Calculate transform (Web Mercator)
    transform_3857 = from_bounds(*bounds, width=width, height=height)

    img_rgb = np.clip(img_rgb, 0, 255).astype(np.uint8)

    if args.format == "geotiff":
        # Reproject image from Web Mercator (EPSG:3857) to WGS84 (EPSG:4326)
        dst_crs = "EPSG:4326"
        transform_4326, dst_width, dst_height = calculate_default_transform(
            "EPSG:3857", dst_crs, width, height, *bounds
        )
        # Allocate destination array for each band
        dst_img = np.empty((3, dst_height, dst_width), dtype=np.float32)
        for i in range(3):
            reproject(
                source=img_rgb[:, :, i],
                destination=dst_img[i],
                src_transform=transform_3857,
                src_crs="EPSG:3857",
                dst_transform=transform_4326,
                dst_crs=dst_crs,
                resampling=Resampling.bilinear,
            )
        # Convert to uint8
        dst_img_uint8 = np.clip(dst_img, 0, 255).astype(np.uint8)
        with rasterio.open(
            args.output,
            "w",
            driver="GTiff",
            height=dst_height,
            width=dst_width,
            count=3,
            dtype=dst_img_uint8.dtype,
            crs=dst_crs,
            transform=transform_4326,
        ) as dst:
            for i in range(3):
                dst.write(dst_img_uint8[i], i + 1)
        print(f"✓ Saved GeoTIFF to {args.output}")
    else:
        import imageio

        # Convert image to uint8 and save as PNG (no reprojection)
        imageio.imwrite(args.output, img_rgb)
        print(f"✓ Saved PNG to {args.output}")


if __name__ == "__main__":
    main()
