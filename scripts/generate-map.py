#!/usr/bin/env python3
# Copyright (c) 2026 Paul Stothard
# SPDX-License-Identifier: MIT

import yaml
from pathlib import Path
import math

import argparse
import xml.etree.ElementTree as ET

import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.patches as mpatches
from matplotlib.path import Path as MplPath
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_bounds
from rasterio.features import rasterize
from matplotlib.colors import LightSource, LinearSegmentedColormap, to_rgb
from matplotlib.offsetbox import AnnotationBbox, DrawingArea
from scipy.ndimage import gaussian_filter
import numpy as np
from shapely.geometry import Polygon, Point
import pandas as pd
from geojson_bounds import apply_primary_segment_clip

# Configure matplotlib for high-quality PDF output with embedded fonts
plt.rcParams["pdf.fonttype"] = 42  # TrueType fonts (not Type 3 bitmapped)
plt.rcParams["ps.fonttype"] = 42  # Also for PostScript
plt.rcParams["font.family"] = "sans-serif"

IMPERIAL_COUNTRY_CODES = {"US", "LR", "MM"}


def _boundary_clip_patch(mask_gdf, ax):
    """Build an invisible PathPatch from the map boundary for raster clipping."""
    boundary = mask_gdf.union_all()
    if boundary is None or boundary.is_empty:
        return None
    if boundary.geom_type == "MultiPolygon":
        polys = list(boundary.geoms)
    elif boundary.geom_type == "Polygon":
        polys = [boundary]
    else:
        return None
    vertices, codes = [], []
    for poly in polys:
        for ring in [poly.exterior] + list(poly.interiors):
            coords = np.array(ring.coords)
            n = len(coords)
            codes += [MplPath.MOVETO] + [MplPath.LINETO] * (n - 2) + [MplPath.CLOSEPOLY]
            vertices.append(coords)
    if not vertices:
        return None
    path = MplPath(np.concatenate(vertices, axis=0), codes)
    patch = mpatches.PathPatch(
        path, facecolor="none", edgecolor="none", transform=ax.transData
    )
    ax.add_patch(patch)
    return patch


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


def _render_info_panel(fig, ax, panel_cfg, config, use_separate_axes=False):
    """
    Render an info panel (footer/header) with text, stats, and future graph support.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        The figure object
    ax : matplotlib.axes.Axes
        The axes object (either panel axes or map axes)
    panel_cfg : dict
        Info panel configuration from YAML
    config : dict
        Full configuration dict
    use_separate_axes : bool
        If True, ax is a dedicated panel axes; if False, panel overlays on map axes
    """
    if not panel_cfg or not panel_cfg.get("enabled", False):
        return

    elements = panel_cfg.get("elements", [])

    def _panel_has_content(panel_elements):
        for element in panel_elements:
            elem_type = element.get("type")
            if elem_type in ["title", "text"]:
                if str(element.get("content", "")).strip():
                    return True
            elif elem_type == "stats":
                items = element.get("items", [])
                for item in items:
                    if (
                        str(item.get("value", "")).strip()
                        or str(item.get("label", "")).strip()
                    ):
                        return True
        return False

    if not _panel_has_content(elements):
        return

    # Panel parameters
    bg_config = panel_cfg.get("background", {})
    bg_color = bg_config.get("color", "#ffffff")
    bg_alpha = bg_config.get("alpha", 1.0)
    zorder = panel_cfg.get("zorder", 1000)

    if use_separate_axes:
        # Dedicated panel axes - set background and remove ticks/spines
        ax.set_facecolor(bg_color)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)

        # Panel coordinates are just 0-1 in this axes
        panel_y0 = 0.0
        panel_y1 = 1.0
    else:
        # Overlay on map axes - draw rectangle
        position = panel_cfg.get("position", "bottom")
        height_frac = panel_cfg.get("height", 0.12)

        if position == "bottom":
            panel_y0 = 0.0
            panel_y1 = height_frac
        elif position == "top":
            panel_y0 = 1.0 - height_frac
            panel_y1 = 1.0
        else:
            panel_y0 = 0.0
            panel_y1 = height_frac

        # Draw panel background
        from matplotlib.patches import Rectangle

        panel_rect = Rectangle(
            (0, panel_y0),
            1.0,
            panel_y1 - panel_y0,
            transform=ax.transAxes,
            facecolor=bg_color,
            edgecolor="none",
            alpha=bg_alpha,
            zorder=zorder,
        )
        ax.add_patch(panel_rect)

    # Get panel dimensions in points for font sizing
    fig_width, fig_height = fig.get_size_inches()
    fig_dpi = fig.dpi

    if use_separate_axes:
        # Panel axes height is the full axes height
        panel_height_frac = panel_cfg.get("height", 0.12)
        panel_height_inches = fig_height * panel_height_frac
    else:
        # Panel overlays part of the map axes
        height_frac = panel_cfg.get("height", 0.12)
        panel_height_inches = fig_height * height_frac

    panel_height_pts = panel_height_inches * 72  # points

    # Render elements
    for element in elements:
        elem_type = element.get("type")

        if elem_type in ["title", "text"]:
            _render_panel_text_element(
                ax, element, panel_y0, panel_y1, panel_height_pts, zorder + 1
            )
        elif elem_type == "stats":
            _render_panel_stats_element(
                ax, element, panel_y0, panel_y1, panel_height_pts, zorder + 1
            )


