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


# DESIGN_SETTINGS
DESIGN_SETTINGS = {
    "coral": {
        "map": {
            "background": {"fc": "#aa332e", "ec": "#aa332e"},
            "scheme": "coral",
            "info": {
                "text": "map-artistry",
                "show": True,
                "position": "bottom-right",
                "font": "DejaVu Sans",
                "fontsize": 10,
                "color": "#cccccc",
            },
            "hillshade": {
                "azimuth": 315,
                "altitude": 45,
                "cmap": "bone",
                "alpha": 0.1,
                "sigma": 1.0,
            },
            "satellite": {
                "visible": False,
                "opacity": 1.0,
            },
        },
        "water": {
            "fc": "#ffffff",
            "ec": "#ffffff",
            "alpha": 1.0,
            "zorder": 4,
            "ew": 0,
            "visible": True,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": True,
                "MultiLineString": True,
                "Polygon": True,
                "MultiPolygon": True,
            },
            "palette": [],
        },
        "ocean": {
            "fc": "#ffffff",
            "ec": "#888888",
            "alpha": 0.9,
            "zorder": 4,
            "ew": 0.1,
            "visible": True,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": True,
                "MultiLineString": True,
                "Polygon": True,
                "MultiPolygon": True,
            },
            "palette": [],
        },
        "waterway": {
            "fc": "#ffffff",
            "ec": "#ffffff",
            "alpha": 1.0,
            "ew": 0,
            "zorder": 3,
            "visible": True,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": True,
                "MultiLineString": True,
                "Polygon": True,
                "MultiPolygon": True,
            },
            "palette": [],
            "lw": {"stream": 0.2, "river": 1.0, "canal": 0.3, "drain": 0.2},
            "default_lw": 0.2,
        },
        "road": {
            "fc": "#ffffff",
            "ec": "#ffffff",
            "alpha": 1.0,
            "ew": 0,
            "zorder": 6,
            "visible": True,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": True,
                "MultiLineString": True,
                "Polygon": True,
                "MultiPolygon": True,
            },
            "palette": [],
            "lw": {
                "motorway": 0.20,
                "trunk": 0.18,
                "primary": 0.16,
                "secondary": 0.14,
                "tertiary": 0.12,
                "residential": 0.10,
            },
            "default_lw": 0.1,
        },
        "building": {
            "fc": "#ffffff",
            "ec": "#000000",
            "alpha": 1.0,
            "zorder": 7,
            "ew": 0.01,
            "visible": True,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": True,
                "MultiLineString": True,
                "Polygon": True,
                "MultiPolygon": True,
            },
            "palette": ["#FFFFFF", "#F2F2F2", "#E6E6E6"],
        },
        "natural": {
            "fc": "#b36969",
            "ec": "#913f3f",
            "alpha": 0.8,
            "zorder": 1,
            "ew": 0,
            "visible": True,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": True,
                "MultiLineString": True,
                "Polygon": True,
                "MultiPolygon": True,
            },
            "palette": [],
        },
        "landuse": {
            "fc": "#d9a57f",
            "ec": "#d9a57f",
            "alpha": 1.0,
            "zorder": 2,
            "ew": 0,
            "visible": False,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": False,
                "MultiLineString": False,
                "Polygon": False,
                "MultiPolygon": False,
            },
            "palette": [],
        },
        "railway": {
            "fc": "#ffffff",
            "ec": "#ffffff",
            "alpha": 1.0,
            "zorder": 5,
            "ew": 0,
            "visible": False,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": False,
                "MultiLineString": False,
                "Polygon": False,
                "MultiPolygon": False,
            },
            "palette": [],
            "default_lw": 0.12,
        },
        "transport": {
            "fc": "#f0e68c",
            "ec": "#f0e68c",
            "alpha": 1.0,
            "zorder": 5,
            "ew": 0,
            "visible": False,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": False,
                "MultiLineString": False,
                "Polygon": False,
                "MultiPolygon": False,
            },
            "palette": [],
            "default_lw": 0.08,
        },
        "places": {
            "fc": "#ffe4b5",
            "ec": "#ffe4b5",
            "alpha": 1.0,
            "zorder": 5,
            "ew": 0,
            "visible": False,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": False,
                "MultiLineString": False,
                "Polygon": False,
                "MultiPolygon": False,
            },
            "palette": [],
        },
        "poi": {
            "fc": "#b36969",
            "ec": "#b36969",
            "alpha": 0.5,
            "zorder": 1,
            "ew": 0,
            "visible": True,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": True,
                "MultiLineString": True,
                "Polygon": True,
                "MultiPolygon": True,
            },
            "palette": [],
            "marker": "o",
            "size": 0.1,
        },
        "pofw": {
            "fc": "#ffdead",
            "ec": "#ffdead",
            "alpha": 1.0,
            "zorder": 5,
            "ew": 0,
            "visible": False,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": False,
                "MultiLineString": False,
                "Polygon": False,
                "MultiPolygon": False,
            },
            "palette": [],
        },
        "traffic": {
            "fc": "#cccccc",
            "ec": "#cccccc",
            "alpha": 1.0,
            "zorder": 5,
            "ew": 0,
            "visible": False,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": False,
                "MultiLineString": False,
                "Polygon": False,
                "MultiPolygon": False,
            },
            "palette": [],
            "default_lw": 0.15,
        },
        "other": {
            "fc": "#cccccc",
            "ec": "#cccccc",
            "alpha": 1.0,
            "zorder": 0,
            "ew": 0,
            "visible": False,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": False,
                "MultiLineString": False,
                "Polygon": False,
                "MultiPolygon": False,
            },
            "palette": [],
            "default_lw": 0.1,
        },
    },
    "river_runs_red": {
        "map": {
            "background": {"fc": "#000000", "ec": "#000000"},
            "scheme": "river_runs_red",
            "info": {
                "text": "map-artistry",
                "show": True,
                "position": "bottom-right",
                "font": "DejaVu Sans",
                "fontsize": 10,
                "color": "#cccccc",
            },
            "hillshade": {
                "azimuth": 315,
                "altitude": 45,
                "cmap": "bone",
                "alpha": 0.1,
                "sigma": 1.0,
            },
            "satellite": {
                "visible": False,
                "opacity": 1.0,
            },
        },
        "water": {
            "fc": "#ff6666",
            "ec": "#ff6666",
            "alpha": 0.9,
            "zorder": 4,
            "ew": 0,
            "visible": True,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": True,
                "MultiLineString": True,
                "Polygon": True,
                "MultiPolygon": True,
            },
            "palette": [],
        },
        "ocean": {
            "fc": "#ff6666",
            "ec": "#883333",
            "alpha": 0.9,
            "zorder": 4,
            "ew": 0.1,
            "visible": True,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": True,
                "MultiLineString": True,
                "Polygon": True,
                "MultiPolygon": True,
            },
            "palette": [],
        },
        "waterway": {
            "fc": "#cc0000",
            "ec": "#cc0000",
            "alpha": 1.0,
            "ew": 0,
            "zorder": 3,
            "visible": True,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": True,
                "MultiLineString": True,
                "Polygon": True,
                "MultiPolygon": True,
            },
            "palette": [],
            "lw": {"stream": 0.2, "river": 1.0, "canal": 0.3, "drain": 0.2},
            "default_lw": 0.2,
        },
        "road": {
            "fc": "#ffffff",
            "ec": "#ffffff",
            "alpha": 1.0,
            "ew": 0,
            "zorder": 6,
            "visible": True,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": True,
                "MultiLineString": True,
                "Polygon": True,
                "MultiPolygon": True,
            },
            "palette": [],
            "lw": {
                "motorway": 0.20,
                "trunk": 0.18,
                "primary": 0.16,
                "secondary": 0.14,
                "tertiary": 0.12,
                "residential": 0.10,
            },
            "default_lw": 0.1,
        },
        "building": {
            "fc": "#ffffff",
            "ec": "#000000",
            "alpha": 1.0,
            "zorder": 7,
            "ew": 0.01,
            "visible": True,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": True,
                "MultiLineString": True,
                "Polygon": True,
                "MultiPolygon": True,
            },
            "palette": ["#FFFFFF", "#F2F2F2", "#E6E6E6"],
        },
        "natural": {
            "fc": "#354038",
            "ec": "#2a302e",
            "alpha": 0.5,
            "zorder": 1,
            "ew": 0,
            "visible": True,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": True,
                "MultiLineString": True,
                "Polygon": True,
                "MultiPolygon": True,
            },
            "palette": [],
        },
        "landuse": {
            "fc": "#4b3832",
            "ec": "#4b3832",
            "alpha": 1.0,
            "zorder": 2,
            "ew": 0,
            "visible": False,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": False,
                "MultiLineString": False,
                "Polygon": False,
                "MultiPolygon": False,
            },
            "palette": [],
        },
        "railway": {
            "fc": "#ffffff",
            "ec": "#ffffff",
            "alpha": 1.0,
            "zorder": 5,
            "ew": 0,
            "visible": False,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": False,
                "MultiLineString": False,
                "Polygon": False,
                "MultiPolygon": False,
            },
            "palette": [],
            "default_lw": 0.12,
        },
        "transport": {
            "fc": "#ffa07a",
            "ec": "#ffa07a",
            "alpha": 1.0,
            "zorder": 5,
            "ew": 0,
            "visible": False,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": False,
                "MultiLineString": False,
                "Polygon": False,
                "MultiPolygon": False,
            },
            "palette": [],
            "default_lw": 0.08,
        },
        "places": {
            "fc": "#ffa500",
            "ec": "#ffa500",
            "alpha": 1.0,
            "zorder": 5,
            "ew": 0,
            "visible": False,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": False,
                "MultiLineString": False,
                "Polygon": False,
                "MultiPolygon": False,
            },
            "palette": [],
        },
        "poi": {
            "fc": "#354038",
            "ec": "#354038",
            "alpha": 0.5,
            "zorder": 1,
            "ew": 0,
            "visible": True,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": True,
                "MultiLineString": True,
                "Polygon": True,
                "MultiPolygon": True,
            },
            "palette": [],
            "marker": "o",
            "size": 0.1,
        },
        "pofw": {
            "fc": "#ff4500",
            "ec": "#ff4500",
            "alpha": 1.0,
            "zorder": 5,
            "ew": 0,
            "visible": False,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": False,
                "MultiLineString": False,
                "Polygon": False,
                "MultiPolygon": False,
            },
            "palette": [],
        },
        "traffic": {
            "fc": "#999999",
            "ec": "#999999",
            "alpha": 1.0,
            "zorder": 5,
            "ew": 0,
            "visible": False,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": False,
                "MultiLineString": False,
                "Polygon": False,
                "MultiPolygon": False,
            },
            "palette": [],
            "default_lw": 0.15,
        },
        "other": {
            "fc": "#cccccc",
            "ec": "#cccccc",
            "alpha": 1.0,
            "zorder": 0,
            "ew": 0,
            "visible": False,
            "geometry_visibility": {
                "Point": False,
                "MultiPoint": False,
                "LineString": False,
                "MultiLineString": False,
                "Polygon": False,
                "MultiPolygon": False,
            },
            "palette": [],
            "default_lw": 0.1,
        },
    },
}


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
):
    if not geojson_path:
        raise ValueError("A geojson_path is required")
    # Load mask if provided
    mask_gdf = gpd.read_file(geojson_path)
    # Select the design scheme based on the provided scheme name
    design = DESIGN_SETTINGS[scheme_name]

    config = {
        "map": dict(design["map"]),
        "layers": {},
    }

    # Include DEM path in map section if specified
    config["map"]["dem"] = str(dem_path) if dem_path is not None else None

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
        gdf = gpd.read_file(layer_path)
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
            settings = design[cat]
            default_style = {
                "fc": settings["fc"],
                "ec": settings.get("ec", settings["fc"]),
                "alpha": settings["alpha"],
                "zorder": settings["zorder"],
                "visible": settings.get("visible", True),
                "palette": settings.get("palette", []),
            }

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
            for attr in preferred_attributes_for_layer(layer_name):
                vals = attrs.get(attr)
                if isinstance(vals, list) and vals:
                    rules = {}
                    # For roads: line widths by highway or fclass
                    if cat == "road" and attr in ("highway", "fclass") and "lw" in settings:
                        for v in vals:
                            if v in settings.get("lw", {}):
                                rules[v] = {"linewidth": settings["lw"][v]}
                            else:
                                rules[v] = {}
                    # For waterways: line widths by fclass
                    elif cat == "waterway" and attr in ("waterway", "fclass") and "lw" in settings:
                        for v in vals:
                            if v in settings.get("lw", {}):
                                rules[v] = {"linewidth": settings["lw"][v]}
                            else:
                                rules[v] = {}
                    else:
                        rules = {v: {} for v in vals}
                    style_rules[attr] = rules
            style_order = [
                a
                for a in preferred_attributes_for_layer(layer_name)
                if a in style_rules
            ]

            # visibility logic: per-geometry
            visible_flag = settings.get("geometry_visibility", {}).get(geom_type, False)

            # assemble entry
            config["layers"][f"{layer_name}{suffix}"] = {
                "file": str(layer_path),
                "layer": layer_name,
                "geometry_type": geom_type,
                "visible": visible_flag,
                "default": default_style,
                "style_rules": style_rules,
                "style_order": style_order,
                "attributes": attrs,
            }

        # If a satellite file is provided, ensure the map section has
        # a satellite dict and inject the file path.
        if satellite is not None:
            config["map"].setdefault(
                "satellite",
                {"visible": True, "opacity": 1.0},
            )
            config["map"]["satellite"]["path"] = str(satellite)

    # Write YAML
    with open(output_path, "w") as f:
        f.write("\n".join(header))
        yaml.dump(config, f, sort_keys=False, Dumper=NoAliasDumper)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate YAML config from GeoPackage layer files"
    )
    parser.add_argument("layer_files", nargs="+", help="Paths to .gpkg files")
    parser.add_argument(
        "-g", "--geojson", type=str, required=True, help="GeoJSON boundary (required)"
    )
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
        choices=list(DESIGN_SETTINGS.keys()),
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
        "--satellite",
        dest="satellite",
        type=str,
        default=None,
        help="Path to a satellite image file (optional)",
    )
    args = parser.parse_args()
    generate_yaml(
        layer_files=[Path(p) for p in args.layer_files],
        geojson_path=Path(args.geojson),
        output_path=Path(args.output),
        unique_threshold=args.unique_threshold,
        scheme_name=args.scheme_name,
        dem_path=Path(args.dem_path) if args.dem_path else None,
        satellite=Path(args.satellite) if args.satellite else None,
    )
