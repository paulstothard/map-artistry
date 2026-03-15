# map-artistry

Artistic topographic map generator using OpenStreetMap, satellite imagery, and digital elevation
models. Generates high-resolution, stylized maps via a customizable pipeline.

## Usage

First, create a virtual environment and install the required Python packages:

```bash
/usr/local/bin/python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Then generate a map using [just](https://github.com/casey/just) (a command runner):

```bash
just edmonton coral          # Generate Edmonton map with coral scheme
just victoria natural        # Generate Victoria map with natural colors
just edmonton all            # Generate all color schemes for Edmonton
just all                     # Generate all maps for all locations
just schemes                 # List available color schemes
```

### Available Color Schemes

- `coral` - Warm coral/red background with white water features
- `river_runs_red` - Black background with red water features
- `blue-yellow` - Blue background with yellow water features
- `natural` - Natural earth tones with green/brown terrain
- `lava` - Volcanic lava with red water
- `frozen` - Frozen landscape with ice and snow
- `satellite` - Satellite imagery with terrain overlay

### Customizing Maps with Config Overlays

To tweak a map's appearance, create a config overlay file in the `configs/` directory:

```bash
# Generate base map first
just victoria coral

# Create an overlay file (examples provided in configs/)
cp configs/victoria-coral-overlay.yaml.example configs/victoria-coral-overlay.yaml

# Edit the overlay with your tweaks
vi configs/victoria-coral-overlay.yaml

# Rebuild - overlay is automatically applied!
just victoria coral
```

See [configs/README.md](configs/README.md) for detailed documentation on config overlays.

### Available Commands

Run `just --list` to see all available recipes:

```bash
just --list
```

### Project Structure

```text
downloads/               # All downloaded/cached data
  regions/              # Region-specific data (auto-downloaded)
    edmonton/
      area.geojson      # Boundary polygon
      dem.tif           # Digital elevation model
      satellite.tif     # Satellite imagery
      layers/*.gpkg     # OSM layers (roads, water, etc.)
    victoria/
    vancouver-island/
  ocean-boundaries/     # IHO World Seas reference data (manual download)

output/                 # Generated maps and configs
  edmonton-coral/
    config-base.yaml    # Base color scheme config
    config.yaml         # Final merged config
    map.png             # Rendered map

configs/                # Optional config overlays for tweaking
cache/                  # OSM query cache (auto-generated)
```

### Options

Each location has its own settings defined in the justfile (buffer distance, dimensions, DPI, etc.).
To modify these, edit the variables at the top of the justfile.

### Recommended Zoom Levels

| Zoom | Detail Level                     | Suggested Use                         |
| ---- | -------------------------------- | ------------------------------------- |
| 5    | Very low (province scale)        | Large areas like Vancouver Island     |
| 6    | Low (regional scale)             | Entire cities with surroundings       |
| 7    | Medium (town/neighborhood scale) | City cores or small regions           |
| 8+   | High (street-level detail)       | Close-up views, custom crops required |

### Ocean Data (for Coastal Maps)

Victoria and Vancouver Island maps automatically include ocean features. This requires downloading
the **World Seas (IHO Sea Areas)** shapefile from
[https://www.marineregions.org/downloads.php](https://www.marineregions.org/downloads.php).

Download `World_Seas_IHO_v3.zip`, extract it, and place all the files (`.shp`, `.dbf`, `.shx`, etc.)
into a folder named `downloads/ocean-boundaries/` within the project directory.

The build pipeline will attempt to derive a region-specific `ocean.gpkg` layer from that source data for each region and will skip cleanly when no ocean overlaps the map area.

### Cache

When generating OSM layers, the pipeline uses OSMnx to query the Overpass API. To avoid repeated
downloads and reduce load on the API, responses are cached locally in a `cache/` folder in the
project directory. This folder can safely be deleted at any time, though doing so will cause fresh
downloads on the next run.
