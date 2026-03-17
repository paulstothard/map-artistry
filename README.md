# map-artistry

Artistic topographic map generator using OpenStreetMap, satellite imagery, and digital elevation
models. Generates high-resolution, stylized maps via a customizable pipeline.

## Dependencies

- [just](https://github.com/casey/just) 1.47.0 or newer — command runner (`brew install just` on
  macOS)
- Python 3

## Getting Started

First, download or clone the repository and switch to the project directory:

```bash
git clone https://github.com/paulstothard/map-artistry.git
cd map-artistry
```

Then proceed with the setup steps below.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
# Build a map with default settings (24" × 24" @ 600 DPI, PNG format) - "coral" is the color scheme
just build "Edmonton, AB" coral

# Build with a different location and use the "natural" color scheme
just build "Vancouver Island, BC" natural

# Build with custom dimensions using the "river_runs_red" color scheme
just build --width 36 --height 24 "Iceland" river_runs_red

# Build with custom dimensions, DPI, format, boundary buffer, and "natural" color scheme
just build --width 24 --height 24 --dpi 600 --format png --buffer-km 20 "Victoria, BC" natural

# List available color schemes
just schemes
```

All settings (boundary padding, DEM source, satellite zoom, layer source) are calculated
automatically based on region size. Use `--buffer-km` to override the automatic extra distance added
around the region boundary, in kilometers.

## Color Schemes

- `coral` — red-toned scheme with white water features (hides natural layer)
- `river_runs_red` — dark red/black scheme with red water features (hides natural and land use layers)
- `natural` — hypsometric tints (green → brown → grey → white), bluish water (hides roads, buildings, and land use layers)
- `lava` — fiery elevation coloring, orange water (hides roads, buildings, and land use layers)
- `glacier` — cool grey-green to white elevation palette, blue-grey water (hides roads, buildings, and land use layers)
- `satellite` — satellite imagery base with vector/map layer overlays (hides natural and land use layers)

**Layer types:** natural (forests, wetlands, beaches, etc.), land use (urban areas), roads (street network), buildings (footprints), water/waterway (bodies of water and streams).

## Examples

### British Columbia

[![British Columbia - Coral](examples/thumbnails/british-columbia-coral.png)](examples/full/british-columbia-coral.png)
[![British Columbia - River Runs Red](examples/thumbnails/british-columbia-river_runs_red.png)](examples/full/british-columbia-river_runs_red.png)
[![British Columbia - Natural](examples/thumbnails/british-columbia-natural.png)](examples/full/british-columbia-natural.png)
[![British Columbia - Lava](examples/thumbnails/british-columbia-lava.png)](examples/full/british-columbia-lava.png)
[![British Columbia - Glacier](examples/thumbnails/british-columbia-glacier.png)](examples/full/british-columbia-glacier.png)
[![British Columbia - Satellite](examples/thumbnails/british-columbia-satellite.png)](examples/full/british-columbia-satellite.png)

### Edmonton, AB

[![Edmonton - Coral](examples/thumbnails/edmonton-ab-coral.png)](examples/full/edmonton-ab-coral.png)
[![Edmonton - River Runs Red](examples/thumbnails/edmonton-ab-river_runs_red.png)](examples/full/edmonton-ab-river_runs_red.png)
[![Edmonton - Natural](examples/thumbnails/edmonton-ab-natural.png)](examples/full/edmonton-ab-natural.png)
[![Edmonton - Lava](examples/thumbnails/edmonton-ab-lava.png)](examples/full/edmonton-ab-lava.png)
[![Edmonton - Glacier](examples/thumbnails/edmonton-ab-glacier.png)](examples/full/edmonton-ab-glacier.png)
[![Edmonton - Satellite](examples/thumbnails/edmonton-ab-satellite.png)](examples/full/edmonton-ab-satellite.png)

### Iceland

[![Iceland - Coral](examples/thumbnails/iceland-coral.png)](examples/full/iceland-coral.png)
[![Iceland - River Runs Red](examples/thumbnails/iceland-river_runs_red.png)](examples/full/iceland-river_runs_red.png)
[![Iceland - Natural](examples/thumbnails/iceland-natural.png)](examples/full/iceland-natural.png)
[![Iceland - Lava](examples/thumbnails/iceland-lava.png)](examples/full/iceland-lava.png)
[![Iceland - Glacier](examples/thumbnails/iceland-glacier.png)](examples/full/iceland-glacier.png)
[![Iceland - Satellite](examples/thumbnails/iceland-satellite.png)](examples/full/iceland-satellite.png)

### Vancouver, BC

[![Vancouver - Coral](examples/thumbnails/vancouver-bc-coral.png)](examples/full/vancouver-bc-coral.png)
[![Vancouver - River Runs Red](examples/thumbnails/vancouver-bc-river_runs_red.png)](examples/full/vancouver-bc-river_runs_red.png)
[![Vancouver - Natural](examples/thumbnails/vancouver-bc-natural.png)](examples/full/vancouver-bc-natural.png)
[![Vancouver - Lava](examples/thumbnails/vancouver-bc-lava.png)](examples/full/vancouver-bc-lava.png)
[![Vancouver - Glacier](examples/thumbnails/vancouver-bc-glacier.png)](examples/full/vancouver-bc-glacier.png)
[![Vancouver - Satellite](examples/thumbnails/vancouver-bc-satellite.png)](examples/full/vancouver-bc-satellite.png)

### Vancouver Island, BC

[![Vancouver Island - Coral](examples/thumbnails/vancouver-island-bc-coral.png)](examples/full/vancouver-island-bc-coral.png)
[![Vancouver Island - River Runs Red](examples/thumbnails/vancouver-island-bc-river_runs_red.png)](examples/full/vancouver-island-bc-river_runs_red.png)
[![Vancouver Island - Natural](examples/thumbnails/vancouver-island-bc-natural.png)](examples/full/vancouver-island-bc-natural.png)
[![Vancouver Island - Lava](examples/thumbnails/vancouver-island-bc-lava.png)](examples/full/vancouver-island-bc-lava.png)
[![Vancouver Island - Glacier](examples/thumbnails/vancouver-island-bc-glacier.png)](examples/full/vancouver-island-bc-glacier.png)
[![Vancouver Island - Satellite](examples/thumbnails/vancouver-island-bc-satellite.png)](examples/full/vancouver-island-bc-satellite.png)

## Customizing a Map

Each build produces two auto-generated files:

- `configs/{location}-base.yaml` — full generated config
- `configs/{location}-{scheme}-final.yaml` — final merged config (used for rendering)
- `configs/{location}-{scheme}-overlay.yaml` — your optional customizations (place here to auto-apply)

Create an overlay file named `configs/{location}-{scheme}-overlay.yaml` and place it in `configs/`. The
build detects it automatically and deep-merges it over the base config to produce the final config.

```bash
# 1. Build the map first to generate the config files
just build "Edmonton, AB" coral

