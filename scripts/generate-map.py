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
        craters: List of crater dicts with keys:
            Required: x, y (relative 0-1), radius_km
            Optional: depth_m, depth_ratio, rim_height_ratio, flat_floor_ratio, bowl_exponent, lava_level_m
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
        depth_ratio = crater_cfg.get("depth_ratio")
        rim_height_ratio = crater_cfg.get("rim_height_ratio")
        if rim_height_ratio is None:
            rim_height_ratio = np.random.uniform(0.12, 0.25)  # Higher and more variable rims
        else:
            rim_height_ratio = float(rim_height_ratio)
        lava_level_m = crater_cfg.get("lava_level_m")
        flat_floor_ratio = crater_cfg.get("flat_floor_ratio")
        if flat_floor_ratio is None:
            flat_floor_ratio = np.random.uniform(0.06, 0.65)
        else:
            flat_floor_ratio = float(flat_floor_ratio)
        bowl_exponent = crater_cfg.get("bowl_exponent")
        if bowl_exponent is None:
            bowl_exponent = 1.0
        else:
            bowl_exponent = float(bowl_exponent)

        # Calculate depth with priority: depth_m > depth_ratio > auto-calculate
        if depth_m is not None:
            # If depth is provided directly, apply only minimum scaling to avoid unrealistically shallow craters
            min_depth = radius_km * 1000 * 0.2  # At least 20% of radius
            depth_m = max(depth_m, min_depth)
        elif depth_ratio is not None:
            # Use depth_ratio if provided (ratio of radius)
            depth_m = radius_km * 1000 * float(depth_ratio)
        else:
            # Auto-calculate depth if not provided - scale with radius for consistent appearance
            # Very deep craters for dramatic appearance
            depth_m = radius_km * 1000 * 0.8  # 80% of radius for deeper craters

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

        # MEMORY OPTIMIZATION: Calculate bounding box for this crater
        # Only process the affected region (crater + ejecta zone + secondary craters + blend)
        # Buffer needs to cover: outer_radius (1.3x) + blend (0.25 of 1.3 = 0.325x) + margin = ~1.75x
        buffer_px = int(max(radius_px_x, radius_px_y) * 1.8)
        y_min = max(0, crater_px_y - buffer_px)
        y_max = min(height_px, crater_px_y + buffer_px)
        x_min = max(0, crater_px_x - buffer_px)
        x_max = min(width_px, crater_px_x + buffer_px)

        # Extract DEM sub-array for this crater region (MUCH smaller than full DEM!)
        dem_region = dem_cratered[y_min:y_max, x_min:x_max].copy()
        region_height = y_max - y_min
        region_width = x_max - x_min

        # Create coordinate grids for sub-array only
        y_coords, x_coords = np.ogrid[y_min:y_max, x_min:x_max]

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
            sector_width = rng.uniform(np.pi / 3, np.pi)
            sector_strength = rng.uniform(0.5, 1.5)
            angular_dist = np.abs((angle - sector_angle + np.pi) % (2 * np.pi) - np.pi)
            base_irregularity += sector_strength * np.exp(
                -((angular_dist / sector_width) ** 2)
            )
        base_irregularity = base_irregularity / base_irregularity.max()

        # SEPARATE: Large-scale + medium-scale shape variation (for crater outline/silhouette)
        # Low frequencies (1-8) for smooth large-scale shape
        low_freq_shape = np.zeros_like(angle)
        for i in range(1, 9):
            phase = np.random.uniform(0, 2 * np.pi)
            amplitude = np.random.uniform(0.03, 0.08)
            low_freq_shape += amplitude * np.sin(i * angle + phase)

        # Medium frequencies (8-16) for natural irregularity, lightly smoothed to avoid zipper
        medium_freq_shape = np.zeros_like(angle)
        for i in range(8, 17):
            phase = np.random.uniform(0, 2 * np.pi)
            amplitude = np.random.uniform(0.04, 0.08)  # Stronger medium frequencies
            medium_freq_shape += amplitude * np.sin(i * angle + phase)
        # Light smoothing of medium frequencies to prevent saw-tooth while keeping geological irregularity
        medium_freq_shape = gaussian_filter(
            medium_freq_shape, sigma=1.2
        )  # Less smoothing

        # Combine low and medium frequencies for boundary shape
        shape_variation = low_freq_shape + medium_freq_shape
        shape_variation = shape_variation * (0.3 + 0.7 * base_irregularity)

        # Create separate outer boundary variation (stronger, more irregular)
        outer_boundary_variation = np.zeros_like(angle)
        for i in range(6, 18):  # Overlapping range for different character
            phase = np.random.uniform(0, 2 * np.pi)
            amplitude = np.random.uniform(0.05, 0.12)
            outer_boundary_variation += amplitude * np.sin(i * angle + phase)
        outer_boundary_variation = gaussian_filter(outer_boundary_variation, sigma=1.0)
        outer_boundary_variation = outer_boundary_variation * (
            0.3 + 0.7 * base_irregularity
        )

        # SEPARATE: High-frequency rim texture (for elevation detail, NOT outline)
        rim_texture = np.zeros_like(angle)
        for i in range(20, 48):  # Higher frequencies for surface detail only
            phase = np.random.uniform(0, 2 * np.pi)
            amplitude = np.random.uniform(0.01, 0.04)
            rim_texture += amplitude * np.sin(i * angle + phase)
        rim_texture = rim_texture * (0.3 + 0.7 * base_irregularity)

        # Distance from crater center with aspect ratio correction
        dist_px = (
            np.sqrt((dx / radius_px_x) ** 2 + (dy / radius_px_y) ** 2) * radius_px_x
        )
        
        # Apply shape distortion to the distance field itself to make crater irregular
        # This creates an elliptical/irregular crater shape (not just irregular rim)
        distortion_strength = rng.uniform(0.05, 0.10)  # 5-10% distortion for subtle irregularity
        dist_px_distorted = dist_px * (1 - shape_variation * distortion_strength)

        # Use shape variation (low + medium freq) for crater boundary
        varied_radius_px = radius_px_x * (1 + shape_variation * 0.10)

        # Pre-generate ejecta ray pattern to match rim variation
        # This ensures smooth transition from rim to ejecta
        # Asymmetric impact: rays concentrated in certain sectors
        ejecta_variation = np.zeros_like(angle)
        num_ejecta_rays = rng.integers(3, 8)  # Fewer rays overall

        # Simulate impact angle - ejecta concentrated in certain direction
        impact_angle = rng.uniform(0, 2 * np.pi)
        impact_cone_width = rng.uniform(
            np.pi * 0.6, np.pi * 1.2
        )  # Sector where most ejecta goes

        ejecta_ray_angles = []  # Store for later use
        for i in range(num_ejecta_rays):
            # Cluster rays in the impact cone (opposite to impact direction)
            # Some random deviation for variety
            if rng.random() < 0.7:  # 70% of rays in main ejecta cone
                ray_angle = impact_angle + rng.uniform(
                    -impact_cone_width / 2, impact_cone_width / 2
                )
            else:  # 30% scattered elsewhere
                ray_angle = rng.uniform(0, 2 * np.pi)

            ray_width = rng.uniform(np.pi / 10, np.pi / 3)  # Variable width
            # Much more variable strength - some very strong, some barely visible
            ray_strength = rng.uniform(0.0, 1.0) ** 2.5  # More contrast
            angular_dist = np.abs((angle - ray_angle + np.pi) % (2 * np.pi) - np.pi)
            ejecta_variation += ray_strength * np.exp(
                -((angular_dist / ray_width) ** 2)
            )
            ejecta_ray_angles.append((ray_angle, ray_width, ray_strength))

        # Blend SMOOTHED shape variation with ejecta rays for outer boundary
        # Outer ejecta should be more lobate, less jagged
        combined_variation = shape_variation * 0.5 + ejecta_variation * 0.3
        varied_radius_px = radius_px_x * (1 + combined_variation * 0.10)

        # Crater profile zones - add slight variation to avoid perfect circles
        # Floor and bowl get subtle variation for more natural boundaries
        floor_variation = shape_variation * 0.3  # Use smooth shape, not texture
        flat_floor_radius = flat_floor_ratio * radius_px_x * (1 + floor_variation * 0.05)
        bowl_radius = 0.82 * radius_px_x * (1 + floor_variation * 0.08)
        inner_radius = varied_radius_px * 0.90  # Inner edge of rim
        rim_radius = varied_radius_px
        outer_radius = varied_radius_px * 1.3

        # Initialize crater as additive delta field (change from baseline)
        # Build as ONE continuous radial profile - no separate zone formulas
        crater_delta = np.zeros_like(dem_region)

        # Create continuous elevation profile across all radial zones
        # Elevation and slope must match at every boundary (no steps or kinks)
        rim_height = depth_m * rim_height_ratio

        # For each pixel, compute its continuous elevation based on radial distance
        # Profile segments blend smoothly at boundaries
        # Use distorted distance for crater shape

        # Zone 1: Flat floor (r <= flat_floor_radius)
        floor_mask = dist_px_distorted <= flat_floor_radius
        crater_delta[floor_mask] = -depth_m

        # Add debris to flat floor (small craters + noise for realism)
        if floor_mask.any():
            # Add subtle noise/roughness to simulate debris and rough texture
            noise_scale = depth_m * 0.008  # Very subtle variation
            floor_noise = np.random.normal(0, noise_scale, size=crater_delta.shape)
            crater_delta[floor_mask] += floor_noise[floor_mask]
            
            # Add small floor craters (simulating later impacts)
            num_floor_craters = rng.integers(8, 18)  # Variable number
            for _ in range(num_floor_craters):
                # Random position within floor
                floor_angle = rng.uniform(0, 2 * np.pi)
                floor_dist = rng.uniform(0, 0.85 * flat_floor_radius.mean() if hasattr(flat_floor_radius, 'mean') else 0.85 * flat_floor_radius)
                
                fc_x = floor_dist * np.cos(floor_angle)
                fc_y = floor_dist * np.sin(floor_angle)
                
                # Small crater size (0.5% to 3% of main crater)
                fc_radius = rng.uniform(radius_px_x * 0.005, radius_px_x * 0.03)
                fc_depth = depth_m * rng.uniform(0.02, 0.08)
                
                # Distance from this small crater center (using dx/dy arrays relative to main crater)
                fc_dist = np.sqrt((dx - fc_x)**2 + (dy - fc_y)**2)
                
                # Simple bowl shape for small craters
                fc_mask = fc_dist <= fc_radius
                if fc_mask.any():
                    fc_u = fc_dist[fc_mask] / fc_radius
                    # Simple parabolic bowl
                    crater_delta[fc_mask] -= fc_depth * (1 - fc_u**2)
            
            # Add rock piles (mound-like debris piles)
            num_rock_piles = rng.integers(3, 8)  # Just a few notable ones
            for _ in range(num_rock_piles):
                # Random position on floor
                pile_angle = rng.uniform(0, 2 * np.pi)
                pile_dist = rng.uniform(0, 0.75 * flat_floor_radius.mean() if hasattr(flat_floor_radius, 'mean') else 0.75 * flat_floor_radius)
                
                pile_x = pile_dist * np.cos(pile_angle)
                pile_y = pile_dist * np.sin(pile_angle)
                
                # Larger rock pile size (1.5% to 6% of main crater radius)
                pile_radius = rng.uniform(radius_px_x * 0.015, radius_px_x * 0.06)
                # More prominent heights (4% to 12% of crater depth)
                pile_height = depth_m * rng.uniform(0.04, 0.12)
                
                # Distance from pile center
                pile_dist_field = np.sqrt((dx - pile_x)**2 + (dy - pile_y)**2)
                
                # Cone/mound shape for rock piles (more visible than gaussian)
                pile_mask = pile_dist_field <= pile_radius
                if pile_mask.any():
                    # Conical mound profile - more pronounced than gaussian
                    pile_u = pile_dist_field[pile_mask] / pile_radius
                    pile_profile = (1 - pile_u**1.5)  # Steep mound shape
                    crater_delta[pile_mask] += pile_height * pile_profile

        # Zone 2: Bowl transition (flat_floor_radius < r <= bowl_radius)
        # Rises smoothly from -depth_m to near zero
        bowl_mask = (dist_px_distorted > flat_floor_radius) & (dist_px_distorted <= bowl_radius)
        
        # Add scree (talus) streaks down the bowl and wall areas
        # Create scree field over entire region first
        scree_field = np.zeros_like(crater_delta)
        num_scree = np.random.randint(20, 40)
        
        for _ in range(num_scree):
            scree_angle = np.random.uniform(0, 2 * np.pi)
            scree_width = np.random.uniform(0.015, 0.045)  # Radians - widened for better visibility
            scree_depth = depth_m * np.random.uniform(0.050, 0.110)  # Deeper scree lines
            
            # Angular distance from scree centerline
            angular_dist = np.abs((angle - scree_angle + np.pi) % (2 * np.pi) - np.pi)
            
            # Gaussian falloff in angular direction
            angular_strength = np.exp(-((angular_dist / scree_width) ** 2))
            
            # Apply to scree field
            scree_field += angular_strength * scree_depth
        
        if bowl_mask.any():
            bowl_u = (dist_px_distorted[bowl_mask] - flat_floor_radius[bowl_mask]) / (
                bowl_radius[bowl_mask] - flat_floor_radius[bowl_mask] + 1e-6
            )
            # Bowl curve controlled by exponent: 2.0=parabolic, higher=steeper walls
            # (1 - u)^exponent creates the bowl shape
            crater_delta[bowl_mask] = -depth_m * (1 - bowl_u) ** bowl_exponent
            
            # Apply scree to bowl, modulated by radial position
            # Stronger near top of bowl (steeper slopes), fades toward floor
            scree_modulation = bowl_u ** 0.7  # Gentler falloff so scree is visible even at bottom
            crater_delta[bowl_mask] -= scree_field[bowl_mask] * scree_modulation

        # Zone 3: Inner wall (bowl_radius < r <= inner_radius)
        # Continues from bowl end (at ~0) and stays near baseline
        wall_mask = (dist_px_distorted > bowl_radius) & (dist_px_distorted <= inner_radius)
        if wall_mask.any():
            wall_u = (dist_px_distorted[wall_mask] - bowl_radius[wall_mask]) / (
                inner_radius[wall_mask] - bowl_radius[wall_mask] + 1e-6
            )
            # At bowl_radius (u=0): bowl ends at 0, so wall must start at 0
            # Wall stays near zero (slight dip allowed for terrace effect)
            # Use smooth curve: 0 at u=0, small dip in middle, back to ~0 at u=1
            crater_delta[wall_mask] = -depth_m * 0.01 * wall_u * (1 - wall_u)
            
            # Apply scree to inner wall too - maximum at bottom, fades toward rim
            scree_modulation = (1 - wall_u) ** 0.5  # Strongest at bowl edge, fades toward rim
            crater_delta[wall_mask] -= scree_field[wall_mask] * scree_modulation * 0.8

        # Zone 4: Rim (inner_radius < r <= rim_radius)
        # Rises smoothly from baseline to rim_height peak, then back down to baseline
        # This ensures smooth transition to flat ejecta zone
        rim_mask = (dist_px_distorted > inner_radius) & (dist_px_distorted <= rim_radius)
        if rim_mask.any():
            rim_u = (dist_px_distorted[rim_mask] - inner_radius[rim_mask]) / (
                rim_radius[rim_mask] - inner_radius[rim_mask] + 1e-6
            )
            # At inner_radius (u=0): 0 (continuous with wall)
            # At mid-rim (u~0.5): peak at rim_height
            # At rim_radius (u=1): 0 (continuous with flat ejecta)
            # Use sine curve for smooth 0 → peak → 0 transition
            rim_profile = rim_height * np.sin(rim_u * np.pi) ** 1.5
            crater_delta[rim_mask] = rim_profile * (1 + rim_texture[rim_mask] * 0.15)

        # Ejecta deposition zone - continuous field, not bounded by outer_radius
        # Use outer_radius only as a scaling reference for the depositional extent
        # Calculate reference distance for ejecta extent (but don't use as hard boundary)
        outer_shape = outer_boundary_variation * 0.7 + ejecta_variation * 0.3
        ejecta_reference_radius = radius_px_x * 1.3 * (1.0 + outer_shape * 0.18)

        # Create continuous ejecta deposition field from rim outward
        # No hard mask - smooth continuous falloff over wide zone
        ejecta_zone = dist_px > rim_radius

        # Calculate normalized radial position from rim outward
        # CRITICAL: max extent must be well within bounding box (1.8x) to avoid edge artifacts
        # Set to 1.6x to ensure smooth falloff to zero before box boundary
        max_ejecta_extent = radius_px_x * 1.6
        normalized_ejecta_dist = (dist_px - rim_radius) / (
            max_ejecta_extent - rim_radius + 1e-6
        )
        normalized_ejecta_dist = np.clip(
            normalized_ejecta_dist, 0, 1.5
        )  # Allow overshoot for smooth tail

        # Smooth continuous falloff (no sharp edges)
        # Power law with high exponent ensures it reaches nearly zero before max_ejecta_extent
        base_ejecta_falloff = np.maximum(0, 1.0 - normalized_ejecta_dist**2.5)

        # Add radial streak modulation (ejecta rays as continuous soft fields)
        # Model as smooth angular deposits with wandering centerlines and gradual tapering
        radial_streaks = np.zeros_like(dist_px)
        num_streaks = rng.integers(6, 12)  # More ejecta rays

        # Normalized radial position in ejecta zone (0 at rim, 1 at max extent)
        ejecta_u = np.clip(
            (dist_px - rim_radius) / (max_ejecta_extent - rim_radius + 1e-6), 0, 1.2
        )

        for i in range(num_streaks):
            # Base ray centerline angle
            if rng.random() < 0.7:
                ray_center_angle = impact_angle + rng.uniform(
                    -impact_cone_width / 2, impact_cone_width / 2
                )
            else:
                ray_center_angle = rng.uniform(0, 2 * np.pi)

            # Ray centerline wanders smoothly as function of ejecta_u
            # Low-frequency sinusoidal wander (not jagged)
            wander_freq = rng.uniform(1.5, 3.5)
            wander_amplitude_rad = rng.uniform(0.08, 0.18)  # Radians
            wander_phase = rng.uniform(0, 2 * np.pi)
            ray_centerline_angle = ray_center_angle + wander_amplitude_rad * np.sin(
                wander_freq * np.pi * ejecta_u + wander_phase
            )

            # Ray width as smooth function of ejecta_u
            # Broader near rim, narrowing toward distal edge
            base_width_rad = rng.uniform(0.12, 0.25)  # Radians (~7-14 degrees)
            width_taper = 1.3 - 0.8 * ejecta_u  # Narrows from 1.3× to 0.5× base width
            ray_width_u = base_width_rad * width_taper

            # Angular offset from wandering centerline
            # Wrapped angle difference (handles 0/2π wraparound)
            angular_offset = np.abs(
                (angle - ray_centerline_angle + np.pi) % (2 * np.pi) - np.pi
            )

            # Lateral falloff: soft Gaussian from centerline
            lateral_falloff = np.exp(-((angular_offset / (ray_width_u + 1e-6)) ** 2))

            # Radial strength envelope: strongest in inner-to-mid ejecta, fading toward distal
            # Peak around ejecta_u ~ 0.3-0.5, declining toward both rim and far edge
            radial_peak = rng.uniform(0.3, 0.5)
            radial_width = rng.uniform(0.4, 0.6)
            radial_envelope = np.exp(-(((ejecta_u - radial_peak) / radial_width) ** 2))
            # Also apply overall decay toward far field
            radial_envelope *= 1.0 - 0.6 * ejecta_u

            # Patchiness: longitudinal modulation creates streaks/clumps along ray
            # Multiple frequency components for natural variation
            patchiness = np.ones_like(ejecta_u)
            for pulse_freq in [2, 3, 5]:
                pulse_phase = rng.uniform(0, 2 * np.pi)
                pulse_amp = rng.uniform(0.15, 0.35)
                patchiness += pulse_amp * np.sin(
                    pulse_freq * np.pi * ejecta_u + pulse_phase
                )
            patchiness = np.clip(patchiness / patchiness.max(), 0.3, 1.0)

            # Overall ray strength
            streak_strength = (
                rng.uniform(0.0, 1.0) ** 1.5
            )  # Less aggressive falloff for more visible rays

            # Combine all components into continuous ray field
            ray_intensity = (
                streak_strength * lateral_falloff * radial_envelope * patchiness
            )

            # Add to accumulated streaks (sum, not max)
            radial_streaks += ray_intensity

        radial_streaks = np.clip(radial_streaks, 0, 1)

        # Ejecta concentrated along rays, thin between them
        # Modulate base falloff by ray density for natural variation
        ejecta_deposition = base_ejecta_falloff * (0.1 + 0.9 * radial_streaks)

        # Add small irregular bumps/mounds in ejecta field - concentrated in rays
        ejecta_texture = np.random.normal(0, rim_height * 0.75, crater_delta.shape)  # Increased amplitude
        ejecta_texture = gaussian_filter(ejecta_texture, sigma=3.0)

        # Zone 5: Ejecta blanket (r > rim_radius)
        # Flat terrain with only subtle texture - secondary craters are the main features
        ejecta_active = ejecta_zone & (base_ejecta_falloff > 0.01)
        if ejecta_active.any():
            # No elevated blanket - keep ejecta zone at baseline elevation
            # Only add very subtle texture for slight roughness
            crater_delta[ejecta_active] = ejecta_texture[ejecta_active] * 0.1

        # Add secondary cratering as distinct terrain features AFTER base ejecta
        # Generate stochastic ejecta density field based on rays (not radial distance)
        # Density field independent of distance rings - only angular/ray modulation
        ejecta_density = np.zeros_like(dist_px)
        for ray_angle, ray_width, ray_strength in ejecta_ray_angles:
            angular_dist = np.abs((angle - ray_angle + np.pi) % (2 * np.pi) - np.pi)
            # Angular factor only - no preferred radius
            angular_factor = np.exp(-((angular_dist / (ray_width * 1.8)) ** 2))
            ejecta_density += ray_strength * angular_factor

        # Add base background density (some secondaries everywhere in ejecta)
        ejecta_density += 0.2
        ejecta_density = np.clip(ejecta_density, 0, 1)

        # Create dedicated secondary field
        secondary_field = np.zeros_like(crater_delta)
        num_secondary = rng.integers(20, 35)  # More secondaries spread broadly

        # Calculate crater offset within sub-array (important for edge cases)
        crater_offset_x = crater_px_x - x_min
        crater_offset_y = crater_px_y - y_min

        # Track placed secondaries to prevent overlaps
        placed_secondaries = []  # List of (distance, angle, radius_x) tuples

        for i in range(num_secondary):
            # Sample position stochastically: very wide range, biased by ejecta density only
            # Try multiple positions, pick one with high density
            best_distance = None
            best_angle = None
            best_density = 0
            for attempt in range(5):
                trial_angle = rng.uniform(0, 2 * np.pi)
                # Very wide range: from just outside bowl to well into surrounding terrain
                # No preferred distance - uniform sampling in broad range
                trial_distance = rng.uniform(radius_px_x * 0.85, radius_px_x * 1.6)

                # Sample density at this location
                trial_dx = trial_distance * np.cos(trial_angle)
                trial_dy = trial_distance * np.sin(trial_angle)
                # Use actual crater position in sub-array, not assumed center
                trial_idx_x = int(crater_offset_x + trial_dx)
                trial_idx_y = int(crater_offset_y + trial_dy)
                if (
                    0 <= trial_idx_y < ejecta_density.shape[0]
                    and 0 <= trial_idx_x < ejecta_density.shape[1]
                ):
                    trial_density = ejecta_density[trial_idx_y, trial_idx_x]
                    # Weight by density and a gentle distance factor (not peaked)
                    distance_weight = np.exp(
                        -((trial_distance / (radius_px_x * 2.0)) ** 2)
                    )  # Very broad
                    weighted_density = trial_density * (0.3 + 0.7 * distance_weight)
                    if weighted_density > best_density:
                        best_density = weighted_density
                        best_distance = trial_distance
                        best_angle = trial_angle

            if best_distance is None:
                continue

            # Size and depth vary with distance (farther = smaller, shallower)
            # But not concentrated - gradual declining trend
            distance_factor = np.exp(-((best_distance / (radius_px_x * 1.8)) ** 1.2))
            distance_factor = np.clip(distance_factor, 0.15, 1.0)

            # Larger secondary craters - range from 3% to 12% of main crater radius
            # Use anisotropic radii to match main crater aspect ratio
            sec_radius_x = (
                rng.uniform(radius_px_x * 0.04, radius_px_x * 0.14) * distance_factor  # Slightly larger
            )
            sec_radius_y = sec_radius_x * (radius_px_y / radius_px_x)  # Match aspect ratio
            sec_depth = depth_m * rng.uniform(0.14, 0.32) * distance_factor  # Increased relief
            sec_rim_height = sec_depth * 0.22  # More pronounced rims

            # Check for overlap with existing secondaries
            overlaps = False
            for placed_dist, placed_angle, placed_radius in placed_secondaries:
                # Calculate distance between this secondary and the placed one
                # Convert polar to cartesian for both
                this_x = best_distance * np.cos(best_angle)
                this_y = best_distance * np.sin(best_angle)
                placed_x = placed_dist * np.cos(placed_angle)
                placed_y = placed_dist * np.sin(placed_angle)
                
                # Distance between centers
                center_dist = np.sqrt((this_x - placed_x)**2 + (this_y - placed_y)**2)
                
                # Check if they overlap (with small buffer to ensure separation)
                min_separation = (sec_radius_x + placed_radius) * 1.2  # 20% buffer
                if center_dist < min_separation:
                    overlaps = True
                    break
            
            # Skip this secondary if it overlaps
            if overlaps:
                continue
            
            # Record this secondary as placed
            placed_secondaries.append((best_distance, best_angle, sec_radius_x))

            # Calculate distance from secondary crater center using anisotropic scaling
            sec_dx = dx - best_distance * np.cos(best_angle)
            sec_dy = dy - best_distance * np.sin(best_angle)
            # Normalized distance (corrects for latitude/longitude distortion)
            sec_dist = np.sqrt((sec_dx / sec_radius_x) ** 2 + (sec_dy / sec_radius_y) ** 2) * sec_radius_x

            # Bowl depression
            sec_bowl_mask = sec_dist < sec_radius_x
            if sec_bowl_mask.any():
                sec_progress = sec_dist[sec_bowl_mask] / sec_radius_x
                sec_profile = -sec_depth * (1 - sec_progress**2)
                secondary_field[sec_bowl_mask] = np.minimum(
                    secondary_field[sec_bowl_mask], sec_profile
                )

            # Small rim
            sec_rim_mask = (sec_dist >= sec_radius_x) & (sec_dist < sec_radius_x * 1.2)
            if sec_rim_mask.any():
                rim_progress = (sec_dist[sec_rim_mask] - sec_radius_x) / (
                    sec_radius_x * 0.2
                )
                rim_profile = sec_rim_height * (1 - rim_progress**2)
                secondary_field[sec_rim_mask] = np.maximum(
                    secondary_field[sec_rim_mask], rim_profile
                )

        # Apply secondaries with continuous density-based modulation (not hard mask or radial peak)
        # Use ejecta deposition falloff to modulate strength (natural tapering with ejecta)
        # But no separate radial preference - just follow the ejecta deposition
        secondary_strength = ejecta_density * base_ejecta_falloff * 0.7
        crater_delta += secondary_field * secondary_strength

        # Add concentric ripples/terraces (like slumping in crater walls)
        # Random parameters per crater for variation
        num_ripples = rng.integers(1, 3)  # Just 1-2 subtle terraces
        ripple_amplitude = rng.uniform(0.08, 0.14) * depth_m  # Increased amplitude for better visibility

        # Apply ripples mainly to bowl and wall areas (not flat floor)
        flat_floor_mean = (
            flat_floor_radius.mean()
            if hasattr(flat_floor_radius, "mean")
            else flat_floor_radius
        )
        ripple_mask = dist_px > flat_floor_mean * 0.8

        if ripple_mask.any() and num_ripples > 0:
            # Normalized radial distance for ripple calculation
            ripple_dist = (dist_px[ripple_mask] - flat_floor_mean) / (
                radius_px_x - flat_floor_mean + 1e-6
            )

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
                ripple_contribution = ripple_strength * np.exp(
                    -(((ripple_dist - ripple_center) / ripple_width) ** 2)
                )
                ripple_sum += ripple_contribution

            # Apply ripples as delta
            crater_delta[ripple_mask] += ripple_amplitude * ripple_sum

        # Add multi-scale surface texture variation (scarred, rough terrain)
        # Large-scale scarring (Impact features, major cracks) - increased amplitude
        large_texture = np.random.normal(0, depth_m * 0.12, crater_delta.shape)
        large_texture = gaussian_filter(large_texture, sigma=12.0)

        # Medium-scale roughness (Secondary impacts, erosion) - increased amplitude
        medium_texture = np.random.normal(0, depth_m * 0.08, crater_delta.shape)
        medium_texture = gaussian_filter(medium_texture, sigma=5.0)

        # Fine-scale detail (Surface irregularities) - increased amplitude
        fine_texture = np.random.normal(0, depth_m * 0.04, crater_delta.shape)
        fine_texture = gaussian_filter(fine_texture, sigma=1.5)

        # Combine textures with distance-based weighting
        combined_texture = large_texture + medium_texture + fine_texture

        # Apply texture to entire crater (including floor for rough lava base)
        crater_interior_mask = dist_px_distorted <= rim_radius
        crater_delta[crater_interior_mask] += combined_texture[crater_interior_mask]

        # Add wall slump scars (collapsed material on crater walls)
        num_slumps = rng.integers(2, 5)
        wall_and_bowl_mask = (dist_px_distorted > flat_floor_mean * 0.6) & (dist_px_distorted <= rim_radius)

        for i in range(num_slumps):
            slump_angle = rng.uniform(0, 2 * np.pi)
            slump_width = rng.uniform(np.pi / 8, np.pi / 4)
            slump_depth = rng.uniform(0.035, 0.070) * depth_m  # Increased amplitude

            angular_dist = np.abs((angle - slump_angle + np.pi) % (2 * np.pi) - np.pi)
            slump_mask = (angular_dist < slump_width) & wall_and_bowl_mask

            if slump_mask.any():
                # Radial distance for falloff
                radial_progress = (dist_px_distorted[slump_mask] - flat_floor_mean) / (
                    radius_px_x - flat_floor_mean + 1e-6
                )
                # Angular falloff
                angular_falloff = 1.0 - (angular_dist[slump_mask] / slump_width) ** 2
                # Create slump depression with some texture
                slump_pattern = (
                    -slump_depth
                    * angular_falloff
                    * (0.8 + 0.2 * np.sin(radial_progress * 8 * np.pi))
                )
                crater_delta[slump_mask] += slump_pattern

        # Add scattered small pockmarks across crater surface
        num_pockmarks = rng.integers(15, 30)
        for i in range(num_pockmarks):
            pock_angle = rng.uniform(0, 2 * np.pi)
            pock_distance = rng.uniform(0.2, 1.0) * radius_px_x
            pock_x = pock_distance * np.cos(pock_angle)
            pock_y = pock_distance * np.sin(pock_angle)

            pock_radius = rng.uniform(0.020, 0.055) * radius_px_x  # Larger for visibility
            pock_depth = rng.uniform(0.025, 0.065) * depth_m  # Increased amplitude

            pock_dist = np.sqrt((dx - pock_x) ** 2 + (dy - pock_y) ** 2)
            pock_mask = (pock_dist < pock_radius * 1.5) & crater_interior_mask

            if pock_mask.any():
                pock_profile = -pock_depth * np.exp(
                    -((pock_dist[pock_mask] / pock_radius) ** 2.5)
                )
                crater_delta[pock_mask] += pock_profile

        # Add radial scrape marks on inner wall (simple radial lines from impact)
        # Subtle texture that looks like material scraped radially during formation
        num_scrapes = rng.integers(80, 140)  # More scrapes for denser texture

        # Get radii for wall zone
        bowl_mean = bowl_radius.mean() if hasattr(bowl_radius, "mean") else bowl_radius
        inner_mean = (
            inner_radius.mean() if hasattr(inner_radius, "mean") else inner_radius
        )
        rim_mean = rim_radius.mean() if hasattr(rim_radius, "mean") else rim_radius

        for i in range(num_scrapes):
            scrape_angle = rng.uniform(0, 2 * np.pi)
            scrape_width = rng.uniform(
                0.010, 0.025
            )  # Widened for better visibility (radians)
            scrape_depth = rng.uniform(0.045, 0.110) * depth_m  # Increased amplitude for visibility

            # Angular distance from scrape centerline
            angular_diff = np.abs((angle - scrape_angle + np.pi) % (2 * np.pi) - np.pi)

            # Scrape extends along wall (bowl edge to upper wall)
            scrape_start = bowl_mean * 1.1
            scrape_end = rim_mean * 0.95
            scrape_mask = (
                (angular_diff < scrape_width)
                & (dist_px >= scrape_start)
                & (dist_px <= scrape_end)
            )

            if not scrape_mask.any():
                continue

            # Simple linear lateral profile (narrow line)
            lateral_u = angular_diff[scrape_mask] / (scrape_width + 1e-6)
            lateral_profile = np.maximum(0, 1.0 - lateral_u)

            # Depth varies along length (some variation)
            radial_u = (dist_px[scrape_mask] - scrape_start) / (
                scrape_end - scrape_start + 1e-6
            )
            depth_variation = 0.7 + 0.3 * np.sin(radial_u * np.pi * rng.uniform(2, 5))

            # Apply scrape
            scrape_profile = -scrape_depth * lateral_profile * depth_variation
            crater_delta[scrape_mask] += scrape_profile

        # Add extra rim surface irregularities (bumps and scars)
        rim_surface_mask = (dist_px_distorted > inner_radius) & (dist_px_distorted <= rim_radius)
        if rim_surface_mask.any():
            rim_bumps = np.random.normal(0, rim_height * 0.50, crater_delta.shape)  # Increased amplitude
            rim_bumps = gaussian_filter(rim_bumps, sigma=1.5)
            crater_delta[rim_surface_mask] += rim_bumps[rim_surface_mask]

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

        # Apply crater to DEM using smooth influence mask (single additive application)
        # This eliminates seams from mixed assignment styles
        # Crater interior (bowl, walls, rim) applied fully
        crater_interior = dist_px <= rim_radius

        # Beyond rim: smooth continuous falloff using base_ejecta_falloff
        # Create unified influence mask across entire crater region
        influence_mask = np.ones_like(dist_px)

        # Interior gets full influence
        influence_mask[crater_interior] = 1.0

        # Ejecta zone gets smooth falloff
        ejecta_influence_zone = (dist_px > rim_radius) & (base_ejecta_falloff > 0.01)
        if ejecta_influence_zone.any():
            influence_mask[ejecta_influence_zone] = base_ejecta_falloff[
                ejecta_influence_zone
            ]

        # Outside ejecta zone gets zero influence
        far_field = dist_px > rim_radius
        if far_field.any():
            influence_mask[far_field] = np.where(
                base_ejecta_falloff[far_field] > 0.01,
                base_ejecta_falloff[far_field],
                0.0,
            )

        # Single additive application - no mixed assignment styles
        dem_region += crater_delta * influence_mask

        # Insert processed region back into full DEM
        dem_cratered[y_min:y_max, x_min:x_max] = dem_region

        # Generate polygon metadata for water layer modification
        # Disruption zone: circular polygon at outer radius (where impact disrupts existing water)
        disruption_radius_deg_x = (radius_km * 1000 * 1.3) / (
            111320 * np.cos(np.radians(crater_lat))
        )
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
            flat_floor_mean = (
                flat_floor_radius.mean()
                if hasattr(flat_floor_radius, "mean")
                else flat_floor_radius
            )
            bowl_mean = (
                bowl_radius.mean() if hasattr(bowl_radius, "mean") else bowl_radius
            )
            lava_radius_px_base = flat_floor_mean + fill_percentage * (
                bowl_mean - flat_floor_mean
            )

            # Convert to geographic coordinates
            lava_radius_m = (
                lava_radius_px_base * abs(pixel_size_x) * meters_per_degree_lon
            )
            lava_radius_deg_lon = lava_radius_m / meters_per_degree_lon
            lava_radius_deg_lat = lava_radius_m / meters_per_degree_lat

            num_edge_points = 120
            lava_edge_angles = np.linspace(
                0, 2 * np.pi, num_edge_points, endpoint=False
            )
            lava_edge_x = []
            lava_edge_y = []

            # Generate irregular edge based on lava radius and angular variation
            for angle in lava_edge_angles:
                # Add angular irregularity (8-12 lobes plus some randomness)
                angular_var = 0.0
                num_lobes = 8
                angular_var += 0.12 * np.sin(
                    angle * num_lobes + rng.uniform(0, 2 * np.pi)
                )
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
        crater_metadata.append(
            {
                "disruption_zone": disruption_polygon,
                "lava_polygon": lava_polygon,
                "center": Point(crater_lon, crater_lat),
                "remove_overlapping_water": crater_cfg.get(
                    "remove_overlapping_water", True
                ),
                "label": crater_cfg.get("label"),
            }
        )

    return dem_cratered, crater_metadata


