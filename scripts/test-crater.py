#!/usr/bin/env python3
"""
Fast crater development tool - iterate on crater appearance in seconds.

Usage:
    python scripts/test-crater.py  # Auto-scaled depth based on radius
    python scripts/test-crater.py --radius 4.0 --lava 200
    python scripts/test-crater.py --radius 2.0 --depth 300  # Override depth
    python scripts/test-crater.py --seed 42
"""

import argparse
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPLPolygon
from matplotlib.colors import LightSource
from matplotlib.widgets import Slider, Button
from scipy.ndimage import gaussian_filter
import sys
import os
import importlib.util

# Import the actual crater function to guarantee 100% parity
# generate-map.py has a hyphen, so we can't use regular import
script_dir = os.path.dirname(os.path.abspath(__file__))
generate_map_path = os.path.join(script_dir, "generate-map.py")
spec = importlib.util.spec_from_file_location("generate_map", generate_map_path)
generate_map = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate_map)
_apply_craters_to_dem = generate_map._apply_craters_to_dem


def create_synthetic_dem(size=1000, base_elevation=500.0, noise_scale=5.0):
    """Create a small synthetic DEM with gentle terrain variation."""
    dem = np.full((size, size), base_elevation, dtype=np.float32)

    # Add some gentle rolling hills
    x = np.linspace(0, 4 * np.pi, size)
    y = np.linspace(0, 4 * np.pi, size)
    xx, yy = np.meshgrid(x, y)
    terrain = 20 * np.sin(xx / 2) * np.cos(yy / 2)
    terrain += 10 * np.sin(xx) * np.sin(yy)

    # Add random noise
    noise = np.random.normal(0, noise_scale, (size, size))
    noise = gaussian_filter(noise, sigma=2.0)

    dem += terrain + noise
    return dem


def simple_hillshade(dem, azimuth=315, altitude=45):
    """Create a simple hillshade from DEM."""
    ls = LightSource(azdeg=azimuth, altdeg=altitude)
    hillshade = ls.hillshade(dem, vert_exag=3.0, dx=30, dy=30)
    return hillshade


