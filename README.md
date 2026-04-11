# map-artistry

Artistic topographic and GPX route map generator using OpenStreetMap, satellite imagery, and digital elevation models. Generates high-resolution, stylized region maps and route-overlay maps via a customizable pipeline.

<table align="center">
  <tr>
    <td width="50%">
      <img src="examples/full/iceland-natural.png" width="100%" alt="Iceland - Natural Style">
    </td>
    <td width="50%">
      <img src="examples/full/boston-emerald-necklace-bicycle-adventure-neon_cyber.png" width="100%" alt="Boston Emerald Necklace - Neon Cyber Style">
    </td>
  </tr>
</table>

> **See [EXAMPLES.md](EXAMPLES.md) for a full gallery of example maps across all color schemes and locations.**

## Dependencies

- [just](https://github.com/casey/just) 1.47.0 or newer — command runner (`brew install just` on macOS)
- Python 3
- **Inter font** — required for text rendering on maps

## Getting Started

First, download or clone the repository and switch to the project directory:

```bash
git clone https://github.com/paulstothard/map-artistry.git
cd map-artistry
```

Then proceed with the setup steps below.

## Setup

### 1. Install Inter Font

**macOS:**

```bash
brew install --cask font-inter
```

**Linux:**

```bash
# Download from Google Fonts
wget https://fonts.google.com/download?family=Inter -O inter.zip
unzip inter.zip -d inter
sudo mkdir -p /usr/share/fonts/truetype/inter
sudo cp inter/*.ttf /usr/share/fonts/truetype/inter/
fc-cache -f -v
```

**Windows:**

1. Download Inter from [Google Fonts](https://fonts.google.com/specimen/Inter)
2. Extract the zip file
3. Right-click on each `.ttf` file and select "Install"

**Verify installation:**

```bash
fc-list | grep -i inter
```

### 2. Install Python Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Optional: Configure OpenTopography API Key (Recommended)

For country-scale DEM downloads (`cop90`), the project calls the OpenTopography Global DEM API.

The code supports two modes:

- **Personal key** via `OPENTOPOGRAPHY_API_KEY` (recommended)
- **Built-in demo key fallback** (shared and rate-limited)

Get a personal key:

1. Create or sign in to your account at [OpenTopography](https://opentopography.org)
2. Generate an API key in your account/API settings

Set it in your shell (current session):

```bash
export OPENTOPOGRAPHY_API_KEY="your_key_here"
```

Persist it on macOS/Linux (zsh):

```bash
echo 'export OPENTOPOGRAPHY_API_KEY="your_key_here"' >> ~/.zshrc
source ~/.zshrc
```

If `OPENTOPOGRAPHY_API_KEY` is not set, map-artistry falls back to the public demo key supplied by OpenTopography. The demo key is shared across users and can hit daily quota limits.

### 4. Understanding the Workspace Structure

The project separates code from data using two directories:

- **`examples/`** — pre-configured example maps with their configs and outputs (tracked in Git)
- **`user/`** — your personal workspace for creating custom maps (ignored by Git)

Both directories have the same structure: `cache/`, `configs/`, `downloads/`, and `output/`.

**By default, `just` commands use the `user/` workspace.** When you run `just build "City Name" scheme`, all configs, outputs, downloads, and cache files go to `user/configs/`, `user/output/`, `user/downloads/`, and `user/cache/`.

The examples workspace is only used when running `./generate-example-maps.sh`, which sets the workspace to `examples/` automatically.

### 5. Optional: Install Ocean Boundaries Data (Recommended for Coastal Maps)

For coastal regions, the pipeline can add an ocean layer from the **World Seas (IHO Sea Areas)** dataset.

1. Download `World_Seas_IHO_v3.zip` from [marineregions.org/downloads.php](https://www.marineregions.org/downloads.php)
2. Extract the zip
3. Put the extracted files in:

`ocean-boundaries/`

That repo-level path is the required setup and works for both:

- normal maps in the default `user/` workspace
- example-map generation in the `examples/` workspace

You only need one copy of the dataset.

### 6. Optional: Portable Justfile Usage

You can copy [justfile](justfile) elsewhere and point it back to this repository using environment variables:

```bash
# Copy justfile to your custom workspace
cp justfile ~/my-maps/
cd ~/my-maps

# Set the repo location and workspace
export MAP_ARTISTRY_REPO="/Users/yourusername/map-artistry"
export WORKSPACE_DIR="$PWD"

# Now run just commands from your custom location
just build "San Francisco, CA" coral
```

This creates all configs and outputs in your current directory while using the scripts and schemes from the repository.

**Environment variables:**

- `MAP_ARTISTRY_REPO` — path to the cloned repository (defaults to the directory containing justfile)
- `WORKSPACE_DIR` — path to your workspace directory (defaults to `user/` within the repo)

## Usage

### Standard Maps

```bash
# Build a map with default settings (24" × 24" @ 300 DPI, PNG format)
just build "Edmonton, AB" coral

# Build with a different location and color scheme
just build "Vancouver Island, BC" natural

# Build with custom dimensions
just build --width 36 --height 24 "Iceland" river_runs_red

# Build with custom dimensions, DPI, format, and boundary buffer
just build --width 24 --height 24 --dpi 300 --format png --buffer-km 20 "Victoria, BC" natural

# Build with title and subtitle panel
just build --text-title "VICTORIA" --text-subtitle "BRITISH COLUMBIA" "Victoria, BC" natural

# Build with title, subtitle, and custom stats
just build --text-title "SAN FRANCISCO" --text-subtitle "CALIFORNIA" --text-stats "37.77°N||LATITUDE;;122.42°W||LONGITUDE" "San Francisco, CA" coral

# Save output to a custom folder
just build --output-dir my-maps "Edmonton, AB" coral

# List available color schemes
just schemes
```

### Route Maps

Route maps overlay a GPX track on the map and optionally display a stats panel with title, subtitle, and custom metrics.

**Region + GPX route** — the map region is defined by a place name, with the GPX track drawn on top:

```bash
just build-route "Edmonton, AB" ./my-ride.gpx coral

# With a stats panel
just build-route \
  --text-title "EDMONTON LOOP" \
  --text-subtitle "SUMMER TRAINING RIDE" \
  --text-stats "94 KM||DISTANCE;;800 M||ELEV GAIN" \
  "Edmonton, AB" ./my-ride.gpx coral
```

**GPX-derived route** — the map region is derived automatically from the GPX track bounding box, no place name required:

```bash
just build-gpx ./my-ride.gpx coral

# With a stats panel
just build-gpx \
  --text-title "RIVER VALLEY LOOP" \
  --text-subtitle "GPX-DERIVED REGION" \
  --text-stats "64 KM||DISTANCE;;530 M||ELEV GAIN" \
  ./my-ride.gpx coral
```

All settings (boundary padding, DEM source, satellite zoom, layer source) are calculated automatically based on region size. Use `--buffer-km` to override the automatic extra distance added around the region boundary, in kilometers.

### Generating All Color Schemes

Generate all 16 color schemes for a region and create a labeled montage for inspection or comparison:

```bash
# Generate all color schemes for Wellington, New Zealand
just build-all-schemes "Wellington, New Zealand"

# Create a montage with automatic layout and scheme labels
# Requires the maps generated by build-all-schemes above
just create-montage user/output wellington-montage.png --cols auto --add-labels true --pattern "wellington-new-zealand-*"

# Or with custom columns and spacing
# Requires the maps generated by build-all-schemes above
just create-montage user/output wellington-4x4.png --cols 4 --spacing 20 --add-labels true --pattern "wellington-new-zealand-*"
```

The `--cols auto` option automatically calculates the optimal grid layout based on the number of images. The `--pattern` option filters which images to include (e.g., `"wellington-new-zealand-*"` for all Wellington maps, `"*-natural"` for all natural scheme maps). You can also generate all schemes for routes:

```bash
# Generate all schemes for a route
just build-all-route-schemes "Boston, MA" downloads/my-route.gpx

# Or for GPX-derived regions
just build-all-gpx-schemes downloads/my-route.gpx
```

### Manifest-Based Montage Script

Use `montage.py` when you want to build a mixed grid of panels (region maps, region+route maps, and GPX-derived route maps) from one CSV manifest.

```bash
# Build a montage from the manifest
./montage.py --manifest montage-manifest.csv

# Dry-run the panel plan without rendering
./montage.py --manifest montage-manifest.csv --dry-run

# Custom layout + output
./montage.py \
  --manifest montage-manifest.csv \
  --cols 3 \
  --spacing-px 24 \
  --canvas-color "#f4f1ea" \
  --final-width-in 36 \
  --final-height-in 24 \
  --final-dpi 300
```

Key options:

- `--manifest`: CSV input file (required)
- `--cols`: grid columns (`auto` or a number)
- `--spacing-px`: spacing between panels
- `--canvas-color`: background color for spacing/letterbox areas
- `--output`: final montage file path
- `--maps-dir`: where intermediate panel renders are written
- `--dry-run`: print plan only

If `--output` is not provided, the script writes to the active workspace output directory as `montage-<run-name>.png`.

### Text Panels

All map types (`build`, `build-route`, and `build-gpx`) support optional text panels with title, subtitle, location, and custom statistics. Use the `--text-title`, `--text-subtitle`, `--text-location`, and `--text-stats` flags to add a styled info panel to your map. Stats use the format `VALUE||LABEL` with `;;` as a separator between multiple stats (e.g., `"94 KM||DISTANCE;;800 M||ELEV GAIN"`).

Route maps can derive distance metrics from the GPX track, while standard maps work well with custom stats like coordinates, elevation, area, or any other relevant information about the location.

### How Data Is Selected

The map pipeline chooses data sources dynamically from the estimated buffered area (`tier`). This controls DEM source, satellite zoom, and vector layer source.

| Tier      |            Area (km²) | DEM source   | Satellite zoom | Vector layer source |
| --------- | --------------------: | ------------ | -------------: | ------------------- |
| city      |            `< 10,000` | `copernicus` |           `12` | `osm`               |
| region    |    `10,000 - 100,000` | `srtm`       |            `9` | `osm`               |
| country   | `100,000 - 1,000,000` | `cop90`      |            `8` | `natural-earth`     |
| continent |        `>= 1,000,000` | `etopo1`     |            `6` | `natural-earth`     |

Default buffer size also scales by area (`5`, `50`, `100`, `200` km), unless you set `--buffer-km`.

Color schemes control layer visibility/opacity and styling in `schemes/*.yaml`. See the Color Schemes section below for details on each scheme. You can always override any defaults via per-location overlay configs.

## Color Schemes

Available color schemes (listed alphabetically):

`blueprint` • `burgundy` • `copper` • `coral` • `glacier` • `lava` • `minimal_white` • `natural` • `neon_cyber` • `night` • `porcelain_ink` • `river_runs_red` • `satellite` • `sepia_vintage` • `slate` • `yellow`

Each scheme controls layer visibility, colors, hillshade, and terrain rendering. See `schemes/*.yaml` for full configuration details.

## Examples

See [EXAMPLES.md](EXAMPLES.md) for the full gallery of example maps across all color schemes and locations.

## Customizing a Map

Each build produces two auto-generated files in your workspace:

- `user/configs/{location}-base.yaml` — full generated config
- `user/configs/{location}-{scheme}-final.yaml` — final merged config (used for rendering)
- `user/configs/{location}-{scheme}-overlay.yaml` — your optional customizations (place here to auto-apply)

Create an overlay file named `user/configs/{location}-{scheme}-overlay.yaml` in your workspace. The build detects it automatically and deep-merges it over the base config to produce the final config.

```bash
# 1. Build the map first to generate the config files
just build "Edmonton, AB" coral

# 2. Copy the current final config as your overlay starting point
cp user/configs/edmonton-ab-coral-final.yaml user/configs/edmonton-ab-coral-overlay.yaml

# 3. Edit it — change whatever you like; leave everything else as-is
vi user/configs/edmonton-ab-coral-overlay.yaml

# 4. Rebuild — the overlay is applied automatically
just build "Edmonton, AB" coral
```

Leaving unchanged keys in the overlay is fine — the merge just keeps the same value. The base config is the raw generated config, while the `-final` file is the scheme-specific rendered config after overlay merging, so it is the better starting point if you want to copy what the map is currently using. The `{location}` is the region name lowercased with spaces and commas replaced by hyphens (e.g. `Edmonton, AB` → `edmonton-ab`).

## Adding New Color Schemes

To create a new color scheme, simply add a new YAML file to the `schemes/` directory. Each color scheme defines styling for all map layers (terrain, hillshade, water, roads, buildings, etc.), including colors, visibility, opacity, line weights, and more.

The easiest approach is to copy an existing scheme file (e.g., `coral.yaml`, `natural.yaml`, `glacier.yaml`) as a starting point, rename it, and modify the colors and settings to your liking:

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

After adding your YAML file to `schemes/`, the new color scheme is automatically discovered and can be used in builds without any code changes.

## Project Structure

```text
map-artistry/
  generate-example-maps.sh   # Script to regenerate all example maps
  justfile                   # just task runner recipes
  montage-manifest.csv       # Manifest for montage generation
  montage.py                 # Montage assembly script
  requirements.txt           # Python dependencies

  ocean-boundaries/          # IHO World Seas shapefile data (not included; download separately — see setup instructions)
    World_Seas_IHO_v3.*      # Shapefile components (.shp, .dbf, .prj, etc.)
    LICENSE_IHO_v3.txt

  schemes/                   # Color scheme definitions (YAML)
    blueprint.yaml
    burgundy.yaml
    copper.yaml
    coral.yaml
    glacier.yaml
    lava.yaml
    minimal_white.yaml
    natural.yaml
    neon_cyber.yaml
    night.yaml
    porcelain_ink.yaml
    river_runs_red.yaml
    satellite.yaml
    sepia_vintage.yaml
    slate.yaml
    yellow.yaml

  scripts/                   # Pipeline scripts
    add-image-label.py
    analyze-route-context.py
    calculate-area.py
    create-image-montage.py
    create-pdf-from-images.py
    download-dem.py
    download-geojson.py
    download-osm-layers.py
    download-satellite-image.py
    generate-config.py
    generate-map.py
    geojson_bounds.py
    merge-config.py
    prepare-ocean-layer.py
    redact-gpx-start-end.py
    resize-images.py
    smart-publish-images.py
    validate-geojson.py

  examples/                  # Example maps workspace
    cache/                   # Cached OSM query responses
    configs/                 # Example map config files
    downloads/               # Downloaded data for example maps
    full/                    # Full-resolution rendered maps
    gpx/                     # Example GPX route files
    output/                  # Rendered map outputs
    overlays/                # Overlay images for example maps
    publish/                 # Publication-ready image exports
    thumbnails/              # Thumbnail versions of rendered maps

  user/                      # Your personal workspace
    cache/                   # OSM query cache (safe to delete)
    configs/                 # Your map config files
    downloads/               # Downloaded data for your maps
    output/                  # Your rendered maps
```

## Cache

OSM query responses are cached in your workspace's `cache/` directory (by default `user/cache/`). The `examples/cache/` directory serves the same purpose for the bundled example maps. Both can be deleted at any time to force fresh downloads.

## Author

Created by Paul Stothard.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
