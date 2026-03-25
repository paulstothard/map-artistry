#!/usr/bin/env python3
# Copyright (c) 2026 Paul Stothard
# SPDX-License-Identifier: MIT

from pathlib import Path
import os
import yaml


# Disable YAML anchors (no aliases)
class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


import geopandas as gpd
import argparse
import sys
from geojson_bounds import apply_primary_segment_clip


"""
Load color schemes from YAML files in the schemes/ directory.
Returns a dictionary mapping scheme names to their configurations.
"""


def load_schemes():
    schemes_dir = Path(__file__).parent.parent / "schemes"
    schemes = {}

    if not schemes_dir.exists():
        raise FileNotFoundError(
            f"Schemes directory not found: {schemes_dir}\n"
            f"Please ensure the 'schemes/' directory exists in the project root."
        )

    for scheme_file in schemes_dir.glob("*.yaml"):
        scheme_name = scheme_file.stem
        try:
            with open(scheme_file, "r") as f:
                schemes[scheme_name] = yaml.safe_load(f)
        except Exception as e:
            print(
                f"Warning: Failed to load scheme '{scheme_name}': {e}", file=sys.stderr
            )

    if not schemes:
        raise ValueError(
            f"No valid color schemes found in {schemes_dir}\n"
            f"Please ensure YAML scheme files exist in the 'schemes/' directory."
        )

    return schemes


# Load color schemes from external files on module initialization
DESIGN_SETTINGS = load_schemes()

"""
Determine the styling category key for a given layer name, used to select design parameters.
"""


def get_category_key(layer_name: str) -> str:
    lname = layer_name.lower()
    if "rail" in lname:
        return "railway"
    if "road" in lname or "highway" in lname:
        return "road"
    for key in [
        "building",
        "landuse",
        "waterway",
        "water",
        "natural",
        "transport",
        "places",
        "poi",
        "pofw",
        "traffic",
        "sea",
        "ocean",
    ]:
        if key in lname:
            return "ocean" if key == "sea" else key
    return "other"


"""
Return a list of attribute names that are preferred for styling a given layer.
These attributes will be used to generate style rules in the config.
For road layers, "highway" is prioritized (the standard OSM tag for road type),
with "fclass" as a fallback for pre-processed datasets.
"""


def preferred_attributes_for_layer(layer_name):
    lname = layer_name.lower()

    # -------- Roads / Highways -------------------------------------------
    if ("road" in lname) or ("highway" in lname):
        return ["highway", "fclass", "class", "maxspeed"]

    # -------- Buildings ---------------------------------------------------
    if "building" in lname:
        return ["fclass", "height"]

    # -------- Waterways ---------------------------------------------------
    if "waterway" in lname:
        return ["waterway", "fclass", "width"]

    # -------- Natural features -------------------------------------------
    if "natural" in lname:
        return ["fclass", "code"]

    # -------- Fallback ----------------------------------------------------
    return ["fclass", "type", "name"]


def _parse_text_stats(text_stats):
    """
    Parse text stats into [{"value": ..., "label": ...}] entries.

    Supported formats:
      - Preferred: "VALUE||LABEL"
      - Backward compatible: "VALUE:LABEL"
      - Multiple stats in one arg: "VALUE||LABEL;;VALUE||LABEL"
    """
    if not text_stats:
        return []

    parsed = []
    for raw_stat in text_stats:
        if raw_stat is None:
            continue

        chunks = [chunk.strip() for chunk in str(raw_stat).split(";;") if chunk.strip()]
        for chunk in chunks:
            if "||" in chunk:
                value, label = chunk.split("||", 1)
                parsed.append({"value": value.strip(), "label": label.strip()})
            elif ":" in chunk:
                value, label = chunk.split(":", 1)
                parsed.append({"value": value.strip(), "label": label.strip()})
            else:
                parsed.append({"value": chunk.strip(), "label": ""})

    return parsed


"""
Generate a YAML configuration file for map rendering using OSM layers in GeoPackage format.
For each layer and geometry type, a style entry is created based on the selected design scheme.
"""