def render_crater_interactive(
    base_dem,
    bounds_tuple,
    pixel_size_x,
    pixel_size_y,
    initial_radius=3.0,
    initial_depth=None,
    initial_lava=0.0,
    initial_rim=0.15,
    initial_flat_floor=0.35,
    initial_bowl_exp=1.0,
):
    """Interactive crater renderer with sliders for real-time adjustment."""

    # Auto-calculate depth from radius if not provided
    if initial_depth is None:
        initial_depth = initial_radius * 1000 * 0.8  # 80% of radius in meters

    # Ensure initial lava doesn't exceed depth
    initial_lava = min(initial_lava, initial_depth)

    fig = plt.figure(figsize=(16, 10))

    # Create axis for hillshade+lava display
    ax_main = plt.subplot2grid((12, 2), (0, 0), colspan=2, rowspan=8)

    # Create axes for sliders (6 sliders total)
    ax_radius = plt.subplot2grid((12, 2), (8, 0), colspan=2)
    ax_depth = plt.subplot2grid((12, 2), (9, 0), colspan=1)
    ax_lava = plt.subplot2grid((12, 2), (9, 1), colspan=1)
    ax_rim = plt.subplot2grid((12, 2), (10, 0), colspan=1)
    ax_flat_floor = plt.subplot2grid((12, 2), (10, 1), colspan=1)
    ax_bowl_exp = plt.subplot2grid((12, 2), (11, 0), colspan=2)

    # Initial crater parameters
    crater_params = {
        "radius": initial_radius,
        "depth": initial_depth,
        "lava": initial_lava,
        "rim": initial_rim,
        "flat_floor": initial_flat_floor,
        "bowl_exp": initial_bowl_exp,
    }

    # Store plot elements
    plot_state = {"im": None, "poly_patch": None}

    # Extract bounds for coordinate conversion
    west, south, east, north = bounds_tuple
    dem_height, dem_width = base_dem.shape

    def lonlat_to_pixel(lon, lat):
        """Convert lon/lat coordinates to pixel coordinates."""
        # Map lon/lat to pixel space
        px = (lon - west) / (east - west) * dem_width
        py = (north - lat) / (north - south) * dem_height
        return px, py

    def apply_and_render(radius, depth, lava, rim, flat_floor, bowl_exp):
        """Apply crater with given parameters and render."""
        crater_config = {
            "x": 0.5,
            "y": 0.5,
            "radius_km": radius,
            "depth_m": None,  # Use auto-calculation from generate-map.py
            "rim_height_ratio": rim,
            "lava_level_m": lava,
            "flat_floor_ratio": flat_floor,
            "bowl_exponent": bowl_exp,
            "remove_overlapping_water": False,
        }

        # Apply crater to a fresh copy of base DEM
        dem_copy = base_dem.copy()
        dem_with_crater, crater_metadata = _apply_craters_to_dem(
            dem_copy, [crater_config], bounds_tuple, pixel_size_x, pixel_size_y
        )

        # Generate hillshade
        hillshade = simple_hillshade(dem_with_crater)

        # Clear and redraw
        ax_main.clear()
        plot_state["im"] = ax_main.imshow(
            hillshade, cmap="gray", interpolation="bilinear"
        )

        # Draw lava polygon if present
        if crater_metadata and len(crater_metadata) > 0:
            meta = crater_metadata[0]
            if "lava_polygon" in meta and meta["lava_polygon"] is not None:
                lava_poly = meta["lava_polygon"]
                coords = np.array(lava_poly.exterior.coords)

                # Properly convert lat/lon to pixel coordinates using bounds
                pixel_coords = np.zeros_like(coords)
                for i, (lon, lat) in enumerate(coords):
                    px, py = lonlat_to_pixel(lon, lat)
                    pixel_coords[i] = [px, py]

                # Draw lava with orange color and transparency
                poly_patch = MPLPolygon(
                    pixel_coords,
                    facecolor="orange",
                    edgecolor="darkorange",
                    alpha=0.7,
                    linewidth=2,
                )
                ax_main.add_patch(poly_patch)
                plot_state["poly_patch"] = poly_patch

        ax_main.set_title(
            f"Crater: {radius:.1f}km × {depth:.0f}m deep | Lava: {lava:.0f}m | Rim: {rim:.2f} | Floor: {flat_floor:.2f} | Bowl exp: {bowl_exp:.1f}",
            fontsize=11,
            fontweight="bold",
        )
        ax_main.axis("off")
        fig.canvas.draw_idle()

    # Create sliders
    radius_slider = Slider(
        ax_radius, "Radius (km)", 0.5, 10.0, valinit=initial_radius, valstep=0.1
    )
    depth_slider = Slider(
        ax_depth, "Depth (m)", 50, 2500, valinit=initial_depth, valstep=10
    )
    lava_slider = Slider(ax_lava, "Lava (m)", 0, 2500, valinit=initial_lava, valstep=10)
    rim_slider = Slider(
        ax_rim, "Rim Height", 0.0, 0.30, valinit=initial_rim, valstep=0.01
    )
    flat_floor_slider = Slider(
        ax_flat_floor, "Flat Floor", 0.0, 0.80, valinit=initial_flat_floor, valstep=0.01
    )
    bowl_exp_slider = Slider(
        ax_bowl_exp, "Bowl Exponent", 1.0, 5.0, valinit=initial_bowl_exp, valstep=0.1
    )

    # Update function when sliders change
    def update(val):
        radius = radius_slider.val
        depth = depth_slider.val
        lava = min(lava_slider.val, depth)  # Lava can't exceed depth
        rim = rim_slider.val
        flat_floor = flat_floor_slider.val
        bowl_exp = bowl_exp_slider.val

        # Update lava slider range if depth changed
        if depth != crater_params["depth"]:
            lava_slider.valmax = depth
            ax_lava.set_xlim(0, depth)

        crater_params["radius"] = radius
        crater_params["depth"] = depth
        crater_params["lava"] = lava
        crater_params["rim"] = rim
        crater_params["flat_floor"] = flat_floor
        crater_params["bowl_exp"] = bowl_exp

        apply_and_render(radius, depth, lava, rim, flat_floor, bowl_exp)

    radius_slider.on_changed(update)
    depth_slider.on_changed(update)
    lava_slider.on_changed(update)
    rim_slider.on_changed(update)
    flat_floor_slider.on_changed(update)
    bowl_exp_slider.on_changed(update)

    # Initial render
    apply_and_render(initial_radius, initial_depth, initial_lava, initial_rim, initial_flat_floor, initial_bowl_exp)

    plt.tight_layout()
    plt.show()


