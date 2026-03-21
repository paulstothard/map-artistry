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

### How Data Is Selected

The map pipeline chooses data sources dynamically from the estimated buffered area (`tier`). This
controls DEM source, satellite zoom, and vector layer source.

| Tier      |            Area (km²) | DEM source   | Satellite zoom | Vector layer source |
| --------- | --------------------: | ------------ | -------------: | ------------------- |
| city      |            `< 10,000` | `copernicus` |           `12` | `osm`               |
| region    |    `10,000 - 100,000` | `srtm`       |            `9` | `osm`               |
| country   | `100,000 - 1,000,000` | `cop90`      |            `8` | `natural-earth`     |
| continent |        `>= 1,000,000` | `etopo1`     |            `6` | `natural-earth`     |

Default buffer size also scales by area (`5`, `50`, `100`, `200` km), unless you set `--buffer-km`.

Color schemes control layer visibility/opacity and styling in `schemes/*.yaml`. See the Color
Schemes section below for details on each scheme. You can always override any defaults via
per-location overlay configs.

## Color Schemes

Listed in the same order as each example image row.

- `blueprint` — blue-tinted terrain with dark blue water; shows roads, buildings, railways, with
  subtle natural/land use layers
- `coral` — red-toned terrain, white water; hides natural and land use layers
- `dark_relief` — dramatic grayscale relief with black background/water; shows waterways only, hides
  roads, buildings, natural, and land use layers
- `etched` — high-contrast engraved style with cream background/water; shows waterways only, hides
  roads, buildings, natural, and land use layers
- `glacier` — cool grey-green terrain, blue-grey water; hides roads, buildings, and land use layers
- `lava` — fiery terrain, orange water; hides roads, buildings, and land use layers
- `minimal_white` — minimalist light style with white/cream background/water; shows waterways only,
  hides roads, buildings, natural, and land use layers
- `natural` — green→brown→grey→white terrain, blue water; hides roads, buildings, and land use
  layers
- `neon_cyber` — sci-fi cyan/neon blue with black background; shows waterways only, hides roads,
  buildings, natural, and land use layers
- `porcelain_ink` — delicate Chinese porcelain style with subtle blue water; shows roads, buildings,
  natural, and waterways
- `river_runs_red` — dark red/black terrain, red water; hides natural and land use layers
- `satellite` — satellite imagery base with vector/map overlays; hides natural and land use layers
- `sepia_vintage` — warm sepia/brown vintage style with tan background/water; shows waterways only,
  hides roads, buildings, natural, and land use layers

**Layer types:** natural (forests, wetlands, beaches, etc.), land use (urban areas), roads (street
network), buildings (footprints), water/waterway (bodies of water and streams).

## Examples

These README examples are reduced-resolution previews (`400×400` thumbnails linking to `1200×1200`
images); for full-detail output, increase build settings (default `24" × 24" @ 600 DPI` is about
`14400×14400`) and use `--format pdf` if needed.

### Resolution Example (Edmonton, River Runs Red)

Left: standard full-map preview thumbnail. Right: crop-first detail preview thumbnail from the same
render, used to highlight local detail.

[![Edmonton - River Runs Red (Full Map)](examples/thumbnails/edmonton-ab-river_runs_red.png)](examples/full/edmonton-ab-river_runs_red.png)
[![Edmonton - River Runs Red (Detail View)](examples/thumbnails/edmonton-ab-river_runs_red-detail.png)](examples/full/edmonton-ab-river_runs_red-detail.png)

### Banff, AB

