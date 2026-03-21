#!/usr/bin/env python3
# Copyright (c) 2026 Paul Stothard
# SPDX-License-Identifier: MIT

import yaml
from pathlib import Path
import math

import argparse

import geopandas as gpd
import matplotlib.pyplot as plt
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_bounds
from rasterio.features import rasterize
from matplotlib.colors import LightSource, LinearSegmentedColormap, to_rgb
from scipy.ndimage import gaussian_filter
import numpy as np
from shapely.geometry import Polygon, Point
import pandas as pd
from geojson_bounds import apply_primary_segment_clip


def _normalize_array(arr: np.ndarray) -> np.ndarray:
    arr = np.asarray(arr, dtype=np.float32)
    finite = np.isfinite(arr)
    if not finite.any():
        return np.zeros_like(arr, dtype=np.float32)
    vmin = np.nanmin(arr[finite])
    vmax = np.nanmax(arr[finite])
    if np.isclose(vmin, vmax):
        out = np.zeros_like(arr, dtype=np.float32)
        out[finite] = 0.5
        return out
    out = np.zeros_like(arr, dtype=np.float32)
    out[finite] = (arr[finite] - vmin) / (vmax - vmin)
    return np.clip(out, 0.0, 1.0)


def _apply_elevation_stretch(
    normed: np.ndarray,
    stretch: str | None = None,
    exponent: float = 1.0,
) -> np.ndarray:
    arr = np.clip(np.asarray(normed, dtype=np.float32), 0.0, 1.0)
    stretch_name = (stretch or "linear").lower()

    if stretch_name == "linear":
        stretched = arr
    elif stretch_name == "gamma":
        exp = max(float(exponent), 1e-6)
        stretched = np.power(arr, exp)
    elif stretch_name == "sqrt":
        stretched = np.sqrt(arr)
    elif stretch_name == "square":
        stretched = np.square(arr)
    else:
        stretched = arr

    return np.clip(stretched, 0.0, 1.0)


def _normalize_dem_for_colormap(
    dem: np.ndarray,
    finite_mask: np.ndarray,
    percentiles: list[float] | tuple[float, float],
    elevation_mode: str = "percentiles",
    elevation_cutoffs: list[float] | tuple[float, ...] | None = None,
    stretch: str | None = None,
    exponent: float = 1.0,
) -> np.ndarray:
    mode = (elevation_mode or "percentiles").lower()

    if mode == "cutoffs" and elevation_cutoffs:
        cutoffs = np.asarray(elevation_cutoffs, dtype=np.float32)
        cutoffs = cutoffs[np.isfinite(cutoffs)]
        cutoffs = np.unique(cutoffs)
        if cutoffs.size >= 2:
            anchors = np.linspace(0.0, 1.0, cutoffs.size, dtype=np.float32)
            normed = np.zeros_like(dem, dtype=np.float32)
            normed[finite_mask] = np.interp(dem[finite_mask], cutoffs, anchors)
        else:
            mode = "percentiles"

    if mode != "cutoffs":
        p_low, p_high = np.nanpercentile(dem[finite_mask], percentiles)
        if np.isclose(p_low, p_high):
            p_low = float(np.nanmin(dem[finite_mask]))
            p_high = float(np.nanmax(dem[finite_mask]))
            if np.isclose(p_low, p_high):
                p_high = p_low + 1.0

        normed = (dem - p_low) / (p_high - p_low)
        normed = np.clip(normed, 0.0, 1.0)

    normed = _apply_elevation_stretch(
        normed,
        stretch=stretch,
        exponent=exponent,
    )
    normed[~finite_mask] = 0.0
    return normed


def _blend_multiply(
    base_rgb: np.ndarray, shade: np.ndarray, strength: float
) -> np.ndarray:
    shade_rgb = np.repeat(shade[..., np.newaxis], 3, axis=2)
    multiplied = base_rgb * shade_rgb
    return np.clip(base_rgb * (1.0 - strength) + multiplied * strength, 0.0, 1.0)