def render_crater(dem, crater_metadata, title="Crater Test", bounds_tuple=None):
    """Render crater with hillshade and lava overlay (static view)."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7))

    # Left: Hillshade only (shows all terrain detail)
    hillshade = simple_hillshade(dem)
    ax1.imshow(hillshade, cmap="gray", interpolation="bilinear")
    ax1.set_title("Hillshade (shows floor texture)")
    ax1.axis("off")

    # Right: Hillshade + lava overlay (simulates final appearance)
    ax2.imshow(hillshade, cmap="gray", interpolation="bilinear")

    # Draw lava polygon if present
    if crater_metadata and len(crater_metadata) > 0:
        meta = crater_metadata[0]
        if "lava_polygon" in meta and meta["lava_polygon"] is not None:
            lava_poly = meta["lava_polygon"]
            coords = np.array(lava_poly.exterior.coords)

            # Properly convert lat/lon to pixel coordinates if bounds provided
            if bounds_tuple is not None:
                west, south, east, north = bounds_tuple
                dem_height, dem_width = dem.shape

                pixel_coords = np.zeros_like(coords)
                for i, (lon, lat) in enumerate(coords):
                    px = (lon - west) / (east - west) * dem_width
                    py = (north - lat) / (north - south) * dem_height
                    pixel_coords[i] = [px, py]
            else:
                # Fallback to old method
                center_y, center_x = dem.shape[0] // 2, dem.shape[1] // 2
                pixel_coords = coords.copy()
                pixel_coords[:, 0] = center_x + (coords[:, 0] - coords[0, 0]) * 30000
                pixel_coords[:, 1] = center_y - (coords[:, 1] - coords[0, 1]) * 30000

            # Draw lava with orange color and transparency
            poly_patch = MPLPolygon(
                pixel_coords,
                facecolor="orange",
                edgecolor="darkorange",
                alpha=0.7,
                linewidth=2,
            )
            ax2.add_patch(poly_patch)

    ax2.set_title("Hillshade + Lava Overlay")
    ax2.axis("off")

    plt.suptitle(title, fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.show()


def main():
    parser = argparse.ArgumentParser(description="Fast crater development tool")
    parser.add_argument(
        "--radius", type=float, default=3.0, help="Crater radius in km (default: 3.0)"
    )
    parser.add_argument(
        "--depth",
        type=float,
        default=None,
        help="Crater depth in meters (default: auto-scaled to 80%% of radius)",
    )
    parser.add_argument(
        "--lava",
        type=float,
        default=0.0,
        help="Lava level in meters (0=empty, depth=full) (default: 0)",
    )
    parser.add_argument(
        "--rim-height",
        type=float,
        default=0.15,
        help="Rim height ratio (default: 0.15)",
    )
    parser.add_argument(
        "--flat-floor",
        type=float,
        default=0.35,
        help="Flat floor ratio (0.0-0.65, default: 0.35)",
    )
    parser.add_argument(
        "--bowl-exp",
        type=float,
        default=1.0,
        help="Bowl exponent (1.0-5.0, 1.0=linear, 2.0=parabolic, default: 1.0)",
    )
    parser.add_argument(
        "--seed", type=int, default=None, help="Random seed for reproducibility"
    )
    parser.add_argument(
        "--size", type=int, default=1000, help="DEM size in pixels (default: 1000)"
    )
    parser.add_argument(
        "--base-elev",
        type=float,
        default=500.0,
        help="Base terrain elevation (default: 500m)",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Interactive mode with sliders (default)",
    )
    parser.add_argument(
        "--static", "-s", action="store_true", help="Static mode (no sliders)"
    )

    args = parser.parse_args()

    # Default to interactive unless --static specified
    interactive_mode = not args.static

    # Set random seed if specified
    if args.seed is not None:
        np.random.seed(args.seed)

    print(f"Creating {args.size}×{args.size} synthetic DEM...")
    dem = create_synthetic_dem(args.size, args.base_elev)

    # Calculate bounds for the DEM (approximate)
    # Using Edmonton-ish lat/lon
    lat = 53.5
    lon = -113.5

    # Rough calculation: DEM extent in degrees
    # Assuming ~30m pixel resolution
    pixel_res_m = 30.0
    dem_width_m = args.size * pixel_res_m

    from math import cos, radians

    meters_per_deg_lon = 111320 * cos(radians(lat))
    meters_per_deg_lat = 111320

    width_deg = dem_width_m / meters_per_deg_lon
    height_deg = dem_width_m / meters_per_deg_lat

    bounds = {
        "west": lon,
        "east": lon + width_deg,
        "north": lat + height_deg / 2,
        "south": lat - height_deg / 2,
    }

    pixel_size_x = width_deg / args.size
    pixel_size_y = -height_deg / args.size  # Negative for north-up

    bounds_tuple = (bounds["west"], bounds["south"], bounds["east"], bounds["north"])

    if interactive_mode:
        print(f"\n🎛️  INTERACTIVE MODE")
        print(f"   Use sliders to adjust crater parameters in real-time!")
        depth_str = f"{args.depth}m" if args.depth else "auto"
        print(
            f"   Initial: {args.radius}km radius, {depth_str} depth, {args.lava}m lava"
        )
        print(f"   Close window when done.\n")

        render_crater_interactive(
            dem,
            bounds_tuple,
            pixel_size_x,
            pixel_size_y,
            initial_radius=args.radius,
            initial_depth=args.depth,
            initial_lava=args.lava,
            initial_rim=args.rim_height,
            initial_flat_floor=args.flat_floor,
            initial_bowl_exp=args.bowl_exp,
        )
    else:
        # Static mode
        crater_config = {
            "x": 0.5,
            "y": 0.5,
            "radius_km": args.radius,
            "depth_m": args.depth,
            "rim_height_ratio": args.rim_height,
            "lava_level_m": args.lava,
            "remove_overlapping_water": False,
        }

        depth_str = f"{args.depth}m" if args.depth is not None else "auto"
        print(
            f"Applying crater: {args.radius}km radius, {depth_str} depth, {args.lava}m lava..."
        )
        print(f"  (This uses the REAL crater function from generate-map.py)")

        # Apply crater using the actual production function
        dem_with_crater, crater_metadata = _apply_craters_to_dem(
            dem, [crater_config], bounds_tuple, pixel_size_x, pixel_size_y
        )

        print(f"Generated crater with {len(crater_metadata)} metadata entries")
        if crater_metadata and "lava_polygon" in crater_metadata[0]:
            lava_poly = crater_metadata[0]["lava_polygon"]
            if lava_poly:
                print(f"  Lava polygon: {len(list(lava_poly.exterior.coords))} points")

        # Render
        title = f"Crater: {args.radius}km × {args.depth}m deep, {args.lava}m lava"
        if args.seed is not None:
            title += f" (seed={args.seed})"

        render_crater(dem_with_crater, crater_metadata, title, bounds_tuple)

    print("\nUsage tips:")
    if interactive_mode:
        print("  - Drag sliders to adjust parameters in real-time")
        print("  - Use --static for non-interactive mode")
    else:
        print("  - Use --interactive (or -i) for real-time sliders")
        print("  - Use --seed for reproducible random features")
    print("\nExample commands:")
    print("  python scripts/test-crater.py  # Interactive mode (auto-scaled depth)")
    print("  python scripts/test-crater.py --radius 5.0  # Larger crater, auto-scaled")
    print("  python scripts/test-crater.py --radius 2.0 --depth 300  # Override depth")
    print("  python scripts/test-crater.py --seed 42  # Reproducible features")
    print("  python scripts/test-crater.py --static   # No sliders")


if __name__ == "__main__":
    main()
