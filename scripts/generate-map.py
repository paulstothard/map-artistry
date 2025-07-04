import yaml
from pathlib import Path
import math

import argparse

import geopandas as gpd
import matplotlib.pyplot as plt
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_bounds
from rasterio.plot import show as show_raster
from matplotlib.colors import LightSource
from scipy.ndimage import gaussian_filter
import numpy as np


def draw_map_from_config(
    config_path: Path,
    geojson_path: Path,
    output_path: Path,
    width: float = 12,
    height: float = 12,
    dpi: int = 300,
    fmt: str = "png",
):
    """
    Draws a map based on a YAML config, a GeoJSON mask, and referenced GeoPackage (.gpkg) layers.

    Parameters
    ----------
    config_path : Path
        Path to the YAML configuration file.
    geojson_path : Path
        Path to the GeoJSON file for clipping (mask).
    output_path : Path
        Path to save the output image file.
    """
    # Load configuration
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    # Prepare figure and axis
    mcfg = cfg["map"]
    fig, ax = plt.subplots(figsize=(width, height), dpi=dpi)
    # remove default margins so axes fill the canvas
    fig.patch.set_facecolor("black")
    ax.set_facecolor("black")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    # Load clipping mask (used both for layer clipping and extent)
    mask_gdf = gpd.read_file(geojson_path)
    # Background
    bg = mcfg.get("background", {})
    face_fc = bg.get("fc", "#ffffff")
    fig.patch.set_facecolor(face_fc)
    ax.set_facecolor(face_fc)
    ax.set_axis_off()

    # --- Render satellite image underlay if configured (drawn immediately after background) ---
    satellite_cfg = cfg.get("map", {}).get("satellite")
    if satellite_cfg and satellite_cfg.get("visible", True):
        with rasterio.open(satellite_cfg["path"]) as src:
            # Use the image data directly without reprojection
            img_rgb = np.moveaxis(src.read([1, 2, 3]), 0, -1)
            img_rgb = np.clip(img_rgb, 0, 255).astype(np.uint8)

            ax.imshow(
                img_rgb,
                extent=[
                    src.bounds.left,
                    src.bounds.right,
                    src.bounds.bottom,
                    src.bounds.top,
                ],
                zorder=satellite_cfg.get("zorder", 0),
                alpha=satellite_cfg.get("opacity", 1.0),
                aspect="auto",
            )

    # --- Render hillshade underlay if DEM is configured ---
    dem_path = mcfg.get("dem")
    hs_cfg = mcfg.get("hillshade", {})
    if dem_path:
        with rasterio.open(dem_path) as dem_ds:
            # Extract DEM bounds and compute target raster shape
            left, bottom, right, top = dem_ds.bounds

            # target output pixels based on figure size and dpi
            width_px = int(width * dpi)
            height_px = int(height * dpi)

            # build transform for target raster
            target_transform = from_bounds(
                left, bottom, right, top, width_px, height_px
            )

            # prepare destination array
            dem_resampled = np.empty((height_px, width_px), dtype=np.float32)

            # reproject/resample DEM into target grid
            reproject(
                source=rasterio.band(dem_ds, 1),
                destination=dem_resampled,
                src_transform=dem_ds.transform,
                src_crs=dem_ds.crs,
                dst_transform=target_transform,
                dst_crs=dem_ds.crs,
                resampling=Resampling.bilinear,
            )

            # Gaussian smoothing: sigma configurable
            sigma = hs_cfg.get("sigma", 1.0)
            dem_smoothed = gaussian_filter(dem_resampled, sigma=sigma)

            # compute pixel sizes in map units
            dx = target_transform.a
            dy = -target_transform.e

            # Compute hillshade using LightSource and Gaussian-smoothed DEM
            ls = LightSource(
                azdeg=hs_cfg.get("azimuth", 315),
                altdeg=hs_cfg.get("altitude", 45),
            )
            shade = ls.hillshade(dem_smoothed, vert_exag=1, dx=dx, dy=dy)

            zorder = hs_cfg.get("zorder", 0)
            alpha = hs_cfg.get("alpha", 0.5)
            ax.imshow(
                shade,
                cmap=hs_cfg.get("cmap", "gray"),
                alpha=alpha,
                extent=[left, right, bottom, top],
                zorder=zorder,
                interpolation="bicubic",
                aspect="auto",  # keep hillshade aligned under custom axis aspect
            )

    # Sort layers by zorder to draw in the right sequence
    layers = sorted(cfg["layers"].items(), key=lambda kv: kv[1]["default"]["zorder"])

    for layer_key, layer_cfg in layers:
        # palette for cycling colors (if provided)
        layer_palette = layer_cfg["default"].get("palette", [])
        # only draw if both geometry-specific and category-level visibility are true
        if not (
            layer_cfg.get("visible", False)
            and layer_cfg["default"].get("visible", True)
        ):
            continue

        # Read directly from GeoPackage
        gdf = gpd.read_file(layer_cfg["file"], layer=layer_cfg["layer"])

        # Clip all layers to the mask if not empty
        if not mask_gdf.empty:
            # Special optimization for ocean layer: pre-filter by intersection with mask bounds
            if layer_cfg["layer"] == "ocean":
                mask_union = mask_gdf.union_all()
                gdf = gdf[gdf.intersects(mask_union.buffer(0.01))]
            gdf = gpd.clip(gdf, mask_gdf)
            # After clipping, further optimize for ocean by simplifying geometry
            if layer_cfg["layer"] == "ocean":
                gdf = gdf.simplify(tolerance=0.001, preserve_topology=True)

        # only keep features matching this entry’s geometry type
        geom_type = layer_cfg["geometry_type"]
        gdf = gdf[gdf.geom_type == geom_type]

        # Keep track of which features we styled
        styled_idx = set()

        # Style matching features based on attribute rules (e.g., road class, type)
        for attr in layer_cfg.get("style_order", []):
            rules = layer_cfg["style_rules"].get(attr, {})
            for val, style in rules.items():
                subset = gdf[gdf[attr].astype(str) == str(val)]
                if subset.empty:
                    continue
                styled_idx.update(subset.index)

                draw_style = layer_cfg["default"].copy()
                draw_style.update(style)
                # Get zorder from style, fallback to 2 for polygons, 2 for lines, 2 for points (default)
                zorder = draw_style.get("zorder", 2)

                # Determine drawing based on recorded geometry type
                geom = layer_cfg["geometry_type"].lower()
                # Polygon (Polygon or MultiPolygon)
                if geom.startswith("polygon"):
                    # Note: hatch_color currently not supported; to re-enable when Matplotlib adds support, uncomment the hatch_color argument below.
                    if layer_palette:
                        colors = [
                            layer_palette[i % len(layer_palette)]
                            for i in range(len(subset))
                        ]
                        subset.plot(
                            ax=ax,
                            facecolor=colors,
                            edgecolor=draw_style.get(
                                "edge_color", draw_style.get("ec")
                            ),
                            linewidth=draw_style.get("edge_width", 0.1),
                            alpha=draw_style.get("alpha", 1.0),
                            zorder=zorder,
                        )
                    else:
                        subset.plot(
                            ax=ax,
                            facecolor=draw_style["fc"],
                            edgecolor=draw_style.get(
                                "edge_color", draw_style.get("ec")
                            ),
                            linewidth=draw_style.get("edge_width", 0.1),
                            alpha=draw_style.get("alpha", 1.0),
                            zorder=zorder,
                        )
                # Point (Point or MultiPoint)
                elif geom.startswith("point"):
                    subset.plot(
                        ax=ax,
                        marker=draw_style.get("marker", "o"),
                        color=draw_style.get("fc"),
                        markersize=draw_style.get("size", 3),
                        alpha=draw_style.get("alpha", 1.0),
                        zorder=zorder,
                    )
                # Line (LineString or MultiLineString)
                else:
                    lw = draw_style.get("linewidth", draw_style.get("default_lw", 1.0))
                    subset.plot(
                        ax=ax,
                        color=draw_style.get("fc"),
                        linewidth=lw,
                        alpha=draw_style.get("alpha", 1.0),
                        zorder=zorder,
                    )

        # Draw any remaining features with the default style
        rest = gdf.loc[~gdf.index.isin(styled_idx)]
        if not rest.empty:
            dft = layer_cfg["default"]
            zorder = dft.get("zorder", 2)
            if layer_cfg["geometry_type"].lower().startswith("polygon"):
                # Note: hatch_color currently not supported; to re-enable when Matplotlib adds support, uncomment the hatch_color argument below.
                if layer_palette:
                    colors = [
                        layer_palette[i % len(layer_palette)] for i in range(len(rest))
                    ]
                    rest.plot(
                        ax=ax,
                        facecolor=colors,
                        edgecolor=dft.get("edge_color", dft.get("ec")),
                        linewidth=dft.get("edge_width", 0.1),
                        alpha=dft.get("alpha", 1.0),
                        zorder=zorder,
                    )
                else:
                    rest.plot(
                        ax=ax,
                        facecolor=dft["fc"],
                        edgecolor=dft.get("edge_color", dft.get("ec")),
                        linewidth=dft.get("edge_width", 0.1),
                        alpha=dft.get("alpha", 1.0),
                        zorder=zorder,
                    )
            elif "marker" in dft:
                rest.plot(
                    ax=ax,
                    marker=dft["marker"],
                    color=dft.get("fc"),
                    markersize=dft.get("size", 3),
                    alpha=dft.get("alpha", 1.0),
                    zorder=zorder,
                )
            else:
                # use config-defined linewidth for all remaining lines
                lw = dft.get("linewidth", 1.0)
                rest.plot(
                    ax=ax,
                    color=dft.get("fc"),
                    linewidth=lw,
                    alpha=dft.get("alpha", 1.0),
                    zorder=zorder,
                )

    # Set map extent and latitude-corrected aspect to fill canvas
    minx, miny, maxx, maxy = mask_gdf.total_bounds
    # compute center latitude
    avg_lat = (miny + maxy) / 2.0
    # adjust aspect so degrees are equal distances
    aspect = 1 / math.cos(math.radians(avg_lat))
    ax.set_aspect(aspect)
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)

    # Draw info text if enabled
    info = mcfg.get("info", {})
    if info.get("show", False) and info.get("text"):
        pos_map = {
            "top-left": (0.01, 0.99),
            "top-right": (0.99, 0.99),
            "bottom-left": (0.01, 0.01),
            "bottom-right": (0.99, 0.01),
        }
        x, y = pos_map.get(info["position"], (0.99, 0.01))
        ax.text(
            x,
            y,
            info["text"],
            transform=ax.transAxes,
            ha="right" if "right" in info["position"] else "left",
            va="top" if "top" in info["position"] else "bottom",
            font=info.get("font", "DejaVu Sans"),
            fontsize=info.get("fontsize", 10),
            color=info.get("color", "#000000"),
        )

    # always save to file
    fig.savefig(
        str(output_path),
        dpi=dpi,
        format=fmt,
        facecolor=fig.get_facecolor(),
        bbox_inches="tight",
        pad_inches=0,
    )
    plt.close(fig)