def _blend_soft_light(
    base_rgb: np.ndarray, shade: np.ndarray, strength: float
) -> np.ndarray:
    shade_rgb = np.repeat(shade[..., np.newaxis], 3, axis=2)
    soft = np.where(
        shade_rgb <= 0.5,
        base_rgb - (1.0 - 2.0 * shade_rgb) * base_rgb * (1.0 - base_rgb),
        base_rgb
        + (2.0 * shade_rgb - 1.0) * (np.sqrt(np.clip(base_rgb, 0.0, 1.0)) - base_rgb),
    )
    return np.clip(base_rgb * (1.0 - strength) + soft * strength, 0.0, 1.0)


def _make_hypsometric_colormap(
    colors: list[str] | None = None,
) -> LinearSegmentedColormap:
    default_colors = [
        "#132B43",
        "#255D83",
        "#4D8DA6",
        "#7FAE7B",
        "#B8C98A",
        "#D7C29E",
        "#A9835A",
        "#7A5D45",
        "#F2F1ED",
    ]
    return LinearSegmentedColormap.from_list(
        "map_artistry_hypsometric", colors or default_colors
    )


def _modulate_rgb(rgb: np.ndarray, variation: np.ndarray) -> np.ndarray:
    base = np.asarray(rgb, dtype=np.float32).reshape(1, 1, 3)
    factors = np.clip(1.0 + variation[..., np.newaxis], 0.0, 2.0)
    return np.clip(base * factors, 0.0, 1.0)


def _prepare_water_hillshade_texture(
    shade: np.ndarray,
    blur_sigma: float,
    contrast: float,
    bias: float,
) -> np.ndarray:
    water_shade = gaussian_filter(np.asarray(shade, dtype=np.float32), sigma=blur_sigma)
    water_tone = 0.5 + (water_shade - 0.5) * contrast
    water_tone = np.clip(water_tone + bias, 0.0, 1.0)
    return water_tone.astype(np.float32)


# --- New helper functions for advanced hillshade/tint/multiscale ---
def _apply_hillshade_tone(
    shade: np.ndarray,
    clip_low: float = 0.0,
    clip_high: float = 1.0,
    contrast: float = 1.0,
    gamma: float = 1.0,
    bias: float = 0.0,
    ambient: float = 0.0,
) -> np.ndarray:
    arr = np.asarray(shade, dtype=np.float32)
    lo = float(np.clip(clip_low, 0.0, 1.0))
    hi = float(np.clip(clip_high, 0.0, 1.0))
    if hi <= lo:
        hi = min(1.0, lo + 1e-3)

    arr = np.clip(arr, lo, hi)
    arr = (arr - lo) / (hi - lo)

    ctr = max(float(contrast), 0.0)
    arr = 0.5 + (arr - 0.5) * ctr
    arr = np.clip(arr, 0.0, 1.0)

    gam = max(float(gamma), 1e-6)
    arr = np.power(arr, gam)

    amb = float(np.clip(ambient, 0.0, 1.0))
    if amb > 0:
        arr = amb + (1.0 - amb) * arr

    arr = np.clip(arr + float(bias), 0.0, 1.0)
    return arr.astype(np.float32)


def _hillshade_to_tinted_rgb(
    shade: np.ndarray,
    shadow_color: str,
    mid_color: str,
    highlight_color: str,
) -> np.ndarray:
    shade_arr = np.clip(np.asarray(shade, dtype=np.float32), 0.0, 1.0)
    shadow = np.array(to_rgb(shadow_color), dtype=np.float32)
    mid = np.array(to_rgb(mid_color), dtype=np.float32)
    highlight = np.array(to_rgb(highlight_color), dtype=np.float32)

    rgb = np.empty(shade_arr.shape + (3,), dtype=np.float32)
    lower = shade_arr <= 0.5
    upper = ~lower

    if np.any(lower):
        t = (shade_arr[lower] / 0.5).astype(np.float32)
        rgb[lower] = shadow * (1.0 - t[:, np.newaxis]) + mid * t[:, np.newaxis]
    if np.any(upper):
        t = ((shade_arr[upper] - 0.5) / 0.5).astype(np.float32)
        rgb[upper] = mid * (1.0 - t[:, np.newaxis]) + highlight * t[:, np.newaxis]

    return np.clip(rgb, 0.0, 1.0)