def _render_panel_text_element(
    ax, element, panel_y0, panel_y1, panel_height_pts, zorder
):
    """Render a text element within the info panel."""
    # Get element properties
    content = element.get("content", "")
    if not content:
        return

    # Transform settings
    transform_type = element.get("transform", "none")
    if transform_type == "uppercase":
        content = content.upper()
    elif transform_type == "lowercase":
        content = content.lower()

    # Position (relative to panel: 0-1)
    x_rel = element.get("x", 0.5)
    y_rel = element.get("y", 0.5)

    # Convert to axes coordinates
    panel_height = panel_y1 - panel_y0
    y_axes = panel_y0 + (y_rel * panel_height)

    # Font properties
    font_family = element.get("font", "Inter")
    font_weight = element.get("font_weight", "normal")
    size_frac = element.get("size", 0.2)  # fraction of panel height
    fontsize = size_frac * panel_height_pts

    color = element.get("color", "#000000")
    alpha = element.get("alpha", 1.0)
    align = element.get("align", "left")
    tracking = element.get("tracking", 0.0)

    # Apply letter spacing if needed
    text = content
    if tracking > 0:
        spaced_text = text[0] if text else ""
        for char in text[1:]:
            spaced_text += "\u200a" * max(1, int(tracking * 10)) + char
        text = spaced_text

    # Auto-shrink title if it overflows the available panel width
    fig = ax.get_figure()
    renderer = fig.canvas.get_renderer()

    # Calculate available width based on alignment
    margin = 0.05  # 5% margin on edges
    if align == "left":
        available_width = 1.0 - x_rel - margin
    elif align == "right":
        available_width = x_rel - margin
    else:  # center
        available_width = min(x_rel, 1.0 - x_rel) * 2 - margin * 2

    # Measure text width and shrink if needed
    max_iterations = 10
    for _ in range(max_iterations):
        temp_text = ax.text(
            x_rel,
            y_axes,
            text,
            transform=ax.transAxes,
            fontsize=fontsize,
            fontfamily=font_family,
            fontweight=font_weight,
            alpha=0,  # invisible
        )
        bbox = temp_text.get_window_extent(renderer=renderer)
        temp_text.remove()

        # Convert pixel width to axes coordinates
        axes_bbox = ax.get_window_extent(renderer=renderer)
        text_width_axes = bbox.width / axes_bbox.width

        if text_width_axes <= available_width or fontsize <= 4:
            break

        # Shrink by 10% and retry
        fontsize *= 0.9

    # Render text
    ax.text(
        x_rel,
        y_axes,
        text,
        transform=ax.transAxes,
        fontsize=fontsize,
        fontfamily=font_family,
        fontweight=font_weight,
        color=color,
        alpha=alpha,
        ha=align,
        va="center",
        zorder=zorder,
    )


def _render_panel_stats_element(
    ax, element, panel_y0, panel_y1, panel_height_pts, zorder
):
    """Render stats within the info panel."""
    items = element.get("items", [])
    if not items:
        return

    # Position and layout
    x_rel = element.get("x", 0.5)
    y_rel = element.get("y", 0.5)
    align = element.get("align", "center")
    layout = element.get("layout", "horizontal")
    spacing = element.get("spacing", 0.05)

    # Convert to axes coordinates
    panel_height = panel_y1 - panel_y0
    y_axes = panel_y0 + (y_rel * panel_height)

    # Font properties
    font_family = element.get("font", "Inter")
    transform_type = element.get("transform", "none")

    # Value properties
    value_size_frac = element.get("value_size", 0.25)
    value_fontsize = value_size_frac * panel_height_pts
    value_weight = element.get("value_weight", "bold")
    value_color = element.get("value_color", "#000000")
    value_alpha = element.get("value_alpha", 1.0)

    # Label properties
    label_size_frac = element.get("label_size", 0.12)
    label_fontsize = label_size_frac * panel_height_pts
    label_weight = element.get("label_weight", "normal")
    label_color = element.get("label_color", "#666666")
    label_alpha = element.get("label_alpha", 1.0)

    if layout == "horizontal":
        # Measure all stats to calculate total width
        stat_data = []
        for item in items:
            value = str(item.get("value", ""))
            label = str(item.get("label", ""))

            if transform_type == "uppercase":
                value = value.upper()
                label = label.upper()

            # Create temp text to measure
            temp_value = ax.text(
                0,
                0,
                value,
                fontsize=value_fontsize,
                fontfamily=font_family,
                fontweight=value_weight,
                transform=ax.transAxes,
                alpha=0,
            )
            temp_label = ax.text(
                0,
                0,
                label,
                fontsize=label_fontsize,
                fontfamily=font_family,
                fontweight=label_weight,
                transform=ax.transAxes,
                alpha=0,
            )

            ax.figure.canvas.draw()

            value_bbox = temp_value.get_window_extent()
            label_bbox = temp_label.get_window_extent()

            # Convert to axes coordinates
            fig_width_px = ax.figure.get_size_inches()[0] * ax.figure.dpi
            value_width = value_bbox.width / fig_width_px
            label_width = label_bbox.width / fig_width_px

            temp_value.remove()
            temp_label.remove()

            stat_width = max(value_width, label_width)
            stat_data.append({"value": value, "label": label, "width": stat_width})

        # Calculate positions
        total_width = sum(s["width"] for s in stat_data) + spacing * max(
            0, len(stat_data) - 1
        )

        if align == "right":
            current_x = x_rel - total_width
        elif align == "center":
            current_x = x_rel - total_width / 2
        else:  # left
            current_x = x_rel

        # Render each stat
        label_offset = 0.20  # fraction of panel height between value and label
        label_y_axes = y_axes - (label_offset * panel_height)

        for stat in stat_data:
            stat_center_x = current_x + stat["width"] / 2

            # Render value
            ax.text(
                stat_center_x,
                y_axes,
                stat["value"],
                transform=ax.transAxes,
                fontsize=value_fontsize,
                fontfamily=font_family,
                fontweight=value_weight,
                color=value_color,
                alpha=value_alpha,
                ha="center",
                va="center",
                zorder=zorder,
            )

            # Render label below
            if stat["label"]:
                ax.text(
                    stat_center_x,
                    label_y_axes,
                    stat["label"],
                    transform=ax.transAxes,
                    fontsize=label_fontsize,
                    fontfamily=font_family,
                    fontweight=label_weight,
                    color=label_color,
                    alpha=label_alpha,
                    ha="center",
                    va="center",
                    zorder=zorder,
                )

            current_x += stat["width"] + spacing