[![Banff - Blueprint](examples/thumbnails/banff-ab-blueprint.png)](examples/full/banff-ab-blueprint.png)
[![Banff - Coral](examples/thumbnails/banff-ab-coral.png)](examples/full/banff-ab-coral.png)
[![Banff - Dark Relief](examples/thumbnails/banff-ab-dark_relief.png)](examples/full/banff-ab-dark_relief.png)
[![Banff - Etched](examples/thumbnails/banff-ab-etched.png)](examples/full/banff-ab-etched.png)
[![Banff - Glacier](examples/thumbnails/banff-ab-glacier.png)](examples/full/banff-ab-glacier.png)
[![Banff - Lava](examples/thumbnails/banff-ab-lava.png)](examples/full/banff-ab-lava.png)
[![Banff - Minimal White](examples/thumbnails/banff-ab-minimal_white.png)](examples/full/banff-ab-minimal_white.png)
[![Banff - Natural](examples/thumbnails/banff-ab-natural.png)](examples/full/banff-ab-natural.png)
[![Banff - Neon Cyber](examples/thumbnails/banff-ab-neon_cyber.png)](examples/full/banff-ab-neon_cyber.png)
[![Banff - Porcelain Ink](examples/thumbnails/banff-ab-porcelain_ink.png)](examples/full/banff-ab-porcelain_ink.png)
[![Banff - River Runs Red](examples/thumbnails/banff-ab-river_runs_red.png)](examples/full/banff-ab-river_runs_red.png)
[![Banff - Satellite](examples/thumbnails/banff-ab-satellite.png)](examples/full/banff-ab-satellite.png)
[![Banff - Sepia Vintage](examples/thumbnails/banff-ab-sepia_vintage.png)](examples/full/banff-ab-sepia_vintage.png)

### British Columbia

[![British Columbia - Blueprint](examples/thumbnails/british-columbia-blueprint.png)](examples/full/british-columbia-blueprint.png)
[![British Columbia - Coral](examples/thumbnails/british-columbia-coral.png)](examples/full/british-columbia-coral.png)
[![British Columbia - Dark Relief](examples/thumbnails/british-columbia-dark_relief.png)](examples/full/british-columbia-dark_relief.png)
[![British Columbia - Etched](examples/thumbnails/british-columbia-etched.png)](examples/full/british-columbia-etched.png)
[![British Columbia - Glacier](examples/thumbnails/british-columbia-glacier.png)](examples/full/british-columbia-glacier.png)
[![British Columbia - Lava](examples/thumbnails/british-columbia-lava.png)](examples/full/british-columbia-lava.png)
[![British Columbia - Minimal White](examples/thumbnails/british-columbia-minimal_white.png)](examples/full/british-columbia-minimal_white.png)
[![British Columbia - Natural](examples/thumbnails/british-columbia-natural.png)](examples/full/british-columbia-natural.png)
[![British Columbia - Neon Cyber](examples/thumbnails/british-columbia-neon_cyber.png)](examples/full/british-columbia-neon_cyber.png)
[![British Columbia - Porcelain Ink](examples/thumbnails/british-columbia-porcelain_ink.png)](examples/full/british-columbia-porcelain_ink.png)
[![British Columbia - River Runs Red](examples/thumbnails/british-columbia-river_runs_red.png)](examples/full/british-columbia-river_runs_red.png)
[![British Columbia - Satellite](examples/thumbnails/british-columbia-satellite.png)](examples/full/british-columbia-satellite.png)
[![British Columbia - Sepia Vintage](examples/thumbnails/british-columbia-sepia_vintage.png)](examples/full/british-columbia-sepia_vintage.png)

### Cape Town, South Africa

[![Cape Town - Blueprint](examples/thumbnails/cape-town-south-africa-blueprint.png)](examples/full/cape-town-south-africa-blueprint.png)
[![Cape Town - Coral](examples/thumbnails/cape-town-south-africa-coral.png)](examples/full/cape-town-south-africa-coral.png)
[![Cape Town - Dark Relief](examples/thumbnails/cape-town-south-africa-dark_relief.png)](examples/full/cape-town-south-africa-dark_relief.png)
[![Cape Town - Etched](examples/thumbnails/cape-town-south-africa-etched.png)](examples/full/cape-town-south-africa-etched.png)
[![Cape Town - Glacier](examples/thumbnails/cape-town-south-africa-glacier.png)](examples/full/cape-town-south-africa-glacier.png)
[![Cape Town - Lava](examples/thumbnails/cape-town-south-africa-lava.png)](examples/full/cape-town-south-africa-lava.png)
[![Cape Town - Minimal White](examples/thumbnails/cape-town-south-africa-minimal_white.png)](examples/full/cape-town-south-africa-minimal_white.png)
[![Cape Town - Natural](examples/thumbnails/cape-town-south-africa-natural.png)](examples/full/cape-town-south-africa-natural.png)
[![Cape Town - Neon Cyber](examples/thumbnails/cape-town-south-africa-neon_cyber.png)](examples/full/cape-town-south-africa-neon_cyber.png)
[![Cape Town - Porcelain Ink](examples/thumbnails/cape-town-south-africa-porcelain_ink.png)](examples/full/cape-town-south-africa-porcelain_ink.png)
[![Cape Town - River Runs Red](examples/thumbnails/cape-town-south-africa-river_runs_red.png)](examples/full/cape-town-south-africa-river_runs_red.png)
[![Cape Town - Satellite](examples/thumbnails/cape-town-south-africa-satellite.png)](examples/full/cape-town-south-africa-satellite.png)
[![Cape Town - Sepia Vintage](examples/thumbnails/cape-town-south-africa-sepia_vintage.png)](examples/full/cape-town-south-africa-sepia_vintage.png)