def _compute_multiscale_hillshade(
    dem: np.ndarray,
    dx: float,
    dy: float,
    altitude: float,
    azimuths: list[float],
    weights: list[float] | None = None,
    vert_exag: float = 1.0,
    multiscale_cfg: dict | None = None,
) -> np.ndarray:
    cfg = multiscale_cfg or {}
    enabled = bool(cfg.get("enabled", False))
    scales = cfg.get("scales") or []

    if not enabled or not scales:
        return _compute_multidirectional_hillshade(
            dem=dem,
            dx=dx,
            dy=dy,
            altitude=altitude,
            azimuths=azimuths,
            weights=weights,
            vert_exag=vert_exag,
        )

    combined = np.zeros_like(dem, dtype=np.float32)
    total_weight = 0.0

    for scale in scales:
        if not isinstance(scale, dict):
            continue
        sigma = float(scale.get("sigma", 0.0) or 0.0)
        weight = float(scale.get("weight", 1.0) or 1.0)
        if weight <= 0:
            continue

        if sigma > 0:
            dem_scale = gaussian_filter(dem, sigma=sigma)
        else:
            dem_scale = dem

        shade_scale = _compute_multidirectional_hillshade(
            dem=dem_scale,
            dx=dx,
            dy=dy,
            altitude=altitude,
            azimuths=azimuths,
            weights=weights,
            vert_exag=vert_exag,
        )
        combined += shade_scale.astype(np.float32) * weight
        total_weight += weight

    if total_weight <= 0:
        return _compute_multidirectional_hillshade(
            dem=dem,
            dx=dx,
            dy=dy,
            altitude=altitude,
            azimuths=azimuths,
            weights=weights,
            vert_exag=vert_exag,
        )

    return _normalize_array(combined / total_weight)


def _render_hillshade_textured_polygon_fill(
    ax,
    gdf: gpd.GeoDataFrame,
    style: dict,
    canvas_width_px: int,
    canvas_height_px: int,
    raster_left: float,
    raster_bottom: float,
    raster_right: float,
    raster_top: float,
    water_tone: np.ndarray | None,
    water_valid: np.ndarray | None,
) -> bool:
    hs_cfg = style.get("hillshade_texture", {})
    if not hs_cfg.get("visible", False) or gdf.empty or water_tone is None:
        return False

    geoms = [geom for geom in gdf.geometry if geom is not None and not geom.is_empty]
    if not geoms:
        return False

    xmin, ymin, xmax, ymax = gdf.total_bounds
    if not np.isfinite([xmin, ymin, xmax, ymax]).all():
        return False
    if np.isclose(xmin, xmax) or np.isclose(ymin, ymax):
        return False

    max_dim = int(hs_cfg.get("max_texture_dim", 1024))
    tex_width = int(hs_cfg.get("width", min(max(canvas_width_px, 256), max_dim)))
    tex_height = int(hs_cfg.get("height", min(max(canvas_height_px, 256), max_dim)))
    tex_width = max(min(tex_width, max_dim), 64)
    tex_height = max(min(tex_height, max_dim), 64)

    transform = from_bounds(xmin, ymin, xmax, ymax, tex_width, tex_height)
    mask = rasterize(
        [(geom, 1) for geom in geoms],
        out_shape=(tex_height, tex_width),
        transform=transform,
        fill=0,
        dtype="uint8",
    )
    if not np.any(mask):
        return False

    src_h, src_w = water_tone.shape
    src_transform = from_bounds(
        raster_left, raster_bottom, raster_right, raster_top, src_w, src_h
    )
    sampled_tone = np.full((tex_height, tex_width), 0.5, dtype=np.float32)
    reproject(
        source=water_tone,
        destination=sampled_tone,
        src_transform=src_transform,
        src_crs=gdf.crs,
        dst_transform=transform,
        dst_crs=gdf.crs,
        resampling=Resampling.bilinear,
    )

    sampled_valid = None
    if water_valid is not None:
        sampled_valid = np.zeros((tex_height, tex_width), dtype=np.uint8)
        reproject(
            source=water_valid.astype(np.uint8),
            destination=sampled_valid,
            src_transform=src_transform,
            src_crs=gdf.crs,
            dst_transform=transform,
            dst_crs=gdf.crs,
            resampling=Resampling.nearest,
        )

    strength = float(hs_cfg.get("strength", 0.10))
    variation = (sampled_tone - 0.5) * 2.0 * strength
    if sampled_valid is not None:
        valid_float = sampled_valid.astype(np.float32)
        variation = variation * np.clip(valid_float, 0.15, 1.0)

    base_rgb = np.array(to_rgb(style.get("fc", "#000000")), dtype=np.float32)
    textured_rgb = _modulate_rgb(base_rgb, variation)

    # Lay down a solid base fill first so any raster mask/interpolation edge
    # artifacts in the textured overlay don't expose the background.
    gdf.plot(
        ax=ax,
        facecolor=style.get("fc", "#000000"),
        edgecolor="none",
        linewidth=0,
        alpha=style.get("alpha", 1.0),
        zorder=style.get("zorder", 2),
    )

    img = np.zeros((tex_height, tex_width, 4), dtype=np.float32)
    img[..., :3] = textured_rgb
    img[..., 3] = mask.astype(np.float32) * float(style.get("alpha", 1.0))

    ax.imshow(
        img,
        extent=[xmin, xmax, ymin, ymax],
        interpolation=hs_cfg.get("interpolation", "bilinear"),
        zorder=style.get("zorder", 2),
        aspect="auto",
    )
    return True