# ----------------------------
# Command-line interface (CLI)
# ----------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Draw a map from a YAML config and GeoJSON mask"
    )
    parser.add_argument("config", type=str, help="Path to the YAML configuration file")
    parser.add_argument(
        "-g", "--geojson", type=str, required=True, help="GeoJSON boundary (required)"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output file path (defaults to config basename.<format>)",
    )
    parser.add_argument(
        "-W",
        "--width",
        type=float,
        default=12.0,
        help="Map width in inches (default: 12)",
    )
    parser.add_argument(
        "-H",
        "--height",
        type=float,
        default=12.0,
        help="Map height in inches (default: 12)",
    )
    parser.add_argument(
        "--dpi", type=int, default=300, help="Output DPI (default: 300)"
    )
    parser.add_argument(
        "-f",
        "--format",
        dest="fmt",
        type=str,
        default=None,
        help="Output format (e.g. png, pdf). Defaults to png if not set.",
    )
    args = parser.parse_args()

    # Determine output format
    fmt_use = args.fmt if args.fmt is not None else "png"

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(args.config).with_suffix(f".{fmt_use}")

    draw_map_from_config(
        config_path=Path(args.config),
        geojson_path=Path(args.geojson),
        output_path=output_path,
        width=args.width,
        height=args.height,
        dpi=args.dpi,
        fmt=fmt_use,
    )