### Edmonton, AB

[![Edmonton - Blueprint](examples/thumbnails/edmonton-ab-blueprint.png)](examples/full/edmonton-ab-blueprint.png)
[![Edmonton - Coral](examples/thumbnails/edmonton-ab-coral.png)](examples/full/edmonton-ab-coral.png)
[![Edmonton - Dark Relief](examples/thumbnails/edmonton-ab-dark_relief.png)](examples/full/edmonton-ab-dark_relief.png)
[![Edmonton - Etched](examples/thumbnails/edmonton-ab-etched.png)](examples/full/edmonton-ab-etched.png)
[![Edmonton - Glacier](examples/thumbnails/edmonton-ab-glacier.png)](examples/full/edmonton-ab-glacier.png)
[![Edmonton - Lava](examples/thumbnails/edmonton-ab-lava.png)](examples/full/edmonton-ab-lava.png)
[![Edmonton - Minimal White](examples/thumbnails/edmonton-ab-minimal_white.png)](examples/full/edmonton-ab-minimal_white.png)
[![Edmonton - Natural](examples/thumbnails/edmonton-ab-natural.png)](examples/full/edmonton-ab-natural.png)
[![Edmonton - Neon Cyber](examples/thumbnails/edmonton-ab-neon_cyber.png)](examples/full/edmonton-ab-neon_cyber.png)
[![Edmonton - Porcelain Ink](examples/thumbnails/edmonton-ab-porcelain_ink.png)](examples/full/edmonton-ab-porcelain_ink.png)
[![Edmonton - River Runs Red](examples/thumbnails/edmonton-ab-river_runs_red.png)](examples/full/edmonton-ab-river_runs_red.png)
[![Edmonton - Satellite](examples/thumbnails/edmonton-ab-satellite.png)](examples/full/edmonton-ab-satellite.png)
[![Edmonton - Sepia Vintage](examples/thumbnails/edmonton-ab-sepia_vintage.png)](examples/full/edmonton-ab-sepia_vintage.png)

### Iceland

[![Iceland - Blueprint](examples/thumbnails/iceland-blueprint.png)](examples/full/iceland-blueprint.png)
[![Iceland - Coral](examples/thumbnails/iceland-coral.png)](examples/full/iceland-coral.png)
[![Iceland - Dark Relief](examples/thumbnails/iceland-dark_relief.png)](examples/full/iceland-dark_relief.png)
[![Iceland - Etched](examples/thumbnails/iceland-etched.png)](examples/full/iceland-etched.png)
[![Iceland - Glacier](examples/thumbnails/iceland-glacier.png)](examples/full/iceland-glacier.png)
[![Iceland - Lava](examples/thumbnails/iceland-lava.png)](examples/full/iceland-lava.png)
[![Iceland - Minimal White](examples/thumbnails/iceland-minimal_white.png)](examples/full/iceland-minimal_white.png)
[![Iceland - Natural](examples/thumbnails/iceland-natural.png)](examples/full/iceland-natural.png)
[![Iceland - Neon Cyber](examples/thumbnails/iceland-neon_cyber.png)](examples/full/iceland-neon_cyber.png)
[![Iceland - Porcelain Ink](examples/thumbnails/iceland-porcelain_ink.png)](examples/full/iceland-porcelain_ink.png)
[![Iceland - River Runs Red](examples/thumbnails/iceland-river_runs_red.png)](examples/full/iceland-river_runs_red.png)
[![Iceland - Satellite](examples/thumbnails/iceland-satellite.png)](examples/full/iceland-satellite.png)
[![Iceland - Sepia Vintage](examples/thumbnails/iceland-sepia_vintage.png)](examples/full/iceland-sepia_vintage.png)