def _render_map_info_text(fig, ax, info_cfg):
    """Render lightweight map info text with panel-style scalable typography."""
    if not info_cfg or not info_cfg.get("show", False):
        return

    content = str(info_cfg.get("text", "")).strip()
    if not content:
        return

    transform_type = info_cfg.get("transform", "none")
    if transform_type == "uppercase":
        content = content.upper()
    elif transform_type == "lowercase":
        content = content.lower()

    pos_map = {
        "top-left": (0.01, 0.99),
        "top-right": (0.99, 0.99),
        "bottom-left": (0.01, 0.01),
        "bottom-right": (0.99, 0.01),
    }
    position = info_cfg.get("position", "bottom-right")
    x_default, y_default = pos_map.get(position, (0.99, 0.01))
    x = float(info_cfg.get("x", x_default))
    y = float(info_cfg.get("y", y_default))

    default_ha = "right" if "right" in position else "left"
    default_va = "top" if "top" in position else "bottom"
    ha = info_cfg.get("h_align", default_ha)
    va = info_cfg.get("v_align", default_va)

    font_family = info_cfg.get("font", "Inter")
    font_weight = info_cfg.get("font_weight", "normal")
    color = info_cfg.get("color", "#000000")
    alpha = float(info_cfg.get("alpha", 1.0))
    tracking = float(info_cfg.get("tracking", 0.0))

    map_height_fraction = float(ax.get_position().height)
    map_height_pts = fig.get_size_inches()[1] * map_height_fraction * 72.0

    size_frac = float(info_cfg.get("size", 0.01))
    fontsize = max(1.0, float(size_frac) * map_height_pts)

    if tracking > 0:
        spaced_text = content[0] if content else ""
        for char in content[1:]:
            spaced_text += "\u200a" * max(1, int(tracking * 10)) + char
        content = spaced_text

    ax.text(
        x,
        y,
        content,
        transform=ax.transAxes,
        ha=ha,
        va=va,
        fontfamily=font_family,
        fontweight=font_weight,
        fontsize=fontsize,
        color=color,
        alpha=alpha,
        zorder=info_cfg.get("zorder", 2000),
        clip_on=False,
    )


def _local_name(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _dedupe_route_coords(route_coords):
    if not route_coords:
        return []
    deduped = [route_coords[0]]
    for lon, lat in route_coords[1:]:
        prev_lon, prev_lat = deduped[-1]
        if not (math.isclose(lon, prev_lon) and math.isclose(lat, prev_lat)):
            deduped.append((lon, lat))
    return deduped


def _route_cumulative_distance_m(route_coords):
    if len(route_coords) < 2:
        return np.array([0.0], dtype=np.float64)

    points = np.asarray(route_coords, dtype=np.float64)
    lons = points[:, 0]
    lats = points[:, 1]

    r = 6371008.8
    phi = np.radians(lats)
    dphi = np.radians(np.diff(lats))
    dlambda = np.radians(np.diff(lons))
    a = (
        np.sin(dphi / 2.0) ** 2
        + np.cos(phi[:-1]) * np.cos(phi[1:]) * np.sin(dlambda / 2.0) ** 2
    )
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(np.maximum(0.0, 1.0 - a)))
    seg_m = r * c
    return np.concatenate([[0.0], np.cumsum(seg_m)])


def _route_distance_km(route_coords):
    cum_m = _route_cumulative_distance_m(route_coords)
    if cum_m.size == 0:
        return 0.0
    return float(cum_m[-1]) / 1000.0


def _elevation_gain_m(elevation_data):
    elev = np.asarray(elevation_data, dtype=np.float64)
    if elev.size < 2:
        return 0.0
    diff = np.diff(elev)
    return float(np.sum(diff[diff > 0]))


def _extract_supplied_stats(cfg):
    panel = cfg.get("map", {}).get("info_panel", {})
    elements = panel.get("elements", []) if isinstance(panel, dict) else []

    supplied_distance = None
    supplied_elev_gain = None

    for element in elements:
        if element.get("type") != "stats" and element.get("id") != "stats":
            continue
        for item in element.get("items", []):
            label = str(item.get("label", "")).strip().lower()
            value = str(item.get("value", "")).strip()
            if label in {"distance", "dist"} and value:
                supplied_distance = value
            if label in {"elev gain", "elevation gain", "gain"} and value:
                supplied_elev_gain = value

    return supplied_distance, supplied_elev_gain


def _select_route_units(units_mode, country_code=None):
    mode = str(units_mode or "auto").strip().lower()
    if mode in {"metric", "imperial"}:
        return mode, "explicit"

    code = (country_code or "").strip().upper()
    if code:
        if code in IMPERIAL_COUNTRY_CODES:
            return "imperial", f"auto-country:{code}"
        return "metric", f"auto-country:{code}"

    return "metric", "auto-fallback"


def _format_route_distance(derived_distance_km, units):
    if units == "imperial":
        miles = derived_distance_km * 0.6213711922
        return f"{int(round(miles))} mi"
    return f"{int(round(derived_distance_km))} km"


def _format_route_elev_gain(derived_gain_m, units):
    if units == "imperial":
        feet = derived_gain_m * 3.280839895
        rounded_ft = int(round(feet / 50.0) * 50)
        return f"{rounded_ft} ft"
    rounded_m = int(round(derived_gain_m / 10.0) * 10)
    return f"{rounded_m} m"


def _ensure_route_stats_in_panel(cfg, distance_value, elev_gain_value):
    panel = cfg.get("map", {}).get("info_panel", {})
    if not isinstance(panel, dict):
        return

    elements = panel.get("elements")
    if not isinstance(elements, list):
        return

    stats_element = None
    for element in elements:
        if element.get("type") == "stats" or element.get("id") == "stats":
            stats_element = element
            break

    if stats_element is None:
        stats_element = {"id": "stats", "type": "stats", "items": []}
        elements.append(stats_element)

    items = stats_element.get("items")
    if not isinstance(items, list):
        items = []
        stats_element["items"] = items

    def upsert(label_candidates, canonical_label, value):
        if not value:
            return
        found = None
        for item in items:
            label = str(item.get("label", "")).strip().lower()
            if label in label_candidates:
                found = item
                break
        if found is not None:
            if not str(found.get("value", "")).strip():
                found["value"] = value
            return
        items.append({"value": value, "label": canonical_label})

    upsert({"distance", "dist"}, "DISTANCE", distance_value)
    upsert({"elev gain", "elevation gain", "gain"}, "ELEV GAIN", elev_gain_value)