def _compute_multidirectional_hillshade(
    dem: np.ndarray,
    dx: float,
    dy: float,
    altitude: float,
    azimuths: list[float],
    weights: list[float] | None = None,
    vert_exag: float = 1.0,
) -> np.ndarray:
    if not azimuths:
        azimuths = [315.0]
    if weights is None:
        weights = [1.0] * len(azimuths)
    if len(weights) != len(azimuths):
        weights = [1.0] * len(azimuths)

    shades = []
    valid_weights = []
    for az, weight in zip(azimuths, weights):
        w = float(weight)
        if w <= 0:
            continue
        ls = LightSource(azdeg=az, altdeg=altitude)
        shade = ls.hillshade(dem, vert_exag=vert_exag, dx=dx, dy=dy)
        shades.append(shade * w)
        valid_weights.append(w)

    if not shades:
        ls = LightSource(azdeg=315, altdeg=altitude)
        return _normalize_array(ls.hillshade(dem, vert_exag=vert_exag, dx=dx, dy=dy))

    combined = np.sum(shades, axis=0) / np.sum(valid_weights)
    return _normalize_array(combined)


def _rasterize_polygon_layer_mask(
    layers_cfg: dict,
    mask_gdf: gpd.GeoDataFrame,
    target_transform,
    width_px: int,
    height_px: int,
    layer_names: str | list[str] | tuple[str, ...] | set[str],
) -> np.ndarray | None:
    """Rasterize polygon features from one or more named layers into the DEM target grid."""
    if isinstance(layer_names, str):
        layer_names = {layer_names}
    else:
        layer_names = set(layer_names)

    geoms = []
    seen_sources = set()
    mask_union = None if mask_gdf.empty else mask_gdf.union_all()

    for layer_cfg in layers_cfg.values():
        if layer_cfg.get("layer") not in layer_names:
            continue

        source_key = (layer_cfg.get("file"), layer_cfg.get("layer"))
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)

        try:
            gdf = gpd.read_file(
                layer_cfg["file"],
                layer=layer_cfg["layer"],
                engine="pyogrio",
                use_arrow=True,
            )
        except (FileNotFoundError, Exception):
            continue

        if gdf.empty:
            continue
        if mask_gdf.crs is not None and gdf.crs != mask_gdf.crs:
            gdf = gdf.to_crs(mask_gdf.crs)

        gdf = gdf[gdf.geometry.notnull()]
        gdf = gdf[~gdf.is_empty]
        gdf = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon"])]
        if gdf.empty:
            continue

        if mask_union is not None:
            gdf = gdf[gdf.intersects(mask_union)]
            if gdf.empty:
                continue
            gdf = gpd.clip(gdf, mask_gdf)
            gdf = gdf[gdf.geometry.notnull()]
            gdf = gdf[~gdf.is_empty]
            if gdf.empty:
                continue

        geoms.extend(
            [geom for geom in gdf.geometry if geom is not None and not geom.is_empty]
        )

    if not geoms:
        return None

    return rasterize(
        [(geom, 1) for geom in geoms],
        out_shape=(height_px, width_px),
        transform=target_transform,
        fill=0,
        dtype="uint8",
    ).astype(bool)


