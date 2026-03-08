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
    stretch: str | None = None,
    exponent: float = 1.0,
) -> np.ndarray:
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


def _blend_multiply(base_rgb: np.ndarray, shade: np.ndarray, strength: float) -> np.ndarray:
    shade_rgb = np.repeat(shade[..., np.newaxis], 3, axis=2)
    multiplied = base_rgb * shade_rgb
    return np.clip(base_rgb * (1.0 - strength) + multiplied * strength, 0.0, 1.0)


def _blend_soft_light(base_rgb: np.ndarray, shade: np.ndarray, strength: float) -> np.ndarray:
    shade_rgb = np.repeat(shade[..., np.newaxis], 3, axis=2)
    soft = np.where(
        shade_rgb <= 0.5,
        base_rgb - (1.0 - 2.0 * shade_rgb) * base_rgb * (1.0 - base_rgb),
        base_rgb
        + (2.0 * shade_rgb - 1.0)
        * (np.sqrt(np.clip(base_rgb, 0.0, 1.0)) - base_rgb),
    )
    return np.clip(base_rgb * (1.0 - strength) + soft * strength, 0.0, 1.0)


def _make_hypsometric_colormap(colors: list[str] | None = None) -> LinearSegmentedColormap:
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
    debug_label: str | None = None,
    debug: bool = False,
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
    sampled_tone = np.empty((tex_height, tex_width), dtype=np.float32)
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
        sampled_valid = np.empty((tex_height, tex_width), dtype=np.uint8)
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

    if debug:
        mask_bool = mask.astype(bool)
        tone_vals = sampled_tone[mask_bool]
        tone_min = float(np.min(tone_vals)) if tone_vals.size else float("nan")
        tone_max = float(np.max(tone_vals)) if tone_vals.size else float("nan")
        tone_std = float(np.std(tone_vals)) if tone_vals.size else float("nan")
        if sampled_valid is not None:
            valid_mask = mask_bool & sampled_valid.astype(bool)
            valid_fraction = (
                float(np.count_nonzero(valid_mask)) / float(np.count_nonzero(mask_bool))
                if np.count_nonzero(mask_bool)
                else float("nan")
            )
            valid_vals = sampled_tone[valid_mask]
            valid_std = float(np.std(valid_vals)) if valid_vals.size else float("nan")
        else:
            valid_fraction = float("nan")
            valid_std = float("nan")
        print(
            "[water-hillshade-debug]"
            f" layer={debug_label!r}"
            f" bounds=({xmin:.6f}, {ymin:.6f}, {xmax:.6f}, {ymax:.6f})"
            f" tone_min={tone_min:.4f}"
            f" tone_max={tone_max:.4f}"
            f" tone_std={tone_std:.6f}"
            f" valid_fraction={valid_fraction:.4f}"
            f" valid_std={valid_std:.6f}"
        )

    base_rgb = np.array(to_rgb(style.get("fc", "#000000")), dtype=np.float32)
    textured_rgb = _modulate_rgb(base_rgb, variation)

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
    for az, weight in zip(azimuths, weights):
        ls = LightSource(azdeg=az, altdeg=altitude)
        shade = ls.hillshade(dem, vert_exag=vert_exag, dx=dx, dy=dy)
        shades.append(shade * weight)

    combined = np.sum(shades, axis=0) / np.sum(weights)
    return _normalize_array(combined)


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
    debug_water_hillshade = bool(mcfg.get("debug_water_hillshade", False))
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
        mask_gdf = gpd.read_file(geojson_path)
    except (FileNotFoundError, Exception) as e:
        print(f"Error: Could not read mask file '{geojson_path}': {e}")
        return
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

                shade = _compute_multidirectional_hillshade(
                    dem=dem_smoothed,
                    dx=dx,
                    dy=dy,
                    altitude=altitude,
                    azimuths=azimuths,
                    weights=weights,
                    vert_exag=vert_exag,
                )

                # Apply unsharp masking to enhance detail
                unsharp_radius = hs_cfg.get("unsharp_radius", 0.0)
                unsharp_amount = hs_cfg.get("unsharp_amount", 0.0)
                if unsharp_radius > 0 and unsharp_amount > 0:
                    shade_blurred = gaussian_filter(shade, sigma=unsharp_radius)
                    shade = shade + unsharp_amount * (shade - shade_blurred)
                    shade = np.clip(shade, 0, 1)

                # keep invalid DEM cells transparent / background-colored for land rendering
                shade = np.where(finite, shade, 1.0)

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
                water_tone[valid_blur] = blurred_shade[valid_blur] / blurred_weight[valid_blur]

                water_tone = 0.5 + (water_tone - 0.5) * contrast
                water_tone = np.clip(water_tone + bias, 0.0, 1.0).astype(np.float32)

                water_valid = (blurred_weight > 0.002).astype(np.uint8)

                terrain_visible = terrain_cfg.get("visible", False)
                if terrain_visible:
                    elev_percentiles = terrain_cfg.get("percentiles", [2, 98])
                    stretch = terrain_cfg.get("stretch", "linear")
                    stretch_exponent = terrain_cfg.get("stretch_exponent", 1.0)
                    terrain_norm = _normalize_dem_for_colormap(
                        dem_resampled,
                        finite_mask=finite,
                        percentiles=elev_percentiles,
                        stretch=stretch,
                        exponent=stretch_exponent,
                    )

                    cmap = _make_hypsometric_colormap(terrain_cfg.get("colors"))
                    terrain_rgb = cmap(terrain_norm)[..., :3]

                    invalid_rgb = np.array(plt.matplotlib.colors.to_rgb(face_fc))
                    terrain_rgb[~finite] = invalid_rgb

                    blend_mode = terrain_cfg.get("blend_mode", "soft_light")
                    shade_strength = terrain_cfg.get("shade_strength", 0.6)
                    if blend_mode == "multiply":
                        terrain_img = _blend_multiply(terrain_rgb, shade, shade_strength)
                    else:
                        terrain_img = _blend_soft_light(terrain_rgb, shade, shade_strength)

                    ax.imshow(
                        terrain_img,
                        extent=[left, right, bottom, top],
                        zorder=terrain_cfg.get("zorder", hs_cfg.get("zorder", 0)),
                        alpha=terrain_cfg.get("alpha", 1.0),
                        interpolation=terrain_cfg.get("interpolation", "bicubic"),
                        aspect="auto",
                    )
                else:
                    ax.imshow(
                        shade,
                        cmap=hs_cfg.get("cmap", "gray"),
                        alpha=hs_cfg.get("alpha", 0.5),
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
            gdf = gpd.read_file(layer_cfg["file"], layer=layer_cfg["layer"])
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
                    if not layer_palette:
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
                            debug_label=layer_key,
                            debug=debug_water_hillshade,
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
                if not layer_palette:
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
                        debug_label=layer_key,
                        debug=debug_water_hillshade,
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