def _resample_route_coords(
    route_coords,
    mode="fixed_count",
    num_points=160,
    interval_m=300.0,
    min_points=40,
    max_points=500,
):
    if len(route_coords) < 2:
        return route_coords

    points = np.asarray(route_coords, dtype=np.float64)
    cum = _route_cumulative_distance_m(route_coords)
    total = float(cum[-1])
    if total <= 0:
        return route_coords

    sampling_mode = str(mode or "fixed_count").lower()
    if sampling_mode == "distance_interval":
        interval = max(float(interval_m), 1.0)
        target_points = int(total / interval) + 1
        target_points = max(int(min_points), min(int(max_points), target_points))
    else:
        target_points = int(num_points)
        target_points = max(int(min_points), min(int(max_points), target_points))

    if target_points <= 2:
        return [tuple(points[0]), tuple(points[-1])]

    if len(route_coords) == target_points:
        return route_coords

    sample_d = np.linspace(0.0, total, target_points)
    sample_x = np.interp(sample_d, cum, points[:, 0])
    sample_y = np.interp(sample_d, cum, points[:, 1])
    return list(zip(sample_x, sample_y))


def _load_gpx_route_coords(gpx_path: Path, sampling_cfg=None):
    tree = ET.parse(gpx_path)
    root = tree.getroot()

    route_coords = []
    gpx_elevation = []

    def _parse_ele(pt):
        for child in pt:
            if _local_name(child.tag) == "ele":
                try:
                    return float(child.text)
                except (TypeError, ValueError):
                    pass
        return None

    # Prefer ordered track points (trk -> trkseg -> trkpt)
    for trk in [e for e in root.iter() if _local_name(e.tag) == "trk"]:
        for trkseg in [e for e in trk if _local_name(e.tag) == "trkseg"]:
            for trkpt in [e for e in trkseg if _local_name(e.tag) == "trkpt"]:
                lat = trkpt.attrib.get("lat")
                lon = trkpt.attrib.get("lon")
                if lat is None or lon is None:
                    continue
                try:
                    route_coords.append((float(lon), float(lat)))
                    gpx_elevation.append(_parse_ele(trkpt))
                except ValueError:
                    continue

    # Fallback to route points (rte -> rtept)
    if len(route_coords) < 2:
        route_coords = []
        gpx_elevation = []
        for rte in [e for e in root.iter() if _local_name(e.tag) == "rte"]:
            for rtept in [e for e in rte if _local_name(e.tag) == "rtept"]:
                lat = rtept.attrib.get("lat")
                lon = rtept.attrib.get("lon")
                if lat is None or lon is None:
                    continue
                try:
                    route_coords.append((float(lon), float(lat)))
                    gpx_elevation.append(_parse_ele(rtept))
                except ValueError:
                    continue

    route_coords = _dedupe_route_coords(route_coords)
    if len(route_coords) < 2:
        raise ValueError(f"No valid route points found in GPX file: {gpx_path}")

    # Check if we have usable elevation data from GPX
    valid_ele = [e for e in gpx_elevation if e is not None]
    if len(valid_ele) >= 2:
        ele_array = np.array(
            [e if e is not None else np.nan for e in gpx_elevation], dtype=np.float64
        )
        # Interpolate any missing values
        idx = np.arange(len(ele_array))
        finite = np.isfinite(ele_array)
        if not finite.all() and finite.any():
            ele_array = np.interp(idx, idx[finite], ele_array[finite])
        parsed_elevation = ele_array
    else:
        parsed_elevation = None

    sampling_cfg = sampling_cfg or {}
    resampled_coords = _resample_route_coords(
        route_coords,
        mode=sampling_cfg.get("mode", "fixed_count"),
        num_points=int(sampling_cfg.get("num_points", 160)),
        interval_m=float(sampling_cfg.get("interval_m", 300.0)),
        min_points=int(sampling_cfg.get("min_points", 40)),
        max_points=int(sampling_cfg.get("max_points", 500)),
    )

    # Resample elevation to match resampled coords
    if parsed_elevation is not None:
        orig_idx = np.linspace(0, 1, len(parsed_elevation))
        new_idx = np.linspace(0, 1, len(resampled_coords))
        parsed_elevation = np.interp(new_idx, orig_idx, parsed_elevation)

    return resampled_coords, parsed_elevation


def _sample_dem_elevation(route_coords, dem_path):
    if not dem_path:
        return None

    with rasterio.open(dem_path) as dem_ds:
        if len(route_coords) < 2:
            return None

        coords = np.asarray(route_coords, dtype=np.float64)
        lons = coords[:, 0]
        lats = coords[:, 1]

        if dem_ds.crs and str(dem_ds.crs).upper() != "EPSG:4326":
            from rasterio.warp import transform as rio_transform

            xs, ys = rio_transform(
                "EPSG:4326", dem_ds.crs, lons.tolist(), lats.tolist()
            )
        else:
            xs, ys = lons.tolist(), lats.tolist()

        samples = list(dem_ds.sample(list(zip(xs, ys))))
        elevation = np.array(
            [s[0] if len(s) else np.nan for s in samples], dtype=np.float64
        )

        nodata = dem_ds.nodata
        if nodata is not None:
            elevation = np.where(np.isclose(elevation, nodata), np.nan, elevation)

        finite = np.isfinite(elevation)
        if not finite.any():
            return None

        if not finite.all():
            idx = np.arange(elevation.size)
            valid_idx = idx[finite]
            valid_vals = elevation[finite]
            if valid_idx.size >= 2:
                elevation = np.interp(idx, valid_idx, valid_vals)
            else:
                elevation = np.full_like(elevation, valid_vals[0])

    return elevation


def _trim_route_for_markers(ax, route_coords, trim_start_px, trim_end_px):
    if len(route_coords) < 2:
        return route_coords

    points = np.asarray(route_coords, dtype=np.float64)
    points_px = ax.transData.transform(points)

    seg = points_px[1:] - points_px[:-1]
    seg_len = np.linalg.norm(seg, axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg_len)])
    total = float(cum[-1])
    if total <= 0:
        return route_coords

    d0 = max(0.0, float(trim_start_px))
    d1 = max(d0, total - max(0.0, float(trim_end_px)))
    if d1 - d0 <= 1e-6:
        return route_coords

    def interpolate_at(distance):
        idx = int(np.searchsorted(cum, distance, side="right") - 1)
        idx = max(0, min(idx, len(seg_len) - 1))
        length = seg_len[idx]
        if length <= 1e-9:
            return points_px[idx]
        t = (distance - cum[idx]) / length
        return points_px[idx] + t * seg[idx]

    trimmed_px = [interpolate_at(d0)]
    for i in range(1, len(points_px) - 1):
        if d0 < cum[i] < d1:
            trimmed_px.append(points_px[i])
    trimmed_px.append(interpolate_at(d1))

    trimmed_px = np.asarray(trimmed_px, dtype=np.float64)
    trimmed_data = ax.transData.inverted().transform(trimmed_px)
    return [tuple(pt) for pt in trimmed_data]