### Oahu, HI

[![Oahu - Blueprint](examples/thumbnails/oahu-hi-blueprint.png)](examples/full/oahu-hi-blueprint.png)
[![Oahu - Coral](examples/thumbnails/oahu-hi-coral.png)](examples/full/oahu-hi-coral.png)
[![Oahu - Dark Relief](examples/thumbnails/oahu-hi-dark_relief.png)](examples/full/oahu-hi-dark_relief.png)
[![Oahu - Etched](examples/thumbnails/oahu-hi-etched.png)](examples/full/oahu-hi-etched.png)
[![Oahu - Glacier](examples/thumbnails/oahu-hi-glacier.png)](examples/full/oahu-hi-glacier.png)
[![Oahu - Lava](examples/thumbnails/oahu-hi-lava.png)](examples/full/oahu-hi-lava.png)
[![Oahu - Minimal White](examples/thumbnails/oahu-hi-minimal_white.png)](examples/full/oahu-hi-minimal_white.png)
[![Oahu - Natural](examples/thumbnails/oahu-hi-natural.png)](examples/full/oahu-hi-natural.png)
[![Oahu - Neon Cyber](examples/thumbnails/oahu-hi-neon_cyber.png)](examples/full/oahu-hi-neon_cyber.png)
[![Oahu - Porcelain Ink](examples/thumbnails/oahu-hi-porcelain_ink.png)](examples/full/oahu-hi-porcelain_ink.png)
[![Oahu - River Runs Red](examples/thumbnails/oahu-hi-river_runs_red.png)](examples/full/oahu-hi-river_runs_red.png)
[![Oahu - Satellite](examples/thumbnails/oahu-hi-satellite.png)](examples/full/oahu-hi-satellite.png)
[![Oahu - Sepia Vintage](examples/thumbnails/oahu-hi-sepia_vintage.png)](examples/full/oahu-hi-sepia_vintage.png)

### Patagonia

[![Patagonia - Blueprint](examples/thumbnails/patagonia-blueprint.png)](examples/full/patagonia-blueprint.png)
[![Patagonia - Coral](examples/thumbnails/patagonia-coral.png)](examples/full/patagonia-coral.png)
[![Patagonia - Dark Relief](examples/thumbnails/patagonia-dark_relief.png)](examples/full/patagonia-dark_relief.png)
[![Patagonia - Etched](examples/thumbnails/patagonia-etched.png)](examples/full/patagonia-etched.png)
[![Patagonia - Glacier](examples/thumbnails/patagonia-glacier.png)](examples/full/patagonia-glacier.png)
[![Patagonia - Lava](examples/thumbnails/patagonia-lava.png)](examples/full/patagonia-lava.png)
[![Patagonia - Minimal White](examples/thumbnails/patagonia-minimal_white.png)](examples/full/patagonia-minimal_white.png)
[![Patagonia - Natural](examples/thumbnails/patagonia-natural.png)](examples/full/patagonia-natural.png)
[![Patagonia - Neon Cyber](examples/thumbnails/patagonia-neon_cyber.png)](examples/full/patagonia-neon_cyber.png)
[![Patagonia - Porcelain Ink](examples/thumbnails/patagonia-porcelain_ink.png)](examples/full/patagonia-porcelain_ink.png)
[![Patagonia - River Runs Red](examples/thumbnails/patagonia-river_runs_red.png)](examples/full/patagonia-river_runs_red.png)
[![Patagonia - Satellite](examples/thumbnails/patagonia-satellite.png)](examples/full/patagonia-satellite.png)
[![Patagonia - Sepia Vintage](examples/thumbnails/patagonia-sepia_vintage.png)](examples/full/patagonia-sepia_vintage.png)

### San Francisco, CA

