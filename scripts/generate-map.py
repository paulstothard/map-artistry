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
    print(f"[HILLSHADE-DEBUG] {debug_label}: hillshade_texture visible={hs_cfg.get('visible', False)}, gdf.empty={gdf.empty}, water_tone is None={water_tone is None}")
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


def _apply_craters_to_dem(
    dem: np.ndarray,
    craters: list[dict],
    bounds: tuple[float, float, float, float],
    pixel_size_x: float,
    pixel_size_y: float,
) -> tuple[np.ndarray, list[dict]]:
    """
    Apply impact craters to a DEM array.
    
    Args:
        dem: DEM elevation array (height, width)
        craters: List of crater dicts with keys: x, y (relative 0-1), radius_km, depth_m, rim_height_ratio, lava_level_m
        bounds: (left, bottom, right, top) in map units
        pixel_size_x: Pixel size in x direction (map units)
        pixel_size_y: Pixel size in y direction (map units, typically negative)
    
    Returns:
        Tuple of (modified DEM, list of crater metadata dicts)
        Each metadata dict contains:
            - 'disruption_zone': Polygon covering outer rim (for removing existing water)
            - 'lava_polygon': Polygon for lava lake (None if no lava)
            - 'center': Point at crater center
    """
    if not craters:
        return dem, []
    
    left, bottom, right, top = bounds
    map_width = right - left
    map_height = top - bottom
    height_px, width_px = dem.shape
    
    dem_cratered = dem.copy()
    crater_metadata = []
    
    for crater_cfg in craters:
        # Parse crater parameters
        rel_x = float(crater_cfg.get("x", 0.5))
        rel_y = float(crater_cfg.get("y", 0.5))
        radius_km = float(crater_cfg.get("radius_km", 5.0))
        depth_m = crater_cfg.get("depth_m")
        rim_height_ratio = float(crater_cfg.get("rim_height_ratio", 0.15))
        lava_level_m = crater_cfg.get("lava_level_m")
        
        # Auto-calculate depth if not provided
        if depth_m is None:
            depth_m = radius_km * 100
        
        # Convert relative position to map coordinates
        crater_x = left + rel_x * map_width
        crater_y = bottom + rel_y * map_height
        
        # Convert to pixel coordinates
        crater_px_x = int((crater_x - left) / pixel_size_x)
        crater_px_y = int((top - crater_y) / abs(pixel_size_y))
        
        # Convert radius from km to pixels
        # pixel_size_x and pixel_size_y are in degrees, need to convert km to degrees
        # at the crater's latitude for accurate calculation
        crater_lat = crater_y
        meters_per_degree_lat = 111320.0
        meters_per_degree_lon = 111320.0 * np.cos(np.radians(crater_lat))
        
        radius_deg_x = (radius_km * 1000.0) / meters_per_degree_lon
        radius_deg_y = (radius_km * 1000.0) / meters_per_degree_lat
        
        radius_px_x = abs(radius_deg_x / pixel_size_x)
        radius_px_y = abs(radius_deg_y / pixel_size_y)
        
        # Get baseline elevation
        if 0 <= crater_px_y < height_px and 0 <= crater_px_x < width_px:
            baseline_elev = dem_cratered[crater_px_y, crater_px_x]
        else:
            baseline_elev = np.nanmedian(dem_cratered)
        
        # Create coordinate grids
        y_coords, x_coords = np.ogrid[:height_px, :width_px]
        
        # Calculate angle from center for jagged rim
        dx = (x_coords - crater_px_x).astype(float)
        dy = (y_coords - crater_px_y).astype(float)
        angle = np.arctan2(dy, dx)
        
        # Store lat/lon for polygon generation
        crater_lon = crater_x
        crater_lat = crater_y
        
        # Create random generator with deterministic seed
        rng = np.random.default_rng(hash(str(crater_cfg)) % 2**32)
        
        # Add jagged variation to rim (natural-looking irregularity)
        np.random.seed(hash(str(crater_cfg)) % 2**32)  # Deterministic noise
        
        # Create a base irregularity map that varies around the rim
        # Some sections more eroded/irregular than others
        base_irregularity = np.zeros_like(angle)
        num_sectors = rng.integers(4, 8)
        for i in range(num_sectors):
            sector_angle = rng.uniform(0, 2 * np.pi)
            sector_width = rng.uniform(np.pi/3, np.pi)
            sector_strength = rng.uniform(0.5, 1.5)
            angular_dist = np.abs((angle - sector_angle + np.pi) % (2 * np.pi) - np.pi)
            base_irregularity += sector_strength * np.exp(-(angular_dist / sector_width)**2)
        base_irregularity = base_irregularity / base_irregularity.max()
        
        # Main rim variation with mixed feature sizes
        n_rim_features = 48
        rim_variation = np.zeros_like(angle)
        for i in range(n_rim_features):
            phase = np.random.uniform(0, 2*np.pi)
            # Variable amplitude - some features larger than others
            amplitude = np.random.uniform(0.02, 0.12)
            frequency = i if i > 0 else 1
            rim_variation += amplitude * np.sin(frequency * angle + phase)
        
        # Add secondary variation
        for i in range(12):
            phase = np.random.uniform(0, 2*np.pi)
            amplitude = np.random.uniform(0.01, 0.05)
            frequency = 20 + i * 5
            rim_variation += amplitude * np.sin(frequency * angle + phase)
        
        # Modulate rim variation by base irregularity (more variation in some areas)
        rim_variation = rim_variation * (0.3 + 0.7 * base_irregularity)
        
        # Distance from crater center with aspect ratio correction
        dist_px = np.sqrt((dx / radius_px_x)**2 + (dy / radius_px_y)**2) * radius_px_x
        
        # Apply rim variation with moderate multiplier
        varied_radius_px = radius_px_x * (1 + rim_variation * 0.10)
        
        # Pre-generate ejecta ray pattern to match rim variation
        # This ensures smooth transition from rim to ejecta
        # Asymmetric impact: rays concentrated in certain sectors
        ejecta_variation = np.zeros_like(angle)
        num_ejecta_rays = rng.integers(3, 8)  # Fewer rays overall
        
        # Simulate impact angle - ejecta concentrated in certain direction
        impact_angle = rng.uniform(0, 2 * np.pi)
        impact_cone_width = rng.uniform(np.pi * 0.6, np.pi * 1.2)  # Sector where most ejecta goes
        
        ejecta_ray_angles = []  # Store for later use
        for i in range(num_ejecta_rays):
            # Cluster rays in the impact cone (opposite to impact direction)
            # Some random deviation for variety
            if rng.random() < 0.7:  # 70% of rays in main ejecta cone
                ray_angle = impact_angle + rng.uniform(-impact_cone_width/2, impact_cone_width/2)
            else:  # 30% scattered elsewhere
                ray_angle = rng.uniform(0, 2 * np.pi)
            
            ray_width = rng.uniform(np.pi/10, np.pi/3)  # Variable width
            # Much more variable strength - some very strong, some barely visible
            ray_strength = rng.uniform(0.0, 1.0)**2.5  # More contrast
            angular_dist = np.abs((angle - ray_angle + np.pi) % (2 * np.pi) - np.pi)
            ejecta_variation += ray_strength * np.exp(-(angular_dist / ray_width)**2)
            ejecta_ray_angles.append((ray_angle, ray_width, ray_strength))
        
        # Blend rim variation with ejecta rays for smooth transition
        # Near rim: mostly rim variation, far from rim: mostly ejecta rays
        combined_variation = rim_variation + ejecta_variation * 0.3  # Ejecta rays extend rim irregularity
        varied_radius_px = radius_px_x * (1 + combined_variation * 0.10)
        
        # Crater profile zones - add slight variation to avoid perfect circles
        # Floor and bowl get subtle variation for more natural boundaries
        floor_variation = rim_variation * 0.3  # Subtle variation carried to floor
        flat_floor_radius = 0.35 * radius_px_x * (1 + floor_variation * 0.05)
        bowl_radius = 0.82 * radius_px_x * (1 + floor_variation * 0.08)
        inner_radius = varied_radius_px * 0.90  # Inner edge of rim
        rim_radius = varied_radius_px
        outer_radius = varied_radius_px * 1.3
        
        # Initialize crater profile with original terrain (prevents corruption)
        crater_profile = dem_cratered.copy()
        
        # Flat floor (full depth, will be filled with lava later if specified)
        floor_mask = dist_px <= flat_floor_radius
        floor_elevation = baseline_elev - depth_m
        crater_profile[floor_mask] = floor_elevation
        
        # Bowl transition (gentle curve from flat floor to rim)
        bowl_mask = (dist_px > flat_floor_radius) & (dist_px <= bowl_radius)
        bowl_progress = (dist_px[bowl_mask] - flat_floor_radius[bowl_mask]) / (bowl_radius[bowl_mask] - flat_floor_radius[bowl_mask] + 1e-6)
        bowl_depth = depth_m * (1 - bowl_progress**1.5)  # Gentler curve
        crater_profile[bowl_mask] = baseline_elev - bowl_depth
        
        # Inner wall (steeper slope to rim)
        wall_mask = (dist_px > bowl_radius) & (dist_px <= inner_radius)
        wall_progress = (dist_px[wall_mask] - bowl_radius[wall_mask]) / (inner_radius[wall_mask] - bowl_radius[wall_mask] + 1e-6)
        wall_elevation = (baseline_elev - depth_m * (1 - bowl_progress.max())) * (1 - wall_progress) + baseline_elev * wall_progress
        crater_profile[wall_mask] = wall_elevation
        
        # Rim (raised edge with variation - additive to existing terrain)
        rim_mask = (dist_px > inner_radius) & (dist_px <= rim_radius)
        rim_progress = (dist_px[rim_mask] - inner_radius[rim_mask]) / (rim_radius[rim_mask] - inner_radius[rim_mask] + 1e-6)
        rim_height = depth_m * rim_height_ratio
        # Add rim height to original terrain to preserve local variation
        crater_profile[rim_mask] = dem_cratered[rim_mask] + rim_height * (1 - rim_progress**2)
        
        # Ejecta/blend zone with irregular outer boundary and radial streaking
        # Use the pre-generated ejecta rays for consistency with rim
        # Outer radius extends from the varied rim smoothly
        outer_radius = varied_radius_px * (1.1 + np.clip(ejecta_variation, 0, 1.0) * 0.25)
        
        blend_mask = (dist_px > rim_radius) & (dist_px <= outer_radius)
        blend_progress = (dist_px[blend_mask] - rim_radius[blend_mask]) / (outer_radius[blend_mask] - rim_radius[blend_mask] + 1e-6)
        
        # Rougher, less uniform falloff with radial streaking
        # Base falloff
        smooth_falloff = 1 - blend_progress**1.5
        
        # Add radial streak modulation (ejecta density varies)
        # Use same asymmetric pattern as the rays - cluster in impact direction
        radial_streaks = np.zeros_like(dist_px)
        num_streaks = rng.integers(3, 7)  # Fewer, more prominent streaks
        for i in range(num_streaks):
            # Cluster streaks in impact cone like rays
            if rng.random() < 0.7:
                ray_angle = impact_angle + rng.uniform(-impact_cone_width/2, impact_cone_width/2)
            else:
                ray_angle = rng.uniform(0, 2 * np.pi)
            
            base_ray_width = rng.uniform(np.pi/6, np.pi/3)
            streak_strength = rng.uniform(0.0, 1.0)**2.0
            angular_dist = np.abs((angle - ray_angle + np.pi) % (2 * np.pi) - np.pi)
            
            # Add irregular, fingered edges to the ray instead of smooth Gaussian
            # Create angular variation that changes with radial distance
            radial_normalized = dist_px / (varied_radius_px.mean() if hasattr(varied_radius_px, 'mean') else varied_radius_px)
            
            # Multiple frequency components for irregular edge
            angular_perturbation = np.zeros_like(angular_dist)
            for freq in [3, 7, 11]:  # Different frequencies create fingering
                phase = rng.uniform(0, 2 * np.pi)
                angular_perturbation += 0.3 * np.sin(radial_normalized * freq * np.pi + phase) * base_ray_width
            
            # Modulate ray width with radial distance (narrower far from crater)
            ray_width = base_ray_width * (1.2 - 0.7 * radial_normalized)
            
            # Apply perturbation to create irregular edges
            perturbed_angular_dist = angular_dist + angular_perturbation
            
            # Sharp cutoff with some noise instead of smooth Gaussian
            edge_noise = rng.uniform(0.7, 1.0, angular_dist.shape)
            ray_mask = (np.abs(perturbed_angular_dist) < ray_width * edge_noise)
            
            # Internal variation - not uniform density
            internal_variation = 0.5 + 0.5 * np.sin(radial_normalized * 6 * np.pi + rng.uniform(0, 2*np.pi))
            
            # Combine into final streak pattern
            ray_profile = np.zeros_like(angular_dist)
            ray_profile[ray_mask] = streak_strength * internal_variation[ray_mask] * (1.0 - (np.abs(perturbed_angular_dist[ray_mask]) / (ray_width[ray_mask] + 1e-6))**0.5)
            
            radial_streaks += ray_profile
        radial_streaks = np.clip(radial_streaks, 0, 1)
        
        # Ejecta concentrated along rays, thin between them
        # Much more dramatic variation - areas without rays have minimal ejecta
        smooth_falloff = smooth_falloff * (0.15 + 0.85 * radial_streaks[blend_mask])
        
        # Add small irregular bumps/mounds in ejecta field - concentrated in rays
        ejecta_texture = np.random.normal(0, rim_height * 0.15, crater_profile.shape)
        ejecta_texture = gaussian_filter(ejecta_texture, sigma=3.0)
        
        crater_profile[blend_mask] = baseline_elev + ejecta_texture[blend_mask] * smooth_falloff
        
        # Add secondary cratering in ejecta field (small impact craters from ejected material)
        num_secondary = rng.integers(12, 25)  # Increased from 6-15 for more visible secondaries
        for i in range(num_secondary):
            # Random position in ejecta field
            sec_angle = rng.uniform(0, 2 * np.pi)
            sec_distance = rng.uniform(rim_radius.mean() * 1.05, outer_radius.mean() * 0.95)
            sec_radius = rng.uniform(radius_px_x * 0.04, radius_px_x * 0.12)  # Larger
            sec_depth = rim_height * rng.uniform(0.5, 1.5)  # Deeper, more visible
            
            # Calculate distance from secondary crater center
            sec_dx = dx - sec_distance * np.cos(sec_angle)
            sec_dy = dy - sec_distance * np.sin(sec_angle)
            sec_dist = np.sqrt(sec_dx**2 + sec_dy**2)
            
            # Only affect pixels in ejecta field near this secondary crater
            sec_mask = (sec_dist < sec_radius) & blend_mask
            if sec_mask.any():
                sec_progress = sec_dist[sec_mask] / sec_radius
                sec_profile = -sec_depth * (1 - sec_progress**2)
                crater_profile[sec_mask] += sec_profile
        
        # Add concentric ripples/terraces (like slumping in crater walls)
        # Random parameters per crater for variation
        num_ripples = rng.integers(1, 4)  # Just 1-3 major terraces
        ripple_amplitude = rng.uniform(0.08, 0.15) * depth_m  # Stronger, more visible
        
        # Apply ripples mainly to bowl and wall areas (not flat floor)
        flat_floor_mean = flat_floor_radius.mean() if hasattr(flat_floor_radius, 'mean') else flat_floor_radius
        ripple_mask = dist_px > flat_floor_mean * 0.8
        
        if ripple_mask.any() and num_ripples > 0:
            # Normalized radial distance for ripple calculation
            ripple_dist = (dist_px[ripple_mask] - flat_floor_mean) / (radius_px_x - flat_floor_mean + 1e-6)
            
            # Create irregularly-spaced ripples by placing them at random positions
            ripple_sum = np.zeros_like(ripple_dist)
            for i in range(num_ripples):
                # Random radial position for this terrace (between 0.2 and 0.8 of the distance)
                ripple_center = rng.uniform(0.2, 0.8)
                # Random width/sharpness for this terrace
                ripple_width = rng.uniform(0.08, 0.2)
                # Random strength variation per ripple
                ripple_strength = rng.uniform(0.6, 1.0)
                
                # Create a localized bump/terrace
                ripple_contribution = ripple_strength * np.exp(-((ripple_dist - ripple_center) / ripple_width)**2)
                ripple_sum += ripple_contribution
            
            # Apply ripples
            crater_profile[ripple_mask] += ripple_amplitude * ripple_sum
        
        # Add multi-scale surface texture variation (scarred, rough terrain)
        # Large-scale scarring (Impact features, major cracks) - stronger
        large_texture = np.random.normal(0, depth_m * 0.18, crater_profile.shape)
        large_texture = gaussian_filter(large_texture, sigma=12.0)
        
        # Medium-scale roughness (Secondary impacts, erosion) - stronger
        medium_texture = np.random.normal(0, depth_m * 0.10, crater_profile.shape)
        medium_texture = gaussian_filter(medium_texture, sigma=5.0)
        
        # Fine-scale detail (Surface irregularities) - more visible
        fine_texture = np.random.normal(0, depth_m * 0.04, crater_profile.shape)
        fine_texture = gaussian_filter(fine_texture, sigma=1.5)
        
        # Combine textures with distance-based weighting
        combined_texture = large_texture + medium_texture + fine_texture
        
        # Apply texture to entire crater (including floor for rough lava base)
        crater_interior_mask = dist_px <= rim_radius
        crater_profile[crater_interior_mask] += combined_texture[crater_interior_mask]
        
        # Add wall slump scars (collapsed material on crater walls)
        num_slumps = rng.integers(2, 5)
        wall_and_bowl_mask = (dist_px > flat_floor_mean * 0.6) & (dist_px <= rim_radius)
        
        for i in range(num_slumps):
            slump_angle = rng.uniform(0, 2 * np.pi)
            slump_width = rng.uniform(np.pi/8, np.pi/4)
            slump_depth = rng.uniform(0.03, 0.08) * depth_m
            
            angular_dist = np.abs((angle - slump_angle + np.pi) % (2 * np.pi) - np.pi)
            slump_mask = (angular_dist < slump_width) & wall_and_bowl_mask
            
            if slump_mask.any():
                # Radial distance for falloff
                radial_progress = (dist_px[slump_mask] - flat_floor_mean) / (radius_px_x - flat_floor_mean + 1e-6)
                # Angular falloff
                angular_falloff = 1.0 - (angular_dist[slump_mask] / slump_width)**2
                # Create slump depression with some texture
                slump_pattern = -slump_depth * angular_falloff * (0.8 + 0.2 * np.sin(radial_progress * 8 * np.pi))
                crater_profile[slump_mask] += slump_pattern
        
        # Add scattered small pockmarks across crater surface
        num_pockmarks = rng.integers(15, 30)
        for i in range(num_pockmarks):
            pock_angle = rng.uniform(0, 2 * np.pi)
            pock_distance = rng.uniform(0.2, 1.0) * radius_px_x
            pock_x = pock_distance * np.cos(pock_angle)
            pock_y = pock_distance * np.sin(pock_angle)
            
            pock_radius = rng.uniform(0.015, 0.04) * radius_px_x
            pock_depth = rng.uniform(0.01, 0.03) * depth_m
            
            pock_dist = np.sqrt((dx - pock_x)**2 + (dy - pock_y)**2)
            pock_mask = (pock_dist < pock_radius * 1.5) & crater_interior_mask
            
            if pock_mask.any():
                pock_profile = -pock_depth * np.exp(-(pock_dist[pock_mask] / pock_radius)**2.5)
                crater_profile[pock_mask] += pock_profile
        
        # Add radial cracks/scars as V-shaped gouges that can intersect
        num_cracks = rng.integers(8, 16)
        crack_accumulator = np.zeros_like(crater_profile)
        
        for i in range(num_cracks):
            crack_angle = rng.uniform(0, 2 * np.pi)
            base_crack_width = rng.uniform(0.015, 0.06) * radius_px_x
            max_crack_depth = rng.uniform(0.3, 0.8) * depth_m * 0.15
            
            # Calculate angular difference
            angular_diff = np.abs((angle - crack_angle + np.pi) % (2 * np.pi) - np.pi)
            
            # Get mean radii for calculations (handle both scalar and array cases)
            flat_floor_mean = flat_floor_radius.mean() if hasattr(flat_floor_radius, 'mean') else flat_floor_radius
            varied_mean = varied_radius_px.mean() if hasattr(varied_radius_px, 'mean') else varied_radius_px
            
            # Add wandering/irregularity to crack path (not perfectly straight)
            wander_frequency = rng.uniform(0.15, 0.35)
            wander_amplitude = rng.uniform(0.01, 0.04) * radius_px_x
            radial_position = np.clip((dist_px - flat_floor_mean * 0.5) / (varied_mean * 1.15 - flat_floor_mean * 0.5 + 1e-6), 0, 1)
            wander_offset = wander_amplitude * np.sin(radial_position * wander_frequency * np.pi * 8)
            angular_diff = np.abs(angular_diff - wander_offset / dist_px.clip(1))
            
            # Variable width: narrower at ends, wider in middle
            width_variation = 1.0 - radial_position**2
            crack_width = base_crack_width * (0.4 + 0.6 * width_variation)
            
            # Crack mask extends into ejecta zone
            crack_mask = (angular_diff < crack_width / dist_px.clip(1)) & (dist_px > flat_floor_mean * 0.5) & (dist_px <= varied_mean * 1.15)
            
            if not crack_mask.any():
                continue
            
            # V-shaped profile instead of Gaussian (sharper, more gouge-like)
            normalized_width = angular_diff[crack_mask] / (crack_width[crack_mask] / dist_px[crack_mask].clip(1))
            v_profile = np.maximum(0, 1.0 - normalized_width)  # Linear V-shape
            
            # Depth variation: deeper near crater rim, shallower toward ends
            depth_variation = 1.0 - (radial_position[crack_mask] ** 1.5) * 0.6
            
            # Fade cracks as they extend beyond rim
            crack_falloff = np.ones(crack_mask.sum())
            dist_masked = dist_px[crack_mask]
            rim_masked = rim_radius[crack_mask] if isinstance(rim_radius, np.ndarray) else rim_radius
            varied_masked = varied_radius_px[crack_mask] if isinstance(varied_radius_px, np.ndarray) else varied_radius_px
            
            beyond_rim_sub = dist_masked > rim_masked
            if beyond_rim_sub.any():
                crack_falloff[beyond_rim_sub] = np.clip(1.0 - ((dist_masked[beyond_rim_sub] - rim_masked[beyond_rim_sub]) / (varied_masked[beyond_rim_sub] * 0.15)), 0, 1)
            
            # Calculate final crack depth with all variations
            crack_depth_array = max_crack_depth * v_profile * depth_variation * crack_falloff
            
            # Accumulate cracks (take maximum where they overlap for realistic intersections)
            crack_accumulator[crack_mask] = np.maximum(crack_accumulator[crack_mask], crack_depth_array)
        
        # Apply accumulated cracks to crater profile
        crater_profile -= crack_accumulator
        
        # Add extra rim surface irregularities (bumps and scars)
        rim_surface_mask = (dist_px > inner_radius) & (dist_px <= rim_radius)
        if rim_surface_mask.any():
            rim_bumps = np.random.normal(0, rim_height * 0.25, crater_profile.shape)
            rim_bumps = gaussian_filter(rim_bumps, sigma=1.5)
            crater_profile[rim_surface_mask] += rim_bumps[rim_surface_mask]
        
        # Apply lava fill if specified
        if lava_level_m is not None:
            # Find the absolute minimum elevation in the DEM for reference
            min_elev = np.nanmin(dem_cratered)
            # Set lava surface very low to hit the bright yellow/orange in color gradient
            # lava_level_m now represents how much to fill (0 = full depth, depth_m = no lava)
            lava_depth_from_baseline = depth_m - lava_level_m
            base_lava_surface = baseline_elev - lava_depth_from_baseline
            # Clamp to at least the minimum to ensure bright coloring
            base_lava_surface = min(base_lava_surface, min_elev + depth_m * 0.1)
            
            # Flat lava surface (like a calm lake) - hillshade comes from floor texture underneath
            lava_surface = base_lava_surface
            
            # DON'T modify the DEM - keep the textured floor for hillshade sampling
            # The lava_surface value is only used for polygon generation and color mapping
            # The water polygon will sample the textured crater floor underneath for hillshade
        
        # Apply crater: replace terrain within crater zone, blend at edges
        impact_mask = dist_px <= rim_radius
        dem_cratered[impact_mask] = crater_profile[impact_mask]
        
        # Blend zone
        dem_cratered[blend_mask] = (
            smooth_falloff * crater_profile[blend_mask] +
            (1 - smooth_falloff) * dem_cratered[blend_mask]
        )
        
        # Generate polygon metadata for water layer modification
        # Disruption zone: circular polygon at outer radius (where impact disrupts existing water)
        disruption_radius_deg_x = (radius_km * 1000 * 1.3) / (111320 * np.cos(np.radians(crater_lat)))
        disruption_radius_deg_y = (radius_km * 1000 * 1.3) / 111320
        
        # Create circular disruption zone
        num_points = 64
        disruption_angles = np.linspace(0, 2 * np.pi, num_points, endpoint=False)
        disruption_x = crater_lon + disruption_radius_deg_x * np.cos(disruption_angles)
        disruption_y = crater_lat + disruption_radius_deg_y * np.sin(disruption_angles)
        disruption_polygon = Polygon(zip(disruption_x, disruption_y))
        
        # Create lava lake polygon if lava is present
        lava_polygon = None
        if lava_level_m is not None and lava_level_m > 0:
            # Calculate lava surface elevation
            lava_depth_from_baseline = depth_m - lava_level_m
            lava_lake_surface = baseline_elev - lava_depth_from_baseline
            
            # Estimate lava extent based on fill level
            # lava_level_m = 0 means filled to rim (depth_m filled)
            # lava_level_m = depth_m means empty (0 filled)
            # Calculate fill percentage
            fill_percentage = lava_level_m / depth_m
            
            # Lava radius varies from flat_floor (empty) to bowl_radius (full)
            # Use mean values since these now have angular variation
            flat_floor_mean = flat_floor_radius.mean() if hasattr(flat_floor_radius, 'mean') else flat_floor_radius
            bowl_mean = bowl_radius.mean() if hasattr(bowl_radius, 'mean') else bowl_radius
            lava_radius_px_base = flat_floor_mean + fill_percentage * (bowl_mean - flat_floor_mean)
            
            # Convert to geographic coordinates
            lava_radius_m = lava_radius_px_base * abs(pixel_size_x) * meters_per_degree_lon
            lava_radius_deg_lon = lava_radius_m / meters_per_degree_lon
            lava_radius_deg_lat = lava_radius_m / meters_per_degree_lat
            
            num_edge_points = 120
            lava_edge_angles = np.linspace(0, 2 * np.pi, num_edge_points, endpoint=False)
            lava_edge_x = []
            lava_edge_y = []
            
            # Generate irregular edge based on lava radius and angular variation
            for angle in lava_edge_angles:
                # Add angular irregularity (8-12 lobes plus some randomness)
                angular_var = 0.0
                num_lobes = 8
                angular_var += 0.12 * np.sin(angle * num_lobes + rng.uniform(0, 2 * np.pi))
                angular_var += 0.06 * np.sin(angle * 3 + rng.uniform(0, 2 * np.pi))
                angular_var += 0.03 * rng.uniform(-1, 1)
                
                # Apply variation to radius (±15% variation)
                varied_radius_lon = lava_radius_deg_lon * (1.0 + angular_var * 0.15)
                varied_radius_lat = lava_radius_deg_lat * (1.0 + angular_var * 0.15)
                
                # Convert to geographic coordinates
                edge_x = crater_lon + varied_radius_lon * np.cos(angle)
                edge_y = crater_lat + varied_radius_lat * np.sin(angle)
                
                lava_edge_x.append(edge_x)
                lava_edge_y.append(edge_y)
            
            if len(lava_edge_x) > 3:
                lava_polygon = Polygon(zip(lava_edge_x, lava_edge_y))
        
        # Store metadata for this crater
        crater_metadata.append({
            'disruption_zone': disruption_polygon,
            'lava_polygon': lava_polygon,
            'center': Point(crater_lon, crater_lat),
            'remove_overlapping_water': crater_cfg.get('remove_overlapping_water', True),
            'label': crater_cfg.get('label'),
        })
    
    return dem_cratered, crater_metadata


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
    crater_metadata = []  # Initialize for crater modifications to water layers
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

                # Apply craters if configured
                craters_cfg = mcfg.get("craters", [])
                if craters_cfg:
                    dem_filled, crater_metadata = _apply_craters_to_dem(
                        dem=dem_filled,
                        craters=craters_cfg,
                        bounds=(left, bottom, right, top),
                        pixel_size_x=target_transform.a,
                        pixel_size_y=target_transform.e,
                    )

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
        
        # Apply crater modifications to water layers
        if crater_metadata and layer_cfg["layer"] in ["water", "ocean", "waterway"]:
            # Remove existing water features that overlap with crater disruption zones
            for crater_meta in crater_metadata:
                if crater_meta.get('remove_overlapping_water', True):
                    disruption_zone = crater_meta['disruption_zone']
                    # Filter out features that intersect the disruption zone
                    if not gdf.empty:
                        gdf = gdf[~gdf.intersects(disruption_zone)]
            
            # Add lava lake polygons to water/ocean layers (not waterways)
            if layer_cfg["layer"] in ["water", "ocean"] and layer_cfg["geometry_type"] == "Polygon":
                lava_features = []
                for crater_meta in crater_metadata:
                    if crater_meta['lava_polygon'] is not None:
                        lava_features.append({
                            'geometry': crater_meta['lava_polygon']
                        })
                
                if lava_features:
                    # Create GeoDataFrame for lava lakes with same CRS as water layer
                    lava_gdf = gpd.GeoDataFrame(lava_features, crs=gdf.crs if not gdf.empty else 'EPSG:4326')
                    print(f"[CRATER-DEBUG] Adding {len(lava_features)} lava lakes to {layer_cfg['layer']} layer")
                    print(f"[CRATER-DEBUG] Lava CRS: {lava_gdf.crs}, Water CRS: {gdf.crs if not gdf.empty else 'empty'}")
                    # Concatenate with existing water features
                    gdf = gpd.GeoDataFrame(pd.concat([gdf, lava_gdf], ignore_index=True), crs=gdf.crs if not gdf.empty else lava_gdf.crs)
                    print(f"[CRATER-DEBUG] After adding lava, {layer_cfg['layer']} has {len(gdf)} total features")

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
            print(f"[RENDER-DEBUG] Layer {layer_key} rendering {len(rest)} unstyled features (including lava lakes)")
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

    # Draw crater labels if present
    if crater_metadata:
        for crater_meta in crater_metadata:
            label = crater_meta.get('label')
            if label:
                center = crater_meta['center']
                # Draw text with white fill and black outline for high visibility
                ax.text(
                    center.x,
                    center.y,
                    str(label),
                    ha='center',
                    va='center',
                    fontsize=14,
                    fontweight='bold',
                    color='white',
                    zorder=101,
                    bbox=dict(boxstyle='circle,pad=0.3', facecolor='black', edgecolor='white', linewidth=2, alpha=0.8)
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