def _render_route_on_map(ax, route_coords, route_cfg, dpi):
    """
    Render a route on the map axes.

    Parameters
    ----------
    ax : matplotlib axes
        The map axes
    route_coords : list of (lon, lat) tuples
        The route coordinates
    route_cfg : dict
        Route configuration (color, linewidth, alpha)
    """
    if not route_coords or not route_cfg.get("enabled", False):
        return

    route_color = route_cfg.get("color", "#444444")
    route_width = float(route_cfg.get("linewidth", 2.5))
    route_alpha = float(route_cfg.get("alpha", 0.8))

    start_cfg = route_cfg.get("start_marker", {})
    end_cfg = route_cfg.get("end_marker", {})
    start_size_pts = float(start_cfg.get("size", 12))
    end_size_pts = float(end_cfg.get("size", 12))
    start_radius_px = (start_size_pts * dpi / 72.0) * 0.52
    end_radius_px = (end_size_pts * dpi / 72.0) * 0.52

    trimmed_coords = _trim_route_for_markers(
        ax,
        route_coords,
        trim_start_px=start_radius_px,
        trim_end_px=end_radius_px,
    )
    if len(trimmed_coords) < 2:
        trimmed_coords = route_coords

    lons, lats = zip(*trimmed_coords)

    outline_cfg = route_cfg.get("outline", {})
    outline_enabled = bool(outline_cfg.get("enabled", False))
    outline_color = outline_cfg.get("color", _mix_colors(route_color, "#000000", 0.35))
    outline_width = float(outline_cfg.get("linewidth", max(0.6, route_width * 0.35)))

    if outline_enabled and outline_width > 0:
        ax.plot(
            lons,
            lats,
            color=outline_color,
            linewidth=route_width + (2.0 * outline_width),
            alpha=route_alpha,
            zorder=999,
            solid_capstyle="round",
            solid_joinstyle="round",
        )

    ax.plot(
        lons,
        lats,
        color=route_color,
        linewidth=route_width,
        alpha=route_alpha,
        zorder=1000,
        solid_capstyle="round",
        solid_joinstyle="round",
    )


def _mix_colors(color_a, color_b, ratio):
    a = np.array(to_rgb(color_a), dtype=np.float32)
    b = np.array(to_rgb(color_b), dtype=np.float32)
    t = float(max(0.0, min(1.0, ratio)))
    return tuple((1.0 - t) * a + t * b)


def _resolve_marker_colors(route_cfg):
    route_color = route_cfg.get("color", "#444444")
    start_cfg = route_cfg.get("start_marker", {})
    end_cfg = route_cfg.get("end_marker", {})

    start_color = start_cfg.get("color")
    if not start_color or str(start_color).lower() == "auto":
        start_color = _mix_colors(route_color, "#000000", 0.15)

    end_color = end_cfg.get("color")
    if not end_color or str(end_color).lower() == "auto":
        end_color = _mix_colors(route_color, "#000000", 0.30)

    return route_color, start_color, end_color


def _offset_point_in_pixels(ax, point, dx_px, dy_px):
    display_xy = ax.transData.transform(point)
    shifted_display = (display_xy[0] + dx_px, display_xy[1] + dy_px)
    shifted_data = ax.transData.inverted().transform(shifted_display)
    return (float(shifted_data[0]), float(shifted_data[1]))


def _resolve_marker_positions(ax, route_coords, start_size_pts, end_size_pts, dpi):
    start = np.array(route_coords[0], dtype=np.float64)
    end = np.array(route_coords[-1], dtype=np.float64)

    start_px = ax.transData.transform(start)
    end_px = ax.transData.transform(end)
    delta = end_px - start_px
    distance_px = float(np.linalg.norm(delta))

    start_radius_px = (start_size_pts * dpi / 72.0) * 0.6
    end_radius_px = (end_size_pts * dpi / 72.0) * 0.6
    min_separation_px = start_radius_px + end_radius_px + 10.0

    if distance_px >= min_separation_px:
        return tuple(start), tuple(end)

    if distance_px > 1e-6:
        direction = delta / distance_px
    elif len(route_coords) > 1:
        alt = ax.transData.transform(route_coords[1]) - start_px
        alt_norm = float(np.linalg.norm(alt))
        direction = alt / alt_norm if alt_norm > 1e-6 else np.array([1.0, 0.0])
    else:
        direction = np.array([1.0, 0.0])

    normal = np.array([-direction[1], direction[0]])
    extra_offset_px = (min_separation_px - distance_px) / 2.0
    offset_px = max(extra_offset_px, 6.0)

    start_shifted = _offset_point_in_pixels(
        ax, tuple(start), -normal[0] * offset_px, -normal[1] * offset_px
    )
    end_shifted = _offset_point_in_pixels(
        ax, tuple(end), normal[0] * offset_px, normal[1] * offset_px
    )
    return start_shifted, end_shifted


def _draw_start_marker(
    ax,
    lon,
    lat,
    color,
    size_pts,
    dpi,
    zorder,
    marker_cfg=None,
    outline_color=None,
):
    marker_cfg = marker_cfg or {}
    # DrawingArea uses points, not pixels
    canvas = size_pts * 2.0
    center = canvas / 2.0

    fill_color = marker_cfg.get("fill_color", "white")
    core_color = marker_cfg.get("core_color", color)
    edge_color = marker_cfg.get("ring_color", outline_color or color)
    ring_width_scale = float(marker_cfg.get("ring_width_scale", 0.12))
    core_radius_scale = float(marker_cfg.get("core_radius_scale", 0.24))
    core_edge_scale = float(marker_cfg.get("core_edge_width_scale", 0.06))

    da = DrawingArea(canvas, canvas, clip=False)
    da.add_artist(
        mpatches.Circle(
            (center, center),
            radius=size_pts * 0.48,
            facecolor=fill_color,
            edgecolor=edge_color,
            linewidth=max(0.8, size_pts * ring_width_scale),
        )
    )
    da.add_artist(
        mpatches.Circle(
            (center, center),
            radius=size_pts * max(0.05, core_radius_scale),
            facecolor=core_color,
            edgecolor=fill_color,
            linewidth=max(0.6, size_pts * core_edge_scale),
        )
    )

    ax.add_artist(
        AnnotationBbox(
            da,
            (lon, lat),
            xycoords="data",
            frameon=False,
            pad=0,
            box_alignment=(0.5, 0.5),
            zorder=zorder,
        )
    )