def _get_layer_fill_color(
    layers_cfg: dict,
    layer_names: list[str] | tuple[str, ...],
    fallback: str,
) -> str:
    for layer_name in layer_names:
        for layer_cfg in layers_cfg.values():
            if layer_cfg.get("layer") != layer_name:
                continue
            geom_type = str(layer_cfg.get("geometry_type", "")).lower()
            if "polygon" not in geom_type:
                continue
            default_style = layer_cfg.get("default", {})
            fill_color = default_style.get("fc")
            if fill_color:
                return fill_color
    return fallback


def draw_map_from_config(
    config_path: Path,
    geojson_path: Path,
    output_path: Path,
    width: float = 12,
    height: float = 12,
    dpi: int = 300,
    fmt: str = "png",
    fit_content: bool = False,
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
    canvas_width_px = int(width * dpi)
    canvas_height_px = int(height * dpi)
    water_tone = None
    water_valid = None
    # Load clipping mask (used both for layer clipping and extent)
    try:
        mask_gdf = gpd.read_file(geojson_path, engine="pyogrio", use_arrow=True)
    except (FileNotFoundError, Exception) as e:
        print(f"Error: Could not read mask file '{geojson_path}': {e}")
        return

    if mask_gdf.crs is None:
        mask_gdf = mask_gdf.set_crs("EPSG:4326")
    else:
        mask_gdf = mask_gdf.to_crs("EPSG:4326")

    mask_gdf = mask_gdf[mask_gdf.geometry.notnull()]
    mask_gdf = mask_gdf[~mask_gdf.is_empty]
    if mask_gdf.empty:
        print(f"Error: Mask file '{geojson_path}' has no valid geometry")
        return

    mask_gdf, primary_segment, antimeridian_clipped = apply_primary_segment_clip(
        mask_gdf
    )
    if antimeridian_clipped:
        print(
            "[ ] Antimeridian boundary detected; "
            f"using primary segment bounds: {primary_segment}"
        )

    # Background
    bg = mcfg.get("background", {})
    face_fc = bg.get("fc", "#ffffff")
    fig.patch.set_facecolor(face_fc)
    ax.set_facecolor(face_fc)
    ax.set_axis_off()

    # --- Render satellite image underlay if configured (drawn immediately after background) ---
    satellite_cfg = cfg.get("map", {}).get("satellite")
    if satellite_cfg and satellite_cfg.get("visible", True):
        try:
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
        except (FileNotFoundError, rasterio.errors.RasterioIOError) as e:
            print(
                f"Warning: Could not read satellite image '{satellite_cfg['path']}': {e}"
            )

    # --- Render terrain underlay if DEM is configured ---
    dem_path = mcfg.get("dem")
    hs_cfg = mcfg.get("hillshade", {})
    terrain_cfg = mcfg.get("terrain", {})
    if dem_path:
        try:
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

                water_exclusion_mask = _rasterize_polygon_layer_mask(
                    cfg.get("layers", {}),
                    mask_gdf,
                    target_transform,
                    width_px,
                    height_px,
                    layer_names={"ocean", "water"},
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
                    resampling=Resampling.cubic,
                )

                # mask nodata values if present
                nodata = dem_ds.nodata
                if nodata is not None:
                    dem_resampled = np.where(
                        np.isclose(dem_resampled, nodata), np.nan, dem_resampled
                    )

                finite = np.isfinite(dem_resampled)
                if not finite.any():
                    raise ValueError("DEM contains no finite values after resampling")

                # fill invalid cells so filters and hillshade do not propagate NaNs
                fill_value = float(np.nanmedian(dem_resampled[finite]))
                dem_filled = np.where(finite, dem_resampled, fill_value)

                # Optional Gaussian smoothing (sigma=0 means no blur)
                sigma = hs_cfg.get("sigma", 0.0)
                if sigma > 0:
                    dem_smoothed = gaussian_filter(dem_filled, sigma=sigma)
                else:
                    dem_smoothed = dem_filled

                # compute pixel sizes in map units
                dx = target_transform.a
                dy = -target_transform.e

                # terrain styling controls
                altitude = hs_cfg.get("altitude", 45)
                vert_exag = hs_cfg.get("vert_exag", 1.0)
                multidirectional = hs_cfg.get("multidirectional", True)
                azimuth = hs_cfg.get("azimuth", 315)
                azimuths = hs_cfg.get("azimuths")
                if azimuths is None:
                    azimuths = [315, 45, 270, 90] if multidirectional else [azimuth]
                weights = hs_cfg.get("weights")

                multiscale_cfg = hs_cfg.get("multiscale", {})
                shade = _compute_multiscale_hillshade(
                    dem=dem_smoothed,
                    dx=dx,
                    dy=dy,
                    altitude=altitude,
                    azimuths=azimuths,
                    weights=weights,
                    vert_exag=vert_exag,
                    multiscale_cfg=multiscale_cfg,
                )

                # Apply unsharp masking to enhance detail
                unsharp_radius = hs_cfg.get("unsharp_radius", 0.0)
                unsharp_amount = hs_cfg.get("unsharp_amount", 0.0)
                if unsharp_radius > 0 and unsharp_amount > 0:
                    shade_blurred = gaussian_filter(shade, sigma=unsharp_radius)
                    shade = shade + unsharp_amount * (shade - shade_blurred)
                    shade = np.clip(shade, 0, 1)

                tone_cfg = hs_cfg.get("tone", {})
                shade = _apply_hillshade_tone(
                    shade,
                    clip_low=tone_cfg.get("clip_low", 0.0),
                    clip_high=tone_cfg.get("clip_high", 1.0),
                    contrast=tone_cfg.get("contrast", 1.0),
                    gamma=tone_cfg.get("gamma", 1.0),
                    bias=tone_cfg.get("bias", 0.0),
                    ambient=tone_cfg.get("ambient", 0.0),
                )

                hillshade_render_mode = str(hs_cfg.get("render_mode", "cmap")).lower()
                hillshade_rgb = None
                if hillshade_render_mode == "tinted":
                    tint_cfg = hs_cfg.get("tint", {})
                    hillshade_rgb = _hillshade_to_tinted_rgb(
                        shade,
                        shadow_color=tint_cfg.get("shadow_color", "#0b0f14"),
                        mid_color=tint_cfg.get("mid_color", "#5f6368"),
                        highlight_color=tint_cfg.get("highlight_color", "#f3f1eb"),
                    )

                # keep invalid DEM cells transparent / background-colored for land rendering
                shade = np.where(finite, shade, 1.0)
                if hillshade_rgb is not None:
                    bg_rgb = np.array(to_rgb(face_fc), dtype=np.float32)
                    hillshade_rgb = np.where(
                        finite[..., np.newaxis],
                        hillshade_rgb,
                        bg_rgb[np.newaxis, np.newaxis, :],
                    )

                # Build water tone from a finite-aware normalized blur so coastal hillshade
                # can influence nearby ocean instead of nodata becoming flat white.
                water_hs_cfg = mcfg.get("water_hillshade", {})
                blur_sigma = float(water_hs_cfg.get("blur_sigma", 8.0))
                contrast = float(water_hs_cfg.get("contrast", 0.35))
                bias = float(water_hs_cfg.get("bias", 0.03))

                shade_src = np.where(finite, shade, 0.0).astype(np.float32)
                weight_src = finite.astype(np.float32)

                blurred_shade = gaussian_filter(shade_src, sigma=blur_sigma)
                blurred_weight = gaussian_filter(weight_src, sigma=blur_sigma)

                water_tone = np.full_like(shade, 0.5, dtype=np.float32)
                valid_blur = blurred_weight > 1e-6
                water_tone[valid_blur] = (
                    blurred_shade[valid_blur] / blurred_weight[valid_blur]
                )

                water_tone = 0.5 + (water_tone - 0.5) * contrast
                water_tone = np.clip(water_tone + bias, 0.0, 1.0).astype(np.float32)

                water_valid = (blurred_weight > 0.002).astype(np.uint8)

                terrain_visible = terrain_cfg.get("visible", False)
                if terrain_visible:
                    elev_percentiles = terrain_cfg.get("percentiles", [2, 98])
                    elevation_mode = terrain_cfg.get("elevation_mode", "percentiles")
                    elevation_cutoffs = terrain_cfg.get("elevation_cutoffs")
                    stretch = terrain_cfg.get("stretch", "linear")
                    stretch_exponent = terrain_cfg.get("stretch_exponent", 1.0)
                    terrain_scale_mask = finite.copy()
                    if water_exclusion_mask is not None:
                        terrain_scale_mask &= ~water_exclusion_mask
                    else:
                        terrain_scale_mask &= dem_resampled > 0

                    if not terrain_scale_mask.any():
                        terrain_scale_mask = finite

                    # Use dem_resampled for terrain coloring
                    terrain_norm = _normalize_dem_for_colormap(
                        dem_resampled,
                        finite_mask=terrain_scale_mask,
                        percentiles=elev_percentiles,
                        elevation_mode=elevation_mode,
                        elevation_cutoffs=elevation_cutoffs,
                        stretch=stretch,
                        exponent=stretch_exponent,
                    )

                    cmap = _make_hypsometric_colormap(terrain_cfg.get("colors"))
                    terrain_rgb = cmap(terrain_norm)[..., :3]

                    invalid_rgb = np.array(plt.matplotlib.colors.to_rgb(face_fc))
                    water_fill_fc = _get_layer_fill_color(
                        cfg.get("layers", {}),
                        ("ocean", "water"),
                        face_fc,
                    )
                    water_fill_rgb = np.array(
                        plt.matplotlib.colors.to_rgb(water_fill_fc)
                    )
                    terrain_rgb[~finite] = invalid_rgb
                    if water_exclusion_mask is not None:
                        terrain_rgb[water_exclusion_mask] = water_fill_rgb

                    blend_mode = terrain_cfg.get("blend_mode", "soft_light")
                    shade_strength = terrain_cfg.get("shade_strength", 0.6)
                    if blend_mode == "multiply":
                        terrain_img = _blend_multiply(
                            terrain_rgb, shade, shade_strength
                        )
                    else:
                        terrain_img = _blend_soft_light(
                            terrain_rgb, shade, shade_strength
                        )

                    ax.imshow(
                        terrain_img,
                        extent=[left, right, bottom, top],
                        zorder=terrain_cfg.get("zorder", hs_cfg.get("zorder", 0)),
                        alpha=terrain_cfg.get("alpha", 1.0),
                        interpolation=terrain_cfg.get("interpolation", "bicubic"),
                        aspect="auto",
                    )
                else:
                    hillshade_alpha = hs_cfg.get("alpha", 0.5)
                    if hillshade_rgb is not None:
                        rgba = np.empty(
                            hillshade_rgb.shape[:2] + (4,), dtype=np.float32
                        )
                        rgba[..., :3] = hillshade_rgb
                        rgba[..., 3] = float(hillshade_alpha)
                        ax.imshow(
                            rgba,
                            extent=[left, right, bottom, top],
                            zorder=hs_cfg.get("zorder", 0),
                            interpolation=hs_cfg.get("interpolation", "bicubic"),
                            aspect="auto",
                        )
                    else:
                        ax.imshow(
                            shade,
                            cmap=hs_cfg.get("cmap", "gray"),
                            alpha=hillshade_alpha,
                            extent=[left, right, bottom, top],
                            zorder=hs_cfg.get("zorder", 0),
                            interpolation=hs_cfg.get("interpolation", "bicubic"),
                            aspect="auto",
                        )
        except (FileNotFoundError, rasterio.errors.RasterioIOError, ValueError) as e:
            print(f"Warning: Could not read DEM file '{dem_path}': {e}")

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

        try:
            # Read directly from GeoPackage
            gdf = gpd.read_file(
                layer_cfg["file"],
                layer=layer_cfg["layer"],
                engine="pyogrio",
                use_arrow=True,
            )
        except (FileNotFoundError, Exception) as e:
            print(
                f"Warning: Could not read layer '{layer_key}' from '{layer_cfg['file']}': {e}"
            )
            continue

        # Clip all layers to the mask if not empty
        if not mask_gdf.empty:
            # Special optimization for ocean layer: pre-filter by intersection with mask bounds
            if layer_cfg["layer"] == "ocean":
                mask_union = mask_gdf.union_all()
                gdf = gdf[gdf.intersects(mask_union.buffer(0.01))]
            gdf = gpd.clip(gdf, mask_gdf)
            # After clipping, further optimize for ocean by simplifying geometry
            if layer_cfg["layer"] == "ocean":
                gdf["geometry"] = gdf.simplify(tolerance=0.001, preserve_topology=True)

        # only keep features matching this entry’s geometry type
        geom_type = layer_cfg["geometry_type"]
        gdf = gdf[gdf.geom_type == geom_type]

        # Keep track of which features we styled
        styled_idx = set()

        # Style matching features based on attribute rules (e.g., road class, type)
        for attr in layer_cfg.get("style_order", []):
            if attr not in gdf.columns:
                continue
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
                if "polygon" in geom:
                    textured = False
                    if not layer_palette and layer_cfg["layer"] == "ocean":
                        textured = _render_hillshade_textured_polygon_fill(
                            ax=ax,
                            gdf=subset,
                            style=draw_style,
                            canvas_width_px=canvas_width_px,
                            canvas_height_px=canvas_height_px,
                            raster_left=left,
                            raster_bottom=bottom,
                            raster_right=right,
                            raster_top=top,
                            water_tone=water_tone,
                            water_valid=water_valid,
                        )

                    if textured:
                        edge_width = draw_style.get("edge_width", 0.1)
                        edge_color = draw_style.get("edge_color", draw_style.get("ec"))
                        if edge_width > 0:
                            subset.boundary.plot(
                                ax=ax,
                                color=edge_color,
                                linewidth=edge_width,
                                alpha=draw_style.get("alpha", 1.0),
                                zorder=zorder + 0.01,
                            )
                    elif layer_palette:
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
            geom_type_lower = layer_cfg["geometry_type"].lower()
            if "polygon" in geom_type_lower:
                textured = False
                if not layer_palette and layer_cfg["layer"] == "ocean":
                    textured = _render_hillshade_textured_polygon_fill(
                        ax=ax,
                        gdf=rest,
                        style=dft,
                        canvas_width_px=canvas_width_px,
                        canvas_height_px=canvas_height_px,
                        raster_left=left,
                        raster_bottom=bottom,
                        raster_right=right,
                        raster_top=top,
                        water_tone=water_tone,
                        water_valid=water_valid,
                    )

                if textured:
                    edge_width = dft.get("edge_width", 0.1)
                    edge_color = dft.get("edge_color", dft.get("ec"))
                    if edge_width > 0:
                        rest.boundary.plot(
                            ax=ax,
                            color=edge_color,
                            linewidth=edge_width,
                            alpha=dft.get("alpha", 1.0),
                            zorder=zorder + 0.01,
                        )
                elif layer_palette:
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
    if fit_content:
        ax.set_xlim(minx, maxx)
        ax.set_ylim(miny, maxy)
    else:
        # crop view to fill requested dimensions, chopping edges as needed
        target = (width / height) * aspect
        dx = maxx - minx
        dy = maxy - miny
        if dx / dy < target:
            # narrow map: crop top/bottom
            new_dy = dx / target
            center_y = avg_lat
            y0 = center_y - new_dy / 2
            y1 = center_y + new_dy / 2
            ax.set_xlim(minx, maxx)
            ax.set_ylim(y0, y1)
        else:
            # wide map: crop left/right
            new_dx = dy * target
            center_x = (minx + maxx) / 2
            x0 = center_x - new_dx / 2
            x1 = center_x + new_dx / 2
            ax.set_xlim(x0, x1)
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
            zorder=100,
        )

    # always save to file
    fig.savefig(
        str(output_path),
        dpi=dpi,
        format=fmt,
        facecolor=fig.get_facecolor(),
        bbox_inches="tight" if fit_content else None,
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
    parser.add_argument(
        "--fit-content",
        action="store_true",
        help="Maintain map content fit within requested dimensions without cropping (current behavior)",
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
        fit_content=args.fit_content,
    )