[![San Francisco - Blueprint](examples/thumbnails/san-francisco-ca-blueprint.png)](examples/full/san-francisco-ca-blueprint.png)
[![San Francisco - Coral](examples/thumbnails/san-francisco-ca-coral.png)](examples/full/san-francisco-ca-coral.png)
[![San Francisco - Dark Relief](examples/thumbnails/san-francisco-ca-dark_relief.png)](examples/full/san-francisco-ca-dark_relief.png)
[![San Francisco - Etched](examples/thumbnails/san-francisco-ca-etched.png)](examples/full/san-francisco-ca-etched.png)
[![San Francisco - Glacier](examples/thumbnails/san-francisco-ca-glacier.png)](examples/full/san-francisco-ca-glacier.png)
[![San Francisco - Lava](examples/thumbnails/san-francisco-ca-lava.png)](examples/full/san-francisco-ca-lava.png)
[![San Francisco - Minimal White](examples/thumbnails/san-francisco-ca-minimal_white.png)](examples/full/san-francisco-ca-minimal_white.png)
[![San Francisco - Natural](examples/thumbnails/san-francisco-ca-natural.png)](examples/full/san-francisco-ca-natural.png)
[![San Francisco - Neon Cyber](examples/thumbnails/san-francisco-ca-neon_cyber.png)](examples/full/san-francisco-ca-neon_cyber.png)
[![San Francisco - Porcelain Ink](examples/thumbnails/san-francisco-ca-porcelain_ink.png)](examples/full/san-francisco-ca-porcelain_ink.png)
[![San Francisco - River Runs Red](examples/thumbnails/san-francisco-ca-river_runs_red.png)](examples/full/san-francisco-ca-river_runs_red.png)
[![San Francisco - Satellite](examples/thumbnails/san-francisco-ca-satellite.png)](examples/full/san-francisco-ca-satellite.png)
[![San Francisco - Sepia Vintage](examples/thumbnails/san-francisco-ca-sepia_vintage.png)](examples/full/san-francisco-ca-sepia_vintage.png)

### Vancouver, BC

[![Vancouver - Blueprint](examples/thumbnails/vancouver-bc-blueprint.png)](examples/full/vancouver-bc-blueprint.png)
[![Vancouver - Coral](examples/thumbnails/vancouver-bc-coral.png)](examples/full/vancouver-bc-coral.png)
[![Vancouver - Dark Relief](examples/thumbnails/vancouver-bc-dark_relief.png)](examples/full/vancouver-bc-dark_relief.png)
[![Vancouver - Etched](examples/thumbnails/vancouver-bc-etched.png)](examples/full/vancouver-bc-etched.png)
[![Vancouver - Glacier](examples/thumbnails/vancouver-bc-glacier.png)](examples/full/vancouver-bc-glacier.png)
[![Vancouver - Lava](examples/thumbnails/vancouver-bc-lava.png)](examples/full/vancouver-bc-lava.png)
[![Vancouver - Minimal White](examples/thumbnails/vancouver-bc-minimal_white.png)](examples/full/vancouver-bc-minimal_white.png)
[![Vancouver - Natural](examples/thumbnails/vancouver-bc-natural.png)](examples/full/vancouver-bc-natural.png)
[![Vancouver - Neon Cyber](examples/thumbnails/vancouver-bc-neon_cyber.png)](examples/full/vancouver-bc-neon_cyber.png)
[![Vancouver - Porcelain Ink](examples/thumbnails/vancouver-bc-porcelain_ink.png)](examples/full/vancouver-bc-porcelain_ink.png)
[![Vancouver - River Runs Red](examples/thumbnails/vancouver-bc-river_runs_red.png)](examples/full/vancouver-bc-river_runs_red.png)
[![Vancouver - Satellite](examples/thumbnails/vancouver-bc-satellite.png)](examples/full/vancouver-bc-satellite.png)
[![Vancouver - Sepia Vintage](examples/thumbnails/vancouver-bc-sepia_vintage.png)](examples/full/vancouver-bc-sepia_vintage.png)

### Vancouver Island, BC