def _draw_concentric_circle_marker(
    ax,
    lon,
    lat,
    color,
    size_pts,
    dpi,
    zorder,
    marker_cfg=None,
    outline_color=None,
):
    _draw_start_marker(
        ax,
        lon,
        lat,
        color,
        size_pts,
        dpi,
        zorder,
        marker_cfg=marker_cfg,
        outline_color=outline_color,
    )


def _draw_end_marker(ax, lon, lat, color, size_pts, dpi, zorder):
    # DrawingArea uses points, not pixels
    canvas = size_pts * 2.0
    center = canvas / 2.0
    ring_radius = size_pts * 0.48
    ring_lw = max(1.0, size_pts * 0.12)

    # Centered 4x4 checker field sized so the square's corner points
    # exactly touch the inner edge of the circular ring.
    inner_ring_radius = ring_radius - (ring_lw / 2.0)
    checker_span = inner_ring_radius * math.sqrt(2.0)
    cell = checker_span / 4.0

    da = DrawingArea(canvas, canvas, clip=False)

    # White base disk
    da.add_artist(
        mpatches.Circle(
            (center, center),
            radius=ring_radius,
            facecolor="white",
            edgecolor="none",
        )
    )

    # 4x4 checker motif (centered; ring trims edges visually)
    x0 = center - checker_span / 2.0
    y0 = center - checker_span / 2.0
    for row in range(4):
        for col in range(4):
            square_color = color if (row + col) % 2 == 0 else "white"
            square = mpatches.Rectangle(
                (x0 + col * cell, y0 + row * cell),
                cell,
                cell,
                facecolor=square_color,
                edgecolor="none",
            )
            da.add_artist(square)

    # Ring drawn on top of checker field
    da.add_artist(
        mpatches.Circle(
            (center, center),
            radius=ring_radius,
            facecolor="none",
            edgecolor=color,
            linewidth=ring_lw,
        )
    )

    ax.add_artist(
        AnnotationBbox(
            da,
            (lon, lat),
            xycoords="data",
            frameon=False,
            pad=0,
            box_alignment=(0.5, 0.5),
            zorder=zorder,
        )
    )


def _render_route_markers(ax, route_coords, route_cfg, dpi):
    """
    Render start and end markers for a route.

    Parameters
    ----------
    ax : matplotlib axes
        The map axes
    route_coords : list of (lon, lat) tuples
        The route coordinates
    route_cfg : dict
        Route configuration with marker settings
    dpi : int
        DPI for size calculations
    """
    if not route_coords or not route_cfg.get("enabled", False):
        return

    start_cfg = route_cfg.get("start_marker", {})
    end_cfg = route_cfg.get("end_marker", {})

    route_color, start_color, end_color = _resolve_marker_colors(route_cfg)
    route_outline_cfg = route_cfg.get("outline", {})
    marker_outline_color = route_outline_cfg.get(
        "color", _mix_colors(route_color, "#000000", 0.35)
    )

    start_size_pts = float(start_cfg.get("size", 12))
    end_size_pts = float(end_cfg.get("size", 12))

    (start_lon, start_lat), (end_lon, end_lat) = _resolve_marker_positions(
        ax,
        route_coords,
        start_size_pts,
        end_size_pts,
        dpi,
    )

    if start_cfg.get("style", "concentric_circles") == "concentric_circles":
        _draw_concentric_circle_marker(
            ax,
            start_lon,
            start_lat,
            start_color,
            start_size_pts,
            dpi,
            zorder=1006,
            marker_cfg=start_cfg,
            outline_color=marker_outline_color,
        )

    end_style = end_cfg.get("style", "concentric_circles")
    if end_style == "checkered_flag":
        _draw_end_marker(
            ax,
            end_lon,
            end_lat,
            end_color,
            end_size_pts,
            dpi,
            zorder=1007,
        )
    elif end_style == "concentric_circles":
        _draw_concentric_circle_marker(
            ax,
            end_lon,
            end_lat,
            end_color,
            end_size_pts,
            dpi,
            zorder=1007,
            marker_cfg=end_cfg,
            outline_color=marker_outline_color,
        )


def _render_elevation_profile(ax, route_coords, elevation_data, profile_cfg, mask_gdf):
    """
    Render elevation profile as an overlay at the bottom of the map axes.

    Parameters
    ----------
    ax : matplotlib axes
        The map axes
    route_coords : list of (lon, lat) tuples
        The route coordinates
    elevation_data : numpy array
        Elevation values
    profile_cfg : dict
        Profile configuration (height, color, alpha)
    mask_gdf : GeoDataFrame
        Map bounds for positioning
    """
    if not profile_cfg.get("enabled", False) or len(route_coords) == 0:
        return

    import numpy as np

    if elevation_data is None or len(elevation_data) == 0:
        return

    # Draw in axes coordinates, not map data coordinates.
    # The footer/profile is a layout element and must span the visible map width
    # exactly, regardless of aspect correction or datalim adjustments.
    profile_height_fraction = float(profile_cfg.get("height", 0.04))
    profile_height_fraction = max(0.0, min(profile_height_fraction, 1.0))

    elev = np.asarray(elevation_data, dtype=np.float64)
    finite = np.isfinite(elev)
    if not finite.any():
        return

    if not finite.all():
        idx = np.arange(elev.size)
        valid_idx = idx[finite]
        valid_vals = elev[finite]
        if valid_idx.size >= 2:
            elev = np.interp(idx, valid_idx, valid_vals)
        else:
            elev = np.full_like(elev, valid_vals[0])

    elev_min = float(np.min(elev))
    elev_max = float(np.max(elev))
    if elev_max > elev_min:
        elev_normalized = (elev - elev_min) / (elev_max - elev_min)
    else:
        elev_normalized = np.zeros_like(elev)

    x_coords = np.linspace(0.0, 1.0, len(elev_normalized))
    y_coords = elev_normalized * profile_height_fraction

    x_fill = np.concatenate([x_coords, [1.0, 0.0]])
    y_fill = np.concatenate([y_coords, [0.0, 0.0]])

    # Check for outline configuration
    outline_cfg = profile_cfg.get("outline", {})
    outline_enabled = outline_cfg.get("enabled", False)
    outline_color = outline_cfg.get("color", "#000000")
    outline_width = float(outline_cfg.get("linewidth", 1.0))
    outline_alpha = float(outline_cfg.get("alpha", 1.0))

    # Convert outline color to RGBA with custom alpha
    if outline_enabled:
        from matplotlib.colors import to_rgba

        outline_rgba = to_rgba(outline_color)
        outline_rgba = (
            outline_rgba[0],
            outline_rgba[1],
            outline_rgba[2],
            outline_alpha,
        )
    else:
        outline_rgba = "none"

    ax.fill(
        x_fill,
        y_fill,
        transform=ax.transAxes,
        facecolor=profile_cfg.get("color", "#2a2a2a"),
        edgecolor=outline_rgba,
        linewidth=outline_width if outline_enabled else 0,
        alpha=profile_cfg.get("alpha", 0.9),
        zorder=1100,  # Above route and features
        antialiased=False,
    )