# 2. Copy the current final config as your overlay starting point
cp configs/edmonton-ab-coral-final.yaml configs/edmonton-ab-coral-overlay.yaml

# 3. Edit it — change whatever you like; leave everything else as-is
vi configs/edmonton-ab-coral-overlay.yaml

# 4. Rebuild — the overlay is applied automatically
just build "Edmonton, AB" coral
```

Leaving unchanged keys in the overlay is fine — the merge just keeps the same value. The base config
is the raw generated config, while the `-final` file is the scheme-specific rendered config after
overlay merging, so it is the better starting point if you want to copy what the map is currently
using. The `{location}` is the region name lowercased with spaces and commas replaced by hyphens
(e.g. `Edmonton, AB` → `edmonton-ab`).

## Adding New Color Schemes

To create a new color scheme, simply add a new YAML file to the `schemes/` directory. Each color
scheme defines styling for all map layers (terrain, hillshade, water, roads, buildings, etc.),
including colors, visibility, opacity, line weights, and more.

The easiest approach is to copy an existing scheme file (e.g., `coral.yaml`, `natural.yaml`,
`glacier.yaml`) as a starting point, rename it, and modify the colors and settings to your liking:

```bash
# Copy an existing scheme as a template
cp schemes/coral.yaml schemes/my_scheme.yaml

# Edit the new scheme file
vi schemes/my_scheme.yaml

# The scheme is now available immediately
just build "Location" my_scheme
```

The scheme file should contain a YAML structure with `map` and layer-specific settings. For example:

```yaml
map:
  background:
    fc: '#ffffff'
    ec: '#ffffff'
  scheme: my_scheme
  # ... terrain, hillshade, satellite settings
water:
  fc: '#0000ff'
  ec: '#0000ff'
  alpha: 1.0
  # ... other water settings
# ... other layers (waterway, road, building, etc.)
```

After adding your YAML file to `schemes/`, the new color scheme is automatically discovered and can
be used in builds without any code changes.

## Ocean Data

For coastal regions, the pipeline can derive an ocean layer from the **World Seas (IHO Sea Areas)**
dataset. Download `World_Seas_IHO_v3.zip` from
[marineregions.org/downloads.php](https://www.marineregions.org/downloads.php), extract it, and
place the files into `downloads/ocean-boundaries/`. The build will skip ocean processing silently if
this directory is absent.

## Project Structure

```text
schemes/                     # Color scheme definitions (YAML files)
  coral.yaml                 # Coral color scheme
  natural.yaml               # Natural color scheme
  # ... other schemes

downloads/
  regions/                  # Per-region data (auto-downloaded)
    edmonton-ab/
      area.geojson           # Boundary polygon
      dem.tif                # Digital elevation model
      satellite.tif          # Satellite imagery
      layers/*.gpkg          # Vector layers (roads, water, etc.)
  ocean-boundaries/          # IHO World Seas source (manual download)

configs/                     # Base configs and optional overlays
output/                      # Rendered maps
cache/                       # OSM query cache (safe to delete)
scripts/                     # Pipeline scripts
```

## Cache

OSM query responses are cached in `cache/`. It can be deleted at any time to force fresh downloads.

## Author

Created by Paul Stothard.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