def generate_yaml(
    layer_files,
    geojson_path,
    output_path=Path("config.yaml"),
    unique_threshold=50,
    scheme_name="coral",
    dem_path=None,
    satellite=None,
    text_title=None,
    text_subtitle=None,
    text_location=None,
    text_stats=None,
    enable_text=False,
    route_gpx=None,
):
    if not geojson_path:
        raise ValueError("A geojson_path is required")
    # Load mask if provided
    mask_gdf = gpd.read_file(geojson_path, engine="pyogrio", use_arrow=True)
    if mask_gdf.crs is None:
        mask_gdf = mask_gdf.set_crs("EPSG:4326")
    else:
        mask_gdf = mask_gdf.to_crs("EPSG:4326")

    mask_gdf, primary_segment, antimeridian_clipped = apply_primary_segment_clip(
        mask_gdf
    )
    if antimeridian_clipped:
        print(
            "[ ] Antimeridian boundary detected in config mask; "
            f"using primary segment bounds: {primary_segment}"
        )

    # Select the design scheme based on the provided scheme name
    design = DESIGN_SETTINGS[scheme_name]

    config = {
        "map": yaml.safe_load(yaml.safe_dump(design["map"])),
        "layers": {},
    }

    if route_gpx is not None:
        config["map"]["route_gpx"] = str(route_gpx)

    # Include DEM path in map section if specified
    config["map"]["dem"] = str(dem_path) if dem_path is not None else None
    config["map"].setdefault("hillshade", {})
    config["map"]["hillshade"].setdefault("azimuths", [315, 45, 270, 90])
    config["map"]["hillshade"].setdefault("weights", [1.2, 1.0, 0.8, 0.8])
    config["map"]["hillshade"].setdefault("multidirectional", True)
    config["map"]["hillshade"].setdefault("vert_exag", 1.0)
    config["map"]["hillshade"].setdefault("interpolation", "bicubic")
    config["map"]["hillshade"].setdefault("zorder", 0)
    config["map"]["hillshade"].setdefault("render_mode", "cmap")
    config["map"]["hillshade"].setdefault(
        "tone",
        {
            "clip_low": 0.0,
            "clip_high": 1.0,
            "contrast": 1.0,
            "gamma": 1.0,
            "bias": 0.0,
            "ambient": 0.0,
        },
    )
    config["map"]["hillshade"].setdefault(
        "tint",
        {
            "shadow_color": "#0b0f14",
            "mid_color": "#5f6368",
            "highlight_color": "#f3f1eb",
        },
    )
    config["map"]["hillshade"].setdefault(
        "multiscale",
        {
            "enabled": False,
            "scales": [
                {"sigma": 8.0, "weight": 0.65},
                {"sigma": 2.0, "weight": 0.35},
            ],
        },
    )

    config["map"].setdefault(
        "terrain",
        {
            "visible": False,
            "alpha": 1.0,
            "zorder": 0,
            "percentiles": [2, 98],
            "blend_mode": "soft_light",
            "shade_strength": 0.6,
            "interpolation": "bicubic",
            "colors": [
                "#132B43",
                "#255D83",
                "#4D8DA6",
                "#7FAE7B",
                "#B8C98A",
                "#D7C29E",
                "#A9835A",
                "#7A5D45",
                "#F2F1ED",
            ],
        },
    )

    # Header comments to be included at the top of the YAML file
    header = [
        "# YAML configuration for map rendering",
        "# zorder controls drawing order: higher values are drawn on top",
        "# You can override default styles per feature type by editing the style_rules section\n",
    ]

    for layer_path in layer_files:
        if not layer_path.exists() or layer_path.suffix.lower() != ".gpkg":
            print(f"Skipping {layer_path} (not a .gpkg file)")
            continue
        layer_name = layer_path.stem
        gdf = gpd.read_file(layer_path, engine="pyogrio", use_arrow=True)
        if mask_gdf is not None:
            gdf = gpd.clip(gdf, mask_gdf)

        # Determine all geometry types in this layer
        geom_types = gdf.geom_type.unique().tolist()

        # For each geometry subtype, build a separate config entry
        for geom_type in geom_types:
            sub_gdf = gdf[gdf.geom_type == geom_type]
            suffix = f"__{geom_type}" if len(geom_types) > 1 else ""

            # sample attributes
            attrs = {}
            for col in sub_gdf.columns:
                if col == "geometry":
                    continue
                vals = sub_gdf[col].dropna().astype(str).unique().tolist()
                attrs[col] = vals if len(vals) <= unique_threshold else len(vals)

            # style: get settings from design
            cat = get_category_key(layer_name)
            if cat not in design:
                continue  # skip layer if not defined in the design scheme
            settings = design[cat]
            default_style = {
                "fc": settings["fc"],
                "ec": settings.get("ec", settings["fc"]),
                "alpha": settings["alpha"],
                "zorder": settings["zorder"],
                "visible": settings.get("visible", True),
                "palette": settings.get("palette", []),
            }
            if "texture" in settings:
                default_style["texture"] = yaml.safe_load(
                    yaml.safe_dump(settings["texture"])
                )
            if "hillshade_texture" in settings:
                default_style["hillshade_texture"] = yaml.safe_load(
                    yaml.safe_dump(settings["hillshade_texture"])
                )

            # Add geometry-dependent defaults
            if "polygon" in geom_type.lower():
                default_style["edge_color"] = settings.get("ec", settings["fc"])
                default_style["edge_width"] = settings.get("ew", 0)
            else:
                # For lines and points: set default line width
                default_style["linewidth"] = settings.get("default_lw", 1.0)

            # If point geometry, include marker and size defaults
            if "point" in geom_type.lower():
                default_style["marker"] = settings.get("marker", "o")
                default_style["size"] = settings.get("size", 3)

            style_rules = {}
            for attr in [
                a for a in preferred_attributes_for_layer(layer_name) if a in attrs
            ]:
                vals = attrs.get(attr)
                if isinstance(vals, list) and vals:
                    rules = {}
                    # For roads: line widths by highway or fclass
                    if (
                        cat == "road"
                        and attr in ("highway", "fclass")
                        and "lw" in settings
                    ):
                        for v in vals:
                            if v in settings.get("lw", {}):
                                rules[v] = {"linewidth": settings["lw"][v]}
                            else:
                                rules[v] = {}
                    # For waterways: line widths by fclass
                    elif (
                        cat == "waterway"
                        and attr in ("waterway", "fclass")
                        and "lw" in settings
                    ):
                        for v in vals:
                            if v in settings.get("lw", {}):
                                rules[v] = {"linewidth": settings["lw"][v]}
                            else:
                                rules[v] = {}
                    else:
                        rules = {v: {} for v in vals}
                    style_rules[attr] = rules
            style_order = list(style_rules.keys())

            # visibility logic: per-geometry
            visible_flag = settings.get("geometry_visibility", {}).get(geom_type, False)

            # assemble entry
            layer_config = {
                "file": str(layer_path),
                "layer": layer_name,
                "geometry_type": geom_type,
                "visible": visible_flag,
                "default": default_style,
                "attributes": attrs,
            }
            if style_rules:
                layer_config["style_rules"] = style_rules
                layer_config["style_order"] = style_order

            config["layers"][f"{layer_name}{suffix}"] = layer_config

        # If a satellite file is provided, ensure the map section has
        # a satellite dict and inject the file path.
        if satellite is not None:
            config["map"].setdefault(
                "satellite",
                {"visible": True, "opacity": 1.0},
            )
            config["map"]["satellite"]["path"] = str(satellite)

    # Handle info panel configuration
    if enable_text and "info_panel" in config["map"]:
        config["map"]["info_panel"]["enabled"] = True

        # Update panel elements with provided content
        if config["map"]["info_panel"].get("elements"):
            for element in config["map"]["info_panel"]["elements"]:
                element_id = element.get("id")

                if element_id == "title" and text_title:
                    element["content"] = text_title
                elif element_id == "subtitle" and text_subtitle:
                    element["content"] = text_subtitle
                elif element_id == "location" and text_location:
                    element["content"] = text_location
                elif element_id == "stats" and text_stats:
                    element["items"] = _parse_text_stats(text_stats)

    # Write YAML
    with open(output_path, "w") as f:
        f.write("\n".join(header))
        yaml.dump(config, f, sort_keys=False, Dumper=NoAliasDumper)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate YAML config from GeoPackage layer files"
    )
    parser.add_argument("layer_files", nargs="*", help="Paths to .gpkg files")
    parser.add_argument("-g", "--geojson", type=str, help="GeoJSON boundary file")
    parser.add_argument(
        "-o", "--output", type=str, default="config.yaml", help="YAML output path"
    )
    parser.add_argument(
        "-t",
        "--unique-threshold",
        dest="unique_threshold",
        type=int,
        default=50,
        help="Max unique values to list (default: 50)",
    )
    parser.add_argument(
        "-s",
        "--scheme",
        dest="scheme_name",
        type=str,
        default="coral",
        help="Color scheme to use (default: coral)",
    )
    parser.add_argument(
        "-d",
        "--dem",
        dest="dem_path",
        type=str,
        default=None,
        help="Path to a DEM GeoTIFF file (optional)",
    )
    parser.add_argument(
        "--gpx",
        dest="route_gpx",
        type=str,
        default=None,
        help="Path to GPX route file for route/profile rendering and optional distance derivation",
    )
    parser.add_argument(
        "--satellite",
        dest="satellite",
        type=str,
        default=None,
        help="Path to a satellite image file (optional)",
    )
    parser.add_argument(
        "--list-schemes",
        action="store_true",
        help="List all available color schemes and exit",
    )
    parser.add_argument(
        "--text-title",
        dest="text_title",
        type=str,
        default=None,
        help="Title text to display on map",
    )
    parser.add_argument(
        "--text-subtitle",
        dest="text_subtitle",
        type=str,
        default=None,
        help="Subtitle text to display on map",
    )
    parser.add_argument(
        "--text-location",
        dest="text_location",
        type=str,
        default=None,
        help="Location text to display on map",
    )
    parser.add_argument(
        "--text-stats",
        dest="text_stats",
        type=str,
        action="append",
        default=None,
        help=(
            "Stats to display. Supports 'VALUE||LABEL' (preferred), "
            "'VALUE:LABEL' (backward compatible), and ';;' as multi-stat separator"
        ),
    )
    parser.add_argument(
        "--enable-text",
        dest="enable_text",
        action="store_true",
        help="Enable text rendering on the map",
    )
    args = parser.parse_args()

    # Handle --list-schemes
    if args.list_schemes:
        if sys.stdout.isatty():
            print("\n📋 Available Color Schemes:\n")
            for scheme_name in sorted(DESIGN_SETTINGS.keys()):
                bg_color = (
                    DESIGN_SETTINGS[scheme_name]
                    .get("map", {})
                    .get("background", {})
                    .get("fc", "N/A")
                )
                print(f"  • {scheme_name:20} (background: {bg_color})")
            print()
        else:
            for scheme_name in sorted(DESIGN_SETTINGS.keys()):
                print(scheme_name)
        sys.exit(0)

    # Validate required args (if not listing schemes)
    if not args.layer_files or not args.geojson:
        parser.error(
            "layer_files and --geojson are required (unless using --list-schemes)"
        )

    # Validate scheme name
    if args.scheme_name not in DESIGN_SETTINGS:
        available_schemes = ", ".join(sorted(DESIGN_SETTINGS.keys()))
        print(
            f"\n❌ Error: Unknown color scheme '{args.scheme_name}'\n", file=sys.stderr
        )
        print(f"📋 Available schemes: {available_schemes}\n", file=sys.stderr)
        print(f"   Use --list-schemes to see more details\n", file=sys.stderr)
        sys.exit(1)
    generate_yaml(
        layer_files=[Path(p) for p in args.layer_files],
        geojson_path=Path(args.geojson),
        output_path=Path(args.output),
        unique_threshold=args.unique_threshold,
        scheme_name=args.scheme_name,
        dem_path=Path(args.dem_path) if args.dem_path else None,
        satellite=Path(args.satellite) if args.satellite else None,
        text_title=args.text_title,
        text_subtitle=args.text_subtitle,
        text_location=args.text_location,
        text_stats=args.text_stats,
        enable_text=args.enable_text,
        route_gpx=Path(args.route_gpx) if args.route_gpx else None,
    )