def draw_map_from_config(
    config_path: Path,
    geojson_path: Path,
    output_path: Path,
    width: float = 12,
    height: float = 12,
    dpi: int = 300,
    fmt: str = "png",
    fit_content: bool = False,
    route_units: str = "auto",
    route_country_code: str = "",
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

    # Check for frame and panel configuration
    frame_cfg = mcfg.get("frame", {})
    panel_cfg = mcfg.get("info_panel", {})
    panel_enabled = panel_cfg and panel_cfg.get("enabled", False)

    # Frame is only enabled when panel is enabled
    frame_enabled = frame_cfg.get("enabled", False) and panel_enabled
    frame_color = frame_cfg.get("color", "#2a2a2a")
    frame_padding_fraction = frame_cfg.get(
        "padding", 0.04
    )  # fraction of smaller dimension

    # Calculate uniform frame padding in inches (based on smaller dimension)
    min_dimension = min(width, height)
    frame_padding_inches = frame_padding_fraction * min_dimension

    # Convert to fractions of each dimension for uniform physical borders
    frame_padding_horizontal = frame_padding_inches / width
    frame_padding_vertical = frame_padding_inches / height

    panel_height = panel_cfg.get("height", 0.12) if panel_enabled else 0.0

    # Create figure
    fig = plt.figure(figsize=(width, height), dpi=dpi)

    # Set frame background color if enabled
    if frame_enabled:
        fig.patch.set_facecolor(frame_color)
    else:
        fig.patch.set_facecolor("black")

    # Calculate axes positions
    # Uniform borders on all sides, panel sits directly above bottom border
    if panel_enabled and frame_enabled:
        # Map axes: uniform borders, panel directly below map with no gap
        map_left = frame_padding_horizontal
        map_bottom = (
            frame_padding_vertical + panel_height
        )  # bottom border + panel (no gap)
        map_width = 1.0 - (2 * frame_padding_horizontal)
        map_height = (
            1.0 - frame_padding_vertical - (frame_padding_vertical + panel_height)
        )  # top border and (bottom border + panel)

        # Panel axes: sits directly above bottom border
        panel_left = frame_padding_horizontal
        panel_bottom = frame_padding_vertical
        panel_width = 1.0 - (2 * frame_padding_horizontal)
        panel_height_axes = panel_height
    elif frame_enabled:
        # Just map with frame padding
        map_left = frame_padding_horizontal
        map_bottom = frame_padding_vertical
        map_width = 1.0 - (2 * frame_padding_horizontal)
        map_height = 1.0 - (2 * frame_padding_vertical)
    else:
        # Full figure
        map_left = 0
        map_bottom = 0
        map_width = 1.0
        map_height = 1.0

    # Create map axes
    ax = fig.add_axes([map_left, map_bottom, map_width, map_height])
    ax.set_facecolor("black")

    # Store axes dimensions for later use in cropping calculations
    map_axes_aspect = (width * map_width) / (height * map_height)

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
    if not frame_enabled:
        fig.patch.set_facecolor(face_fc)
    ax.set_facecolor(face_fc)
    ax.set_axis_off()
    ax.add_patch(
        mpatches.Rectangle(
            (0, 0),
            1,
            1,
            transform=ax.transAxes,
            facecolor=face_fc,
            edgecolor="none",
            zorder=-1000,
        )
    )

    # Clip patch in data coordinates — applied to all raster layers so nothing bleeds beyond the boundary
    raster_clip_patch = _boundary_clip_patch(mask_gdf, ax)

    # --- Render satellite image underlay if configured (drawn immediately after background) ---
    satellite_cfg = cfg.get("map", {}).get("satellite")
    if satellite_cfg and satellite_cfg.get("visible", True):
        try:
            with rasterio.open(satellite_cfg["path"]) as src:
                # Use the image data directly without reprojection
                img_rgb = np.moveaxis(src.read([1, 2, 3]), 0, -1)
                img_rgb = np.clip(img_rgb, 0, 255).astype(np.uint8)

                _im = ax.imshow(
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
                if raster_clip_patch is not None:
                    _im.set_clip_path(raster_clip_patch)
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
                dem_resampled = np.full((height_px, width_px), np.nan, dtype=np.float32)

                # reproject/resample DEM into target grid
                reproject(
                    source=rasterio.band(dem_ds, 1),
                    destination=dem_resampled,
                    src_transform=dem_ds.transform,
                    src_crs=dem_ds.crs,
                    dst_transform=target_transform,
                    dst_crs=dem_ds.crs,
                    src_nodata=dem_ds.nodata,
                    dst_nodata=np.nan,
                    resampling=Resampling.bilinear,
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

                    _im = ax.imshow(
                        terrain_img,
                        extent=[left, right, bottom, top],
                        zorder=terrain_cfg.get("zorder", hs_cfg.get("zorder", 0)),
                        alpha=terrain_cfg.get("alpha", 1.0),
                        interpolation=terrain_cfg.get("interpolation", "bicubic"),
                        aspect="auto",
                    )
                    if raster_clip_patch is not None:
                        _im.set_clip_path(raster_clip_patch)
                else:
                    hillshade_alpha = hs_cfg.get("alpha", 0.5)
                    if hillshade_rgb is not None:
                        rgba = np.empty(
                            hillshade_rgb.shape[:2] + (4,), dtype=np.float32
                        )
                        rgba[..., :3] = hillshade_rgb
                        rgba[..., 3] = float(hillshade_alpha)
                        _im = ax.imshow(
                            rgba,
                            extent=[left, right, bottom, top],
                            zorder=hs_cfg.get("zorder", 0),
                            interpolation=hs_cfg.get("interpolation", "bicubic"),
                            aspect="auto",
                        )
                        if raster_clip_patch is not None:
                            _im.set_clip_path(raster_clip_patch)
                    else:
                        _im = ax.imshow(
                            shade,
                            cmap=hs_cfg.get("cmap", "gray"),
                            alpha=hillshade_alpha,
                            extent=[left, right, bottom, top],
                            zorder=hs_cfg.get("zorder", 0),
                            interpolation=hs_cfg.get("interpolation", "bicubic"),
                            aspect="auto",
                        )
                        if raster_clip_patch is not None:
                            _im.set_clip_path(raster_clip_patch)
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
    aspect = 1 / math.cos(math.radians(avg_lat))
    # adjust aspect so degrees are equal distances
    ax.set_aspect(aspect)
    if fit_content:
        ax.set_xlim(minx, maxx)
        ax.set_ylim(miny, maxy)
    else:
        # crop view to fill map axes dimensions (accounts for panel if present)
        target = map_axes_aspect * aspect
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

    # Inset axes limits to hide boundary artifacts and satellite attribution text.
    _xl, _xr = ax.get_xlim()
    _yb, _yt = ax.get_ylim()
    _xi = (_xr - _xl) * 0.02
    _yi = (_yt - _yb) * 0.02
    ax.set_xlim(_xl + _xi, _xr - _xi)
    ax.set_ylim(_yb + _yi, _yt - _yi)

    # Render elevation profile and route if configured
    elevation_cfg = mcfg.get("elevation_profile", {})
    route_gpx_path = mcfg.get("route_gpx")
    if elevation_cfg.get("enabled", False) and route_gpx_path:
        route_coords = None
        route_cfg = elevation_cfg.get("route", {})
        sampling_cfg = route_cfg.get("sampling", {})

        gpx_elevation = None
        try:
            route_coords, gpx_elevation = _load_gpx_route_coords(
                Path(route_gpx_path),
                sampling_cfg=sampling_cfg,
            )
        except (FileNotFoundError, ET.ParseError, OSError, ValueError) as e:
            print(f"Warning: Could not load GPX route '{route_gpx_path}': {e}")

        if route_coords:
            elevation_data = None
            if dem_path:
                try:
                    elevation_data = _sample_dem_elevation(route_coords, dem_path)
                except (
                    FileNotFoundError,
                    rasterio.errors.RasterioIOError,
                    ValueError,
                ) as e:
                    print(
                        f"Warning: Could not sample DEM elevations for GPX route: {e}"
                    )

            if elevation_data is None:
                elevation_data = gpx_elevation

            derived_distance_km = _route_distance_km(route_coords)
            derived_gain_m = _elevation_gain_m(elevation_data)
            supplied_distance, supplied_elev_gain = _extract_supplied_stats(cfg)
            resolved_units, units_reason = _select_route_units(
                route_units,
                country_code=route_country_code,
            )
            derived_distance_display = _format_route_distance(
                derived_distance_km,
                resolved_units,
            )
            derived_gain_display = _format_route_elev_gain(
                derived_gain_m, resolved_units
            )

            effective_distance = supplied_distance or derived_distance_display
            effective_elev_gain = supplied_elev_gain or derived_gain_display
            _ensure_route_stats_in_panel(cfg, effective_distance, effective_elev_gain)

            print("📊 Route Profile Stats")
            print(f"📏 Distance (derived): {derived_distance_km:.1f} km")
            print(f"⛰️  Elevation gain (derived): {derived_gain_m:.0f} m")
            print(
                "⚖️  Units: "
                f"{resolved_units} "
                f"(mode={route_units}, reason={units_reason})"
            )
            if supplied_distance:
                print(f"📝 Distance (supplied): {supplied_distance}")
            else:
                print(f"📝 Distance (auto): {derived_distance_display}")
            if supplied_elev_gain:
                print(f"📝 Elevation gain (supplied): {supplied_elev_gain}")
            else:
                print(f"📝 Elevation gain (auto): {derived_gain_display}")

            # Render route on map if enabled
            if route_cfg.get("enabled", False):
                _render_route_on_map(ax, route_coords, route_cfg, dpi)
                _render_route_markers(ax, route_coords, route_cfg, dpi)

            # Render elevation profile overlay
            _render_elevation_profile(
                ax, route_coords, elevation_data, elevation_cfg, mask_gdf
            )

    # Render info panel if configured
    panel_cfg = mcfg.get("info_panel")
    if panel_cfg and panel_cfg.get("enabled", False):
        # Create separate axes for panel
        if frame_enabled:
            panel_ax = fig.add_axes(
                [panel_left, panel_bottom, panel_width, panel_height_axes]
            )
        else:
            # Panel without frame - use transAxes on main ax
            panel_ax = None
        _render_info_panel(
            fig,
            panel_ax if panel_ax else ax,
            panel_cfg,
            cfg,
            use_separate_axes=(panel_ax is not None),
        )

    # Draw info text last so it is never hidden by profile/panel overlays.
    _render_map_info_text(fig, ax, mcfg.get("info", {}))

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
    parser.add_argument(
        "--route-units",
        choices=["auto", "metric", "imperial"],
        default="auto",
        help="Route stat units for auto-filled distance/elevation (default: auto)",
    )
    parser.add_argument(
        "--route-country-code",
        default="",
        help="Optional 2-letter country code used when --route-units=auto",
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
        route_units=args.route_units,
        route_country_code=args.route_country_code,
    )