def _render_procedural_lava(fig, ax, crater_metadata, bounds, map_config=None):
    """
    Render crater lava pools as procedural molten surfaces.
    
    Creates fiery textured surfaces with heat fields, cooling edges,
    fracture networks, and irregular temperature variation.
    """
    if not crater_metadata:
        return
    
    # Use original DEM bounds (not cropped axis limits) for coordinate transformation
    # This ensures lava polygons render at the correct positions
    minx, miny, maxx, maxy = bounds
    
    # Resolution for rasterization (higher = more detail)
    render_width = 2048
    # Account for aspect ratio in height calculation
    data_width = maxx - minx
    data_height = maxy - miny
    render_height = int(render_width * (data_height / data_width))
    
    # Transform from data coordinates to pixel coordinates
    def lonlat_to_pixel(lon, lat):
        px = (lon - minx) / (maxx - minx) * render_width
        py = (1 - (lat - miny) / (maxy - miny)) * render_height
        return px, py
    
    # Lava color palette: dark brown-red → deep red → red-orange → bright orange → limited yellow
    lava_colors = [
        (0.00, (0.12, 0.05, 0.03)),  # Very dark brown-red (solidified crust)
        (0.15, (0.20, 0.06, 0.04)),  # Dark maroon
        (0.30, (0.35, 0.08, 0.04)),  # Deep brownish-red
        (0.45, (0.55, 0.12, 0.05)),  # Deep red
        (0.60, (0.75, 0.20, 0.08)),  # Red-orange
        (0.75, (0.90, 0.35, 0.12)),  # Bright red-orange
        (0.88, (1.00, 0.55, 0.18)),  # Bright orange
        (0.96, (1.00, 0.75, 0.30)),  # Yellow-orange (limited)
        (1.00, (1.00, 0.90, 0.60)),  # Yellow-white (very hot, minimal)
    ]
    
    # Process each lava pool
    for crater_meta in crater_metadata:
        lava_poly = crater_meta.get("lava_polygon")
        if lava_poly is None or lava_poly.is_empty:
            continue
        
        # Get polygon bounds
        poly_minx, poly_miny, poly_maxx, poly_maxy = lava_poly.bounds
        
        # Skip if outside view (using actual axis limits which may be cropped)
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        if poly_maxx < xlim[0] or poly_minx > xlim[1] or poly_maxy < ylim[0] or poly_miny > ylim[1]:
            continue
        
        # Convert polygon to pixel coordinates
        coords = np.array(lava_poly.exterior.coords)
        pixel_coords = np.array([lonlat_to_pixel(lon, lat) for lon, lat in coords])
        
        # Create mask for this lava pool
        from PIL import Image, ImageDraw
        mask_img = Image.new('L', (render_width, render_height), 0)
        draw = ImageDraw.Draw(mask_img)
        draw.polygon([tuple(p) for p in pixel_coords], fill=255)
        mask = np.array(mask_img) > 128
        
        if not mask.any():
            continue
        
        # Get bounding box in pixel space
        ys, xs = np.where(mask)
        if len(xs) == 0:
            continue
        
        x0, x1 = xs.min(), xs.max() + 1
        y0, y1 = ys.min(), ys.max() + 1
        local_mask = mask[y0:y1, x0:x1]
        h, w = local_mask.shape
        
        # Generate heat field
        # 1. Broad low-frequency base (overall temperature variation)
        heat_base = np.random.normal(0.65, 0.15, (h//4, w//4))  # Slightly hotter base
        heat_base = gaussian_filter(heat_base, sigma=2.0)
        from scipy.ndimage import zoom
        heat_base = zoom(heat_base, (h / heat_base.shape[0], w / heat_base.shape[1]), order=1)
        heat_base = np.clip(heat_base, 0, 1)
        
        # 2. Medium-frequency mottled texture
        heat_medium = np.random.normal(0, 0.12, (h//2, w//2))
        heat_medium = gaussian_filter(heat_medium, sigma=1.0)
        heat_medium = zoom(heat_medium, (h / heat_medium.shape[0], w / heat_medium.shape[1]), order=1)
        
        # 3. Fine texture for detail
        heat_fine = np.random.normal(0, 0.06, (h, w))
        heat_fine = gaussian_filter(heat_fine, sigma=0.5)
        
        # Combine heat components
        heat = heat_base + heat_medium + heat_fine
        heat = np.clip(heat, 0, 1)
        
        # 4. Edge cooling - margins are darker/solidified
        from scipy.ndimage import distance_transform_edt
        dist = distance_transform_edt(local_mask)
        max_dist = dist.max()
        if max_dist > 0:
            edge_factor = np.clip(dist / (max_dist * 0.25), 0, 1)  # Less edge cooling (25% vs 30%)
            edge_factor = edge_factor ** 0.7  # Nonlinear falloff
            heat = heat * (0.25 + 0.75 * edge_factor)  # Less severe cooling
        
        # 5. Organic crust/fracture patterns using multi-scale noise
        # Create natural-looking cooled patches and cracks without geometric lines
        
        # Crust pattern - broad cooled regions
        crust_noise = np.random.normal(0, 0.2, (max(1, h//3), max(1, w//3)))
        crust_noise = gaussian_filter(crust_noise, sigma=1.5)
        from scipy.ndimage import zoom
        crust_noise = zoom(crust_noise, (h / crust_noise.shape[0], w / crust_noise.shape[1]), order=1)
        crust_noise = np.clip(crust_noise, -0.3, 0.3)
        
        # Fine cracks - high-frequency detail for fracture network
        crack_noise = np.random.normal(0, 0.15, (h, w))
        crack_noise = gaussian_filter(crack_noise, sigma=0.3)
        
        # Combine: broader crust cooling + fine cracks
        crust_modulation = crust_noise + crack_noise * 0.5
        
        # Apply crust effect: some areas cooler (dark), some hotter along cracks
        # Threshold to create distinct hot/cool regions without hard edges
        crust_modulation = gaussian_filter(crust_modulation, sigma=1.0)  # Smooth transitions
        heat += crust_modulation
        
        # Add localized bright hot streaks for visual interest
        num_hot_streaks = np.random.randint(3, 7)
        for _ in range(num_hot_streaks):
            streak_x = np.random.uniform(0, w)
            streak_y = np.random.uniform(0, h)
            streak_radius = np.random.uniform(min(h, w) * 0.08, min(h, w) * 0.18)
            streak_intensity = np.random.uniform(0.15, 0.30)
            
            yy_local, xx_local = np.ogrid[:h, :w]
            dist_to_streak = np.sqrt((xx_local - streak_x)**2 + (yy_local - streak_y)**2)
            hot_streak = streak_intensity * np.exp(-((dist_to_streak / streak_radius) ** 2))
            heat += hot_streak
        
        # 6. Optional swirl/flow distortion for fluidity
        if np.random.random() < 0.7:  # 70% chance of flow
            flow_angle = np.random.uniform(0, 2 * np.pi)
            yy, xx = np.meshgrid(np.arange(h), np.arange(w), indexing='ij')
            # Create flow field
            flow_x = np.sin(yy / (h / 6) + flow_angle) * 2.0
            flow_y = np.cos(xx / (w / 6) + flow_angle) * 2.0
            
            # Warp heat field slightly
            from scipy.ndimage import map_coordinates
            coords_y = np.clip(yy + flow_y, 0, h - 1)
            coords_x = np.clip(xx + flow_x, 0, w - 1)
            heat_warped = map_coordinates(heat, [coords_y, coords_x], order=1)
            heat = heat * 0.6 + heat_warped * 0.4
        
        # Clip and normalize heat
        heat = np.clip(heat, 0, 1)
        
        # Apply unsharp masking for detail enhancement (same as hillshade)
        if map_config:
            hillshade_cfg = map_config.get("hillshade", {})
            unsharp_radius = hillshade_cfg.get("unsharp_radius", 0.0)
            unsharp_amount = hillshade_cfg.get("unsharp_amount", 0.0)
            if unsharp_radius > 0 and unsharp_amount > 0:
                heat_blurred = gaussian_filter(heat, sigma=unsharp_radius)
                heat = heat + unsharp_amount * (heat - heat_blurred)
                heat = np.clip(heat, 0, 1)
        
        # Convert heat to RGB using lava palette
        lava_r = np.interp(heat.ravel(), [c[0] for c in lava_colors], [c[1][0] for c in lava_colors]).reshape(h, w)
        lava_g = np.interp(heat.ravel(), [c[0] for c in lava_colors], [c[1][1] for c in lava_colors]).reshape(h, w)
        lava_b = np.interp(heat.ravel(), [c[0] for c in lava_colors], [c[1][2] for c in lava_colors]).reshape(h, w)
        
        # Emissive brightening in hotter zones (moderate boost)
        emissive = np.clip((heat - 0.75) / 0.20, 0, 1) * 0.20  # Starts at 75% heat, 20% boost
        lava_r = np.clip(lava_r + emissive, 0, 1)
        lava_g = np.clip(lava_g + emissive, 0, 1)
        lava_b = np.clip(lava_b + emissive, 0, 1)
        
        # Stack into RGBA
        lava_rgba = np.dstack([lava_r, lava_g, lava_b, local_mask.astype(float)])
        
        # Convert back to data coordinates using original DEM bounds
        extent = [
            minx + (x0 / render_width) * (maxx - minx),
            minx + (x1 / render_width) * (maxx - minx),
            miny + ((render_height - y1) / render_height) * (maxy - miny),
            miny + ((render_height - y0) / render_height) * (maxy - miny),
        ]
        
        # Overlay lava on axes - use aspect="auto" to respect map extent like DEM/hillshade layers
        ax.imshow(lava_rgba, extent=extent, origin='upper', zorder=150, interpolation='bilinear', aspect='auto')


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
                water_tone[valid_blur] = (
                    blurred_shade[valid_blur] / blurred_weight[valid_blur]
                )

                water_tone = 0.5 + (water_tone - 0.5) * contrast
                water_tone = np.clip(water_tone + bias, 0.0, 1.0).astype(np.float32)

                water_valid = (blurred_weight > 0.002).astype(np.uint8)

                terrain_visible = terrain_cfg.get("visible", False)
                if terrain_visible:
                    elev_percentiles = terrain_cfg.get("percentiles", [2, 98])
                    stretch = terrain_cfg.get("stretch", "linear")
                    stretch_exponent = terrain_cfg.get("stretch_exponent", 1.0)
                    # Use dem_resampled (original terrain) for colors if you want craters to show
                    # only in shading/relief. Use dem_smoothed (cratered terrain) if you want
                    # crater depths to affect both shading AND hypsometric colors.
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
                if crater_meta.get("remove_overlapping_water", True):
                    disruption_zone = crater_meta["disruption_zone"]
                    # Filter out features that intersect the disruption zone
                    if not gdf.empty:
                        gdf = gdf[~gdf.intersects(disruption_zone)]

            # Add lava lake polygons to water/ocean layers (not waterways)
            # NOTE: Lava is now rendered procedurally via _render_procedural_lava()
            # Disabled this section to prevent double-rendering
            if (
                False  # DISABLED
                and layer_cfg["layer"] in ["water", "ocean"]
                and layer_cfg["geometry_type"] == "Polygon"
            ):
                lava_features = []
                for crater_meta in crater_metadata:
                    if crater_meta["lava_polygon"] is not None:
                        lava_features.append({"geometry": crater_meta["lava_polygon"]})

                if lava_features:
                    # Create GeoDataFrame for lava lakes with same CRS as water layer
                    lava_gdf = gpd.GeoDataFrame(
                        lava_features, crs=gdf.crs if not gdf.empty else "EPSG:4326"
                    )
                    # Concatenate with existing water features
                    gdf = gpd.GeoDataFrame(
                        pd.concat([gdf, lava_gdf], ignore_index=True),
                        crs=gdf.crs if not gdf.empty else lava_gdf.crs,
                    )

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

    # Render procedural lava pools (after all vector layers, before labels)
    if crater_metadata:
        _render_procedural_lava(fig, ax, crater_metadata, (minx, miny, maxx, maxy), map_config=mcfg)

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
            label = crater_meta.get("label")
            if label:
                center = crater_meta["center"]
                # Draw text with white fill and black outline for high visibility
                ax.text(
                    center.x,
                    center.y,
                    str(label),
                    ha="center",
                    va="center",
                    fontsize=14,
                    fontweight="bold",
                    color="white",
                    zorder=200,
                    bbox=dict(
                        boxstyle="circle,pad=0.3",
                        facecolor="black",
                        edgecolor="white",
                        linewidth=2,
                        alpha=0.8,
                    ),
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