[![Vancouver Island - Blueprint](examples/thumbnails/vancouver-island-bc-blueprint.png)](examples/full/vancouver-island-bc-blueprint.png)
[![Vancouver Island - Coral](examples/thumbnails/vancouver-island-bc-coral.png)](examples/full/vancouver-island-bc-coral.png)
[![Vancouver Island - Dark Relief](examples/thumbnails/vancouver-island-bc-dark_relief.png)](examples/full/vancouver-island-bc-dark_relief.png)
[![Vancouver Island - Etched](examples/thumbnails/vancouver-island-bc-etched.png)](examples/full/vancouver-island-bc-etched.png)
[![Vancouver Island - Glacier](examples/thumbnails/vancouver-island-bc-glacier.png)](examples/full/vancouver-island-bc-glacier.png)
[![Vancouver Island - Lava](examples/thumbnails/vancouver-island-bc-lava.png)](examples/full/vancouver-island-bc-lava.png)
[![Vancouver Island - Minimal White](examples/thumbnails/vancouver-island-bc-minimal_white.png)](examples/full/vancouver-island-bc-minimal_white.png)
[![Vancouver Island - Natural](examples/thumbnails/vancouver-island-bc-natural.png)](examples/full/vancouver-island-bc-natural.png)
[![Vancouver Island - Neon Cyber](examples/thumbnails/vancouver-island-bc-neon_cyber.png)](examples/full/vancouver-island-bc-neon_cyber.png)
[![Vancouver Island - Porcelain Ink](examples/thumbnails/vancouver-island-bc-porcelain_ink.png)](examples/full/vancouver-island-bc-porcelain_ink.png)
[![Vancouver Island - River Runs Red](examples/thumbnails/vancouver-island-bc-river_runs_red.png)](examples/full/vancouver-island-bc-river_runs_red.png)
[![Vancouver Island - Satellite](examples/thumbnails/vancouver-island-bc-satellite.png)](examples/full/vancouver-island-bc-satellite.png)
[![Vancouver Island - Sepia Vintage](examples/thumbnails/vancouver-island-bc-sepia_vintage.png)](examples/full/vancouver-island-bc-sepia_vintage.png)

### Vestland, Norway

[![Vestland - Blueprint](examples/thumbnails/vestland-norway-blueprint.png)](examples/full/vestland-norway-blueprint.png)
[![Vestland - Coral](examples/thumbnails/vestland-norway-coral.png)](examples/full/vestland-norway-coral.png)
[![Vestland - Dark Relief](examples/thumbnails/vestland-norway-dark_relief.png)](examples/full/vestland-norway-dark_relief.png)
[![Vestland - Etched](examples/thumbnails/vestland-norway-etched.png)](examples/full/vestland-norway-etched.png)
[![Vestland - Glacier](examples/thumbnails/vestland-norway-glacier.png)](examples/full/vestland-norway-glacier.png)
[![Vestland - Lava](examples/thumbnails/vestland-norway-lava.png)](examples/full/vestland-norway-lava.png)
[![Vestland - Minimal White](examples/thumbnails/vestland-norway-minimal_white.png)](examples/full/vestland-norway-minimal_white.png)
[![Vestland - Natural](examples/thumbnails/vestland-norway-natural.png)](examples/full/vestland-norway-natural.png)
[![Vestland - Neon Cyber](examples/thumbnails/vestland-norway-neon_cyber.png)](examples/full/vestland-norway-neon_cyber.png)
[![Vestland - Porcelain Ink](examples/thumbnails/vestland-norway-porcelain_ink.png)](examples/full/vestland-norway-porcelain_ink.png)
[![Vestland - River Runs Red](examples/thumbnails/vestland-norway-river_runs_red.png)](examples/full/vestland-norway-river_runs_red.png)
[![Vestland - Satellite](examples/thumbnails/vestland-norway-satellite.png)](examples/full/vestland-norway-satellite.png)
[![Vestland - Sepia Vintage](examples/thumbnails/vestland-norway-sepia_vintage.png)](examples/full/vestland-norway-sepia_vintage.png)

## Customizing a Map

Each build produces two auto-generated files:

- `configs/{location}-base.yaml` — full generated config
- `configs/{location}-{scheme}-final.yaml` — final merged config (used for rendering)
- `configs/{location}-{scheme}-overlay.yaml` — your optional customizations (place here to
  auto-apply)

Create an overlay file named `configs/{location}-{scheme}-overlay.yaml` and place it in `configs/`.
The build detects it automatically and deep-merges it over the base config to produce the final
config.

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
    fc: "#ffffff"
    ec: "#ffffff"
  scheme: my_scheme
  # ... terrain, hillshade, satellite settings
water:
  fc: "#0000ff"
  ec: "#0000ff"
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
