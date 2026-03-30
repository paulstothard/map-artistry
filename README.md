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

### 3. Understanding the Workspace Structure

The project separates code from data using two directories:

- **`examples/`** — pre-configured example maps with their configs and outputs (tracked in Git)
- **`user/`** — your personal workspace for creating custom maps (ignored by Git)

Both directories have the same structure: `cache/`, `configs/`, `downloads/`, and `output/`.

**By default, `just` commands use the `user/` workspace.** When you run `just build "City Name" scheme`, all configs, outputs, downloads, and cache files go to `user/configs/`, `user/output/`, `user/downloads/`, and `user/cache/`.

The examples workspace is only used when running `./generate-example-maps.sh`, which sets the workspace to `examples/` automatically.

### 4. Optional: Portable Justfile Usage

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

These README examples are `400×400` thumbnails linking to `1200×1200` full previews, rendered at `24" × 24" @ 150 DPI`. Full-resolution builds (default `300 DPI`) produce approximately `14400×14400` pixel images; use `--format pdf` for print-quality output.

### Banff, AB

<table>
  <tr>
    <td align="center">
      <a href="examples/full/banff-ab-blueprint.png"><img src="examples/thumbnails/banff-ab-blueprint.png" alt="Banff - Blueprint" width="200"></a><br>
      <sub>blueprint</sub>
    </td>
    <td align="center">
      <a href="examples/full/banff-ab-burgundy.png"><img src="examples/thumbnails/banff-ab-burgundy.png" alt="Banff - Burgundy" width="200"></a><br>
      <sub>burgundy</sub>
    </td>
    <td align="center">
      <a href="examples/full/banff-ab-copper.png"><img src="examples/thumbnails/banff-ab-copper.png" alt="Banff - Copper" width="200"></a><br>
      <sub>copper</sub>
    </td>
    <td align="center">
      <a href="examples/full/banff-ab-coral.png"><img src="examples/thumbnails/banff-ab-coral.png" alt="Banff - Coral" width="200"></a><br>
      <sub>coral</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/banff-ab-glacier.png"><img src="examples/thumbnails/banff-ab-glacier.png" alt="Banff - Glacier" width="200"></a><br>
      <sub>glacier</sub>
    </td>
    <td align="center">
      <a href="examples/full/banff-ab-lava.png"><img src="examples/thumbnails/banff-ab-lava.png" alt="Banff - Lava" width="200"></a><br>
      <sub>lava</sub>
    </td>
    <td align="center">
      <a href="examples/full/banff-ab-minimal_white.png"><img src="examples/thumbnails/banff-ab-minimal_white.png" alt="Banff - Minimal White" width="200"></a><br>
      <sub>minimal_white</sub>
    </td>
    <td align="center">
      <a href="examples/full/banff-ab-natural.png"><img src="examples/thumbnails/banff-ab-natural.png" alt="Banff - Natural" width="200"></a><br>
      <sub>natural</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/banff-ab-neon_cyber.png"><img src="examples/thumbnails/banff-ab-neon_cyber.png" alt="Banff - Neon Cyber" width="200"></a><br>
      <sub>neon_cyber</sub>
    </td>
    <td align="center">
      <a href="examples/full/banff-ab-night.png"><img src="examples/thumbnails/banff-ab-night.png" alt="Banff - Night" width="200"></a><br>
      <sub>night</sub>
    </td>
    <td align="center">
      <a href="examples/full/banff-ab-porcelain_ink.png"><img src="examples/thumbnails/banff-ab-porcelain_ink.png" alt="Banff - Porcelain Ink" width="200"></a><br>
      <sub>porcelain_ink</sub>
    </td>
    <td align="center">
      <a href="examples/full/banff-ab-river_runs_red.png"><img src="examples/thumbnails/banff-ab-river_runs_red.png" alt="Banff - River Runs Red" width="200"></a><br>
      <sub>river_runs_red</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/banff-ab-satellite.png"><img src="examples/thumbnails/banff-ab-satellite.png" alt="Banff - Satellite" width="200"></a><br>
      <sub>satellite</sub>
    </td>
    <td align="center">
      <a href="examples/full/banff-ab-sepia_vintage.png"><img src="examples/thumbnails/banff-ab-sepia_vintage.png" alt="Banff - Sepia Vintage" width="200"></a><br>
      <sub>sepia_vintage</sub>
    </td>
    <td align="center">
      <a href="examples/full/banff-ab-slate.png"><img src="examples/thumbnails/banff-ab-slate.png" alt="Banff - Slate" width="200"></a><br>
      <sub>slate</sub>
    </td>
    <td align="center">
      <a href="examples/full/banff-ab-yellow.png"><img src="examples/thumbnails/banff-ab-yellow.png" alt="Banff - Yellow" width="200"></a><br>
      <sub>yellow</sub>
    </td>
  </tr>
</table>

### British Columbia

<table>
  <tr>
    <td align="center">
      <a href="examples/full/british-columbia-blueprint.png"><img src="examples/thumbnails/british-columbia-blueprint.png" alt="British Columbia - Blueprint" width="200"></a><br>
      <sub>blueprint</sub>
    </td>
    <td align="center">
      <a href="examples/full/british-columbia-burgundy.png"><img src="examples/thumbnails/british-columbia-burgundy.png" alt="British Columbia - Burgundy" width="200"></a><br>
      <sub>burgundy</sub>
    </td>
    <td align="center">
      <a href="examples/full/british-columbia-copper.png"><img src="examples/thumbnails/british-columbia-copper.png" alt="British Columbia - Copper" width="200"></a><br>
      <sub>copper</sub>
    </td>
    <td align="center">
      <a href="examples/full/british-columbia-coral.png"><img src="examples/thumbnails/british-columbia-coral.png" alt="British Columbia - Coral" width="200"></a><br>
      <sub>coral</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/british-columbia-glacier.png"><img src="examples/thumbnails/british-columbia-glacier.png" alt="British Columbia - Glacier" width="200"></a><br>
      <sub>glacier</sub>
    </td>
    <td align="center">
      <a href="examples/full/british-columbia-lava.png"><img src="examples/thumbnails/british-columbia-lava.png" alt="British Columbia - Lava" width="200"></a><br>
      <sub>lava</sub>
    </td>
    <td align="center">
      <a href="examples/full/british-columbia-minimal_white.png"><img src="examples/thumbnails/british-columbia-minimal_white.png" alt="British Columbia - Minimal White" width="200"></a><br>
      <sub>minimal_white</sub>
    </td>
    <td align="center">
      <a href="examples/full/british-columbia-natural.png"><img src="examples/thumbnails/british-columbia-natural.png" alt="British Columbia - Natural" width="200"></a><br>
      <sub>natural</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/british-columbia-neon_cyber.png"><img src="examples/thumbnails/british-columbia-neon_cyber.png" alt="British Columbia - Neon Cyber" width="200"></a><br>
      <sub>neon_cyber</sub>
    </td>
    <td align="center">
      <a href="examples/full/british-columbia-night.png"><img src="examples/thumbnails/british-columbia-night.png" alt="British Columbia - Night" width="200"></a><br>
      <sub>night</sub>
    </td>
    <td align="center">
      <a href="examples/full/british-columbia-porcelain_ink.png"><img src="examples/thumbnails/british-columbia-porcelain_ink.png" alt="British Columbia - Porcelain Ink" width="200"></a><br>
      <sub>porcelain_ink</sub>
    </td>
    <td align="center">
      <a href="examples/full/british-columbia-river_runs_red.png"><img src="examples/thumbnails/british-columbia-river_runs_red.png" alt="British Columbia - River Runs Red" width="200"></a><br>
      <sub>river_runs_red</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/british-columbia-satellite.png"><img src="examples/thumbnails/british-columbia-satellite.png" alt="British Columbia - Satellite" width="200"></a><br>
      <sub>satellite</sub>
    </td>
    <td align="center">
      <a href="examples/full/british-columbia-sepia_vintage.png"><img src="examples/thumbnails/british-columbia-sepia_vintage.png" alt="British Columbia - Sepia Vintage" width="200"></a><br>
      <sub>sepia_vintage</sub>
    </td>
    <td align="center">
      <a href="examples/full/british-columbia-slate.png"><img src="examples/thumbnails/british-columbia-slate.png" alt="British Columbia - Slate" width="200"></a><br>
      <sub>slate</sub>
    </td>
    <td align="center">
      <a href="examples/full/british-columbia-yellow.png"><img src="examples/thumbnails/british-columbia-yellow.png" alt="British Columbia - Yellow" width="200"></a><br>
      <sub>yellow</sub>
    </td>
  </tr>
</table>

### Cape Town, South Africa

<table>
  <tr>
    <td align="center">
      <a href="examples/full/cape-town-south-africa-blueprint.png"><img src="examples/thumbnails/cape-town-south-africa-blueprint.png" alt="Cape Town - Blueprint" width="200"></a><br>
      <sub>blueprint</sub>
    </td>
    <td align="center">
      <a href="examples/full/cape-town-south-africa-burgundy.png"><img src="examples/thumbnails/cape-town-south-africa-burgundy.png" alt="Cape Town - Burgundy" width="200"></a><br>
      <sub>burgundy</sub>
    </td>
    <td align="center">
      <a href="examples/full/cape-town-south-africa-copper.png"><img src="examples/thumbnails/cape-town-south-africa-copper.png" alt="Cape Town - Copper" width="200"></a><br>
      <sub>copper</sub>
    </td>
    <td align="center">
      <a href="examples/full/cape-town-south-africa-coral.png"><img src="examples/thumbnails/cape-town-south-africa-coral.png" alt="Cape Town - Coral" width="200"></a><br>
      <sub>coral</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/cape-town-south-africa-glacier.png"><img src="examples/thumbnails/cape-town-south-africa-glacier.png" alt="Cape Town - Glacier" width="200"></a><br>
      <sub>glacier</sub>
    </td>
    <td align="center">
      <a href="examples/full/cape-town-south-africa-lava.png"><img src="examples/thumbnails/cape-town-south-africa-lava.png" alt="Cape Town - Lava" width="200"></a><br>
      <sub>lava</sub>
    </td>
    <td align="center">
      <a href="examples/full/cape-town-south-africa-minimal_white.png"><img src="examples/thumbnails/cape-town-south-africa-minimal_white.png" alt="Cape Town - Minimal White" width="200"></a><br>
      <sub>minimal_white</sub>
    </td>
    <td align="center">
      <a href="examples/full/cape-town-south-africa-natural.png"><img src="examples/thumbnails/cape-town-south-africa-natural.png" alt="Cape Town - Natural" width="200"></a><br>
      <sub>natural</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/cape-town-south-africa-neon_cyber.png"><img src="examples/thumbnails/cape-town-south-africa-neon_cyber.png" alt="Cape Town - Neon Cyber" width="200"></a><br>
      <sub>neon_cyber</sub>
    </td>
    <td align="center">
      <a href="examples/full/cape-town-south-africa-night.png"><img src="examples/thumbnails/cape-town-south-africa-night.png" alt="Cape Town - Night" width="200"></a><br>
      <sub>night</sub>
    </td>
    <td align="center">
      <a href="examples/full/cape-town-south-africa-porcelain_ink.png"><img src="examples/thumbnails/cape-town-south-africa-porcelain_ink.png" alt="Cape Town - Porcelain Ink" width="200"></a><br>
      <sub>porcelain_ink</sub>
    </td>
    <td align="center">
      <a href="examples/full/cape-town-south-africa-river_runs_red.png"><img src="examples/thumbnails/cape-town-south-africa-river_runs_red.png" alt="Cape Town - River Runs Red" width="200"></a><br>
      <sub>river_runs_red</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/cape-town-south-africa-satellite.png"><img src="examples/thumbnails/cape-town-south-africa-satellite.png" alt="Cape Town - Satellite" width="200"></a><br>
      <sub>satellite</sub>
    </td>
    <td align="center">
      <a href="examples/full/cape-town-south-africa-sepia_vintage.png"><img src="examples/thumbnails/cape-town-south-africa-sepia_vintage.png" alt="Cape Town - Sepia Vintage" width="200"></a><br>
      <sub>sepia_vintage</sub>
    </td>
    <td align="center">
      <a href="examples/full/cape-town-south-africa-slate.png"><img src="examples/thumbnails/cape-town-south-africa-slate.png" alt="Cape Town - Slate" width="200"></a><br>
      <sub>slate</sub>
    </td>
    <td align="center">
      <a href="examples/full/cape-town-south-africa-yellow.png"><img src="examples/thumbnails/cape-town-south-africa-yellow.png" alt="Cape Town - Yellow" width="200"></a><br>
      <sub>yellow</sub>
    </td>
  </tr>
</table>

### Edmonton, AB

<table>
  <tr>
    <td align="center">
      <a href="examples/full/edmonton-ab-blueprint.png"><img src="examples/thumbnails/edmonton-ab-blueprint.png" alt="Edmonton - Blueprint" width="200"></a><br>
      <sub>blueprint</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-burgundy.png"><img src="examples/thumbnails/edmonton-ab-burgundy.png" alt="Edmonton - Burgundy" width="200"></a><br>
      <sub>burgundy</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-copper.png"><img src="examples/thumbnails/edmonton-ab-copper.png" alt="Edmonton - Copper" width="200"></a><br>
      <sub>copper</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-coral.png"><img src="examples/thumbnails/edmonton-ab-coral.png" alt="Edmonton - Coral" width="200"></a><br>
      <sub>coral</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/edmonton-ab-glacier.png"><img src="examples/thumbnails/edmonton-ab-glacier.png" alt="Edmonton - Glacier" width="200"></a><br>
      <sub>glacier</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-lava.png"><img src="examples/thumbnails/edmonton-ab-lava.png" alt="Edmonton - Lava" width="200"></a><br>
      <sub>lava</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-minimal_white.png"><img src="examples/thumbnails/edmonton-ab-minimal_white.png" alt="Edmonton - Minimal White" width="200"></a><br>
      <sub>minimal_white</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-natural.png"><img src="examples/thumbnails/edmonton-ab-natural.png" alt="Edmonton - Natural" width="200"></a><br>
      <sub>natural</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/edmonton-ab-neon_cyber.png"><img src="examples/thumbnails/edmonton-ab-neon_cyber.png" alt="Edmonton - Neon Cyber" width="200"></a><br>
      <sub>neon_cyber</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-night.png"><img src="examples/thumbnails/edmonton-ab-night.png" alt="Edmonton - Night" width="200"></a><br>
      <sub>night</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-porcelain_ink.png"><img src="examples/thumbnails/edmonton-ab-porcelain_ink.png" alt="Edmonton - Porcelain Ink" width="200"></a><br>
      <sub>porcelain_ink</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-river_runs_red.png"><img src="examples/thumbnails/edmonton-ab-river_runs_red.png" alt="Edmonton - River Runs Red" width="200"></a><br>
      <sub>river_runs_red</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/edmonton-ab-satellite.png"><img src="examples/thumbnails/edmonton-ab-satellite.png" alt="Edmonton - Satellite" width="200"></a><br>
      <sub>satellite</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-sepia_vintage.png"><img src="examples/thumbnails/edmonton-ab-sepia_vintage.png" alt="Edmonton - Sepia Vintage" width="200"></a><br>
      <sub>sepia_vintage</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-slate.png"><img src="examples/thumbnails/edmonton-ab-slate.png" alt="Edmonton - Slate" width="200"></a><br>
      <sub>slate</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-yellow.png"><img src="examples/thumbnails/edmonton-ab-yellow.png" alt="Edmonton - Yellow" width="200"></a><br>
      <sub>yellow</sub>
    </td>
  </tr>
</table>

### Iceland

<table>
  <tr>
    <td align="center">
      <a href="examples/full/iceland-blueprint.png"><img src="examples/thumbnails/iceland-blueprint.png" alt="Iceland - Blueprint" width="200"></a><br>
      <sub>blueprint</sub>
    </td>
    <td align="center">
      <a href="examples/full/iceland-burgundy.png"><img src="examples/thumbnails/iceland-burgundy.png" alt="Iceland - Burgundy" width="200"></a><br>
      <sub>burgundy</sub>
    </td>
    <td align="center">
      <a href="examples/full/iceland-copper.png"><img src="examples/thumbnails/iceland-copper.png" alt="Iceland - Copper" width="200"></a><br>
      <sub>copper</sub>
    </td>
    <td align="center">
      <a href="examples/full/iceland-coral.png"><img src="examples/thumbnails/iceland-coral.png" alt="Iceland - Coral" width="200"></a><br>
      <sub>coral</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/iceland-glacier.png"><img src="examples/thumbnails/iceland-glacier.png" alt="Iceland - Glacier" width="200"></a><br>
      <sub>glacier</sub>
    </td>
    <td align="center">
      <a href="examples/full/iceland-lava.png"><img src="examples/thumbnails/iceland-lava.png" alt="Iceland - Lava" width="200"></a><br>
      <sub>lava</sub>
    </td>
    <td align="center">
      <a href="examples/full/iceland-minimal_white.png"><img src="examples/thumbnails/iceland-minimal_white.png" alt="Iceland - Minimal White" width="200"></a><br>
      <sub>minimal_white</sub>
    </td>
    <td align="center">
      <a href="examples/full/iceland-natural.png"><img src="examples/thumbnails/iceland-natural.png" alt="Iceland - Natural" width="200"></a><br>
      <sub>natural</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/iceland-neon_cyber.png"><img src="examples/thumbnails/iceland-neon_cyber.png" alt="Iceland - Neon Cyber" width="200"></a><br>
      <sub>neon_cyber</sub>
    </td>
    <td align="center">
      <a href="examples/full/iceland-night.png"><img src="examples/thumbnails/iceland-night.png" alt="Iceland - Night" width="200"></a><br>
      <sub>night</sub>
    </td>
    <td align="center">
      <a href="examples/full/iceland-porcelain_ink.png"><img src="examples/thumbnails/iceland-porcelain_ink.png" alt="Iceland - Porcelain Ink" width="200"></a><br>
      <sub>porcelain_ink</sub>
    </td>
    <td align="center">
      <a href="examples/full/iceland-river_runs_red.png"><img src="examples/thumbnails/iceland-river_runs_red.png" alt="Iceland - River Runs Red" width="200"></a><br>
      <sub>river_runs_red</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/iceland-satellite.png"><img src="examples/thumbnails/iceland-satellite.png" alt="Iceland - Satellite" width="200"></a><br>
      <sub>satellite</sub>
    </td>
    <td align="center">
      <a href="examples/full/iceland-sepia_vintage.png"><img src="examples/thumbnails/iceland-sepia_vintage.png" alt="Iceland - Sepia Vintage" width="200"></a><br>
      <sub>sepia_vintage</sub>
    </td>
    <td align="center">
      <a href="examples/full/iceland-slate.png"><img src="examples/thumbnails/iceland-slate.png" alt="Iceland - Slate" width="200"></a><br>
      <sub>slate</sub>
    </td>
    <td align="center">
      <a href="examples/full/iceland-yellow.png"><img src="examples/thumbnails/iceland-yellow.png" alt="Iceland - Yellow" width="200"></a><br>
      <sub>yellow</sub>
    </td>
  </tr>
</table>

### Oahu, HI

<table>
  <tr>
    <td align="center">
      <a href="examples/full/oahu-hi-blueprint.png"><img src="examples/thumbnails/oahu-hi-blueprint.png" alt="Oahu - Blueprint" width="200"></a><br>
      <sub>blueprint</sub>
    </td>
    <td align="center">
      <a href="examples/full/oahu-hi-burgundy.png"><img src="examples/thumbnails/oahu-hi-burgundy.png" alt="Oahu - Burgundy" width="200"></a><br>
      <sub>burgundy</sub>
    </td>
    <td align="center">
      <a href="examples/full/oahu-hi-copper.png"><img src="examples/thumbnails/oahu-hi-copper.png" alt="Oahu - Copper" width="200"></a><br>
      <sub>copper</sub>
    </td>
    <td align="center">
      <a href="examples/full/oahu-hi-coral.png"><img src="examples/thumbnails/oahu-hi-coral.png" alt="Oahu - Coral" width="200"></a><br>
      <sub>coral</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/oahu-hi-glacier.png"><img src="examples/thumbnails/oahu-hi-glacier.png" alt="Oahu - Glacier" width="200"></a><br>
      <sub>glacier</sub>
    </td>
    <td align="center">
      <a href="examples/full/oahu-hi-lava.png"><img src="examples/thumbnails/oahu-hi-lava.png" alt="Oahu - Lava" width="200"></a><br>
      <sub>lava</sub>
    </td>
    <td align="center">
      <a href="examples/full/oahu-hi-minimal_white.png"><img src="examples/thumbnails/oahu-hi-minimal_white.png" alt="Oahu - Minimal White" width="200"></a><br>
      <sub>minimal_white</sub>
    </td>
    <td align="center">
      <a href="examples/full/oahu-hi-natural.png"><img src="examples/thumbnails/oahu-hi-natural.png" alt="Oahu - Natural" width="200"></a><br>
      <sub>natural</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/oahu-hi-neon_cyber.png"><img src="examples/thumbnails/oahu-hi-neon_cyber.png" alt="Oahu - Neon Cyber" width="200"></a><br>
      <sub>neon_cyber</sub>
    </td>
    <td align="center">
      <a href="examples/full/oahu-hi-night.png"><img src="examples/thumbnails/oahu-hi-night.png" alt="Oahu - Night" width="200"></a><br>
      <sub>night</sub>
    </td>
    <td align="center">
      <a href="examples/full/oahu-hi-porcelain_ink.png"><img src="examples/thumbnails/oahu-hi-porcelain_ink.png" alt="Oahu - Porcelain Ink" width="200"></a><br>
      <sub>porcelain_ink</sub>
    </td>
    <td align="center">
      <a href="examples/full/oahu-hi-river_runs_red.png"><img src="examples/thumbnails/oahu-hi-river_runs_red.png" alt="Oahu - River Runs Red" width="200"></a><br>
      <sub>river_runs_red</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/oahu-hi-satellite.png"><img src="examples/thumbnails/oahu-hi-satellite.png" alt="Oahu - Satellite" width="200"></a><br>
      <sub>satellite</sub>
    </td>
    <td align="center">
      <a href="examples/full/oahu-hi-sepia_vintage.png"><img src="examples/thumbnails/oahu-hi-sepia_vintage.png" alt="Oahu - Sepia Vintage" width="200"></a><br>
      <sub>sepia_vintage</sub>
    </td>
    <td align="center">
      <a href="examples/full/oahu-hi-slate.png"><img src="examples/thumbnails/oahu-hi-slate.png" alt="Oahu - Slate" width="200"></a><br>
      <sub>slate</sub>
    </td>
    <td align="center">
      <a href="examples/full/oahu-hi-yellow.png"><img src="examples/thumbnails/oahu-hi-yellow.png" alt="Oahu - Yellow" width="200"></a><br>
      <sub>yellow</sub>
    </td>
  </tr>
</table>

### Patagonia

<table>
  <tr>
    <td align="center">
      <a href="examples/full/patagonia-blueprint.png"><img src="examples/thumbnails/patagonia-blueprint.png" alt="Patagonia - Blueprint" width="200"></a><br>
      <sub>blueprint</sub>
    </td>
    <td align="center">
      <a href="examples/full/patagonia-burgundy.png"><img src="examples/thumbnails/patagonia-burgundy.png" alt="Patagonia - Burgundy" width="200"></a><br>
      <sub>burgundy</sub>
    </td>
    <td align="center">
      <a href="examples/full/patagonia-copper.png"><img src="examples/thumbnails/patagonia-copper.png" alt="Patagonia - Copper" width="200"></a><br>
      <sub>copper</sub>
    </td>
    <td align="center">
      <a href="examples/full/patagonia-coral.png"><img src="examples/thumbnails/patagonia-coral.png" alt="Patagonia - Coral" width="200"></a><br>
      <sub>coral</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/patagonia-glacier.png"><img src="examples/thumbnails/patagonia-glacier.png" alt="Patagonia - Glacier" width="200"></a><br>
      <sub>glacier</sub>
    </td>
    <td align="center">
      <a href="examples/full/patagonia-lava.png"><img src="examples/thumbnails/patagonia-lava.png" alt="Patagonia - Lava" width="200"></a><br>
      <sub>lava</sub>
    </td>
    <td align="center">
      <a href="examples/full/patagonia-minimal_white.png"><img src="examples/thumbnails/patagonia-minimal_white.png" alt="Patagonia - Minimal White" width="200"></a><br>
      <sub>minimal_white</sub>
    </td>
    <td align="center">
      <a href="examples/full/patagonia-natural.png"><img src="examples/thumbnails/patagonia-natural.png" alt="Patagonia - Natural" width="200"></a><br>
      <sub>natural</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/patagonia-neon_cyber.png"><img src="examples/thumbnails/patagonia-neon_cyber.png" alt="Patagonia - Neon Cyber" width="200"></a><br>
      <sub>neon_cyber</sub>
    </td>
    <td align="center">
      <a href="examples/full/patagonia-night.png"><img src="examples/thumbnails/patagonia-night.png" alt="Patagonia - Night" width="200"></a><br>
      <sub>night</sub>
    </td>
    <td align="center">
      <a href="examples/full/patagonia-porcelain_ink.png"><img src="examples/thumbnails/patagonia-porcelain_ink.png" alt="Patagonia - Porcelain Ink" width="200"></a><br>
      <sub>porcelain_ink</sub>
    </td>
    <td align="center">
      <a href="examples/full/patagonia-river_runs_red.png"><img src="examples/thumbnails/patagonia-river_runs_red.png" alt="Patagonia - River Runs Red" width="200"></a><br>
      <sub>river_runs_red</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/patagonia-satellite.png"><img src="examples/thumbnails/patagonia-satellite.png" alt="Patagonia - Satellite" width="200"></a><br>
      <sub>satellite</sub>
    </td>
    <td align="center">
      <a href="examples/full/patagonia-sepia_vintage.png"><img src="examples/thumbnails/patagonia-sepia_vintage.png" alt="Patagonia - Sepia Vintage" width="200"></a><br>
      <sub>sepia_vintage</sub>
    </td>
    <td align="center">
      <a href="examples/full/patagonia-slate.png"><img src="examples/thumbnails/patagonia-slate.png" alt="Patagonia - Slate" width="200"></a><br>
      <sub>slate</sub>
    </td>
    <td align="center">
      <a href="examples/full/patagonia-yellow.png"><img src="examples/thumbnails/patagonia-yellow.png" alt="Patagonia - Yellow" width="200"></a><br>
      <sub>yellow</sub>
    </td>
  </tr>
</table>

### San Francisco, CA

<table>
  <tr>
    <td align="center">
      <a href="examples/full/san-francisco-ca-blueprint.png"><img src="examples/thumbnails/san-francisco-ca-blueprint.png" alt="San Francisco - Blueprint" width="200"></a><br>
      <sub>blueprint</sub>
    </td>
    <td align="center">
      <a href="examples/full/san-francisco-ca-burgundy.png"><img src="examples/thumbnails/san-francisco-ca-burgundy.png" alt="San Francisco - Burgundy" width="200"></a><br>
      <sub>burgundy</sub>
    </td>
    <td align="center">
      <a href="examples/full/san-francisco-ca-copper.png"><img src="examples/thumbnails/san-francisco-ca-copper.png" alt="San Francisco - Copper" width="200"></a><br>
      <sub>copper</sub>
    </td>
    <td align="center">
      <a href="examples/full/san-francisco-ca-coral.png"><img src="examples/thumbnails/san-francisco-ca-coral.png" alt="San Francisco - Coral" width="200"></a><br>
      <sub>coral</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/san-francisco-ca-glacier.png"><img src="examples/thumbnails/san-francisco-ca-glacier.png" alt="San Francisco - Glacier" width="200"></a><br>
      <sub>glacier</sub>
    </td>
    <td align="center">
      <a href="examples/full/san-francisco-ca-lava.png"><img src="examples/thumbnails/san-francisco-ca-lava.png" alt="San Francisco - Lava" width="200"></a><br>
      <sub>lava</sub>
    </td>
    <td align="center">
      <a href="examples/full/san-francisco-ca-minimal_white.png"><img src="examples/thumbnails/san-francisco-ca-minimal_white.png" alt="San Francisco - Minimal White" width="200"></a><br>
      <sub>minimal_white</sub>
    </td>
    <td align="center">
      <a href="examples/full/san-francisco-ca-natural.png"><img src="examples/thumbnails/san-francisco-ca-natural.png" alt="San Francisco - Natural" width="200"></a><br>
      <sub>natural</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/san-francisco-ca-neon_cyber.png"><img src="examples/thumbnails/san-francisco-ca-neon_cyber.png" alt="San Francisco - Neon Cyber" width="200"></a><br>
      <sub>neon_cyber</sub>
    </td>
    <td align="center">
      <a href="examples/full/san-francisco-ca-night.png"><img src="examples/thumbnails/san-francisco-ca-night.png" alt="San Francisco - Night" width="200"></a><br>
      <sub>night</sub>
    </td>
    <td align="center">
      <a href="examples/full/san-francisco-ca-porcelain_ink.png"><img src="examples/thumbnails/san-francisco-ca-porcelain_ink.png" alt="San Francisco - Porcelain Ink" width="200"></a><br>
      <sub>porcelain_ink</sub>
    </td>
    <td align="center">
      <a href="examples/full/san-francisco-ca-river_runs_red.png"><img src="examples/thumbnails/san-francisco-ca-river_runs_red.png" alt="San Francisco - River Runs Red" width="200"></a><br>
      <sub>river_runs_red</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/san-francisco-ca-satellite.png"><img src="examples/thumbnails/san-francisco-ca-satellite.png" alt="San Francisco - Satellite" width="200"></a><br>
      <sub>satellite</sub>
    </td>
    <td align="center">
      <a href="examples/full/san-francisco-ca-sepia_vintage.png"><img src="examples/thumbnails/san-francisco-ca-sepia_vintage.png" alt="San Francisco - Sepia Vintage" width="200"></a><br>
      <sub>sepia_vintage</sub>
    </td>
    <td align="center">
      <a href="examples/full/san-francisco-ca-slate.png"><img src="examples/thumbnails/san-francisco-ca-slate.png" alt="San Francisco - Slate" width="200"></a><br>
      <sub>slate</sub>
    </td>
    <td align="center">
      <a href="examples/full/san-francisco-ca-yellow.png"><img src="examples/thumbnails/san-francisco-ca-yellow.png" alt="San Francisco - Yellow" width="200"></a><br>
      <sub>yellow</sub>
    </td>
  </tr>
</table>

### Vancouver, BC

<table>
  <tr>
    <td align="center">
      <a href="examples/full/vancouver-bc-blueprint.png"><img src="examples/thumbnails/vancouver-bc-blueprint.png" alt="Vancouver - Blueprint" width="200"></a><br>
      <sub>blueprint</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-bc-burgundy.png"><img src="examples/thumbnails/vancouver-bc-burgundy.png" alt="Vancouver - Burgundy" width="200"></a><br>
      <sub>burgundy</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-bc-copper.png"><img src="examples/thumbnails/vancouver-bc-copper.png" alt="Vancouver - Copper" width="200"></a><br>
      <sub>copper</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-bc-coral.png"><img src="examples/thumbnails/vancouver-bc-coral.png" alt="Vancouver - Coral" width="200"></a><br>
      <sub>coral</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/vancouver-bc-glacier.png"><img src="examples/thumbnails/vancouver-bc-glacier.png" alt="Vancouver - Glacier" width="200"></a><br>
      <sub>glacier</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-bc-lava.png"><img src="examples/thumbnails/vancouver-bc-lava.png" alt="Vancouver - Lava" width="200"></a><br>
      <sub>lava</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-bc-minimal_white.png"><img src="examples/thumbnails/vancouver-bc-minimal_white.png" alt="Vancouver - Minimal White" width="200"></a><br>
      <sub>minimal_white</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-bc-natural.png"><img src="examples/thumbnails/vancouver-bc-natural.png" alt="Vancouver - Natural" width="200"></a><br>
      <sub>natural</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/vancouver-bc-neon_cyber.png"><img src="examples/thumbnails/vancouver-bc-neon_cyber.png" alt="Vancouver - Neon Cyber" width="200"></a><br>
      <sub>neon_cyber</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-bc-night.png"><img src="examples/thumbnails/vancouver-bc-night.png" alt="Vancouver - Night" width="200"></a><br>
      <sub>night</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-bc-porcelain_ink.png"><img src="examples/thumbnails/vancouver-bc-porcelain_ink.png" alt="Vancouver - Porcelain Ink" width="200"></a><br>
      <sub>porcelain_ink</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-bc-river_runs_red.png"><img src="examples/thumbnails/vancouver-bc-river_runs_red.png" alt="Vancouver - River Runs Red" width="200"></a><br>
      <sub>river_runs_red</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/vancouver-bc-satellite.png"><img src="examples/thumbnails/vancouver-bc-satellite.png" alt="Vancouver - Satellite" width="200"></a><br>
      <sub>satellite</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-bc-sepia_vintage.png"><img src="examples/thumbnails/vancouver-bc-sepia_vintage.png" alt="Vancouver - Sepia Vintage" width="200"></a><br>
      <sub>sepia_vintage</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-bc-slate.png"><img src="examples/thumbnails/vancouver-bc-slate.png" alt="Vancouver - Slate" width="200"></a><br>
      <sub>slate</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-bc-yellow.png"><img src="examples/thumbnails/vancouver-bc-yellow.png" alt="Vancouver - Yellow" width="200"></a><br>
      <sub>yellow</sub>
    </td>
  </tr>
</table>

### Vancouver Island, BC

<table>
  <tr>
    <td align="center">
      <a href="examples/full/vancouver-island-bc-blueprint.png"><img src="examples/thumbnails/vancouver-island-bc-blueprint.png" alt="Vancouver Island - Blueprint" width="200"></a><br>
      <sub>blueprint</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-island-bc-burgundy.png"><img src="examples/thumbnails/vancouver-island-bc-burgundy.png" alt="Vancouver Island - Burgundy" width="200"></a><br>
      <sub>burgundy</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-island-bc-copper.png"><img src="examples/thumbnails/vancouver-island-bc-copper.png" alt="Vancouver Island - Copper" width="200"></a><br>
      <sub>copper</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-island-bc-coral.png"><img src="examples/thumbnails/vancouver-island-bc-coral.png" alt="Vancouver Island - Coral" width="200"></a><br>
      <sub>coral</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/vancouver-island-bc-glacier.png"><img src="examples/thumbnails/vancouver-island-bc-glacier.png" alt="Vancouver Island - Glacier" width="200"></a><br>
      <sub>glacier</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-island-bc-lava.png"><img src="examples/thumbnails/vancouver-island-bc-lava.png" alt="Vancouver Island - Lava" width="200"></a><br>
      <sub>lava</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-island-bc-minimal_white.png"><img src="examples/thumbnails/vancouver-island-bc-minimal_white.png" alt="Vancouver Island - Minimal White" width="200"></a><br>
      <sub>minimal_white</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-island-bc-natural.png"><img src="examples/thumbnails/vancouver-island-bc-natural.png" alt="Vancouver Island - Natural" width="200"></a><br>
      <sub>natural</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/vancouver-island-bc-neon_cyber.png"><img src="examples/thumbnails/vancouver-island-bc-neon_cyber.png" alt="Vancouver Island - Neon Cyber" width="200"></a><br>
      <sub>neon_cyber</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-island-bc-night.png"><img src="examples/thumbnails/vancouver-island-bc-night.png" alt="Vancouver Island - Night" width="200"></a><br>
      <sub>night</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-island-bc-porcelain_ink.png"><img src="examples/thumbnails/vancouver-island-bc-porcelain_ink.png" alt="Vancouver Island - Porcelain Ink" width="200"></a><br>
      <sub>porcelain_ink</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-island-bc-river_runs_red.png"><img src="examples/thumbnails/vancouver-island-bc-river_runs_red.png" alt="Vancouver Island - River Runs Red" width="200"></a><br>
      <sub>river_runs_red</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/vancouver-island-bc-satellite.png"><img src="examples/thumbnails/vancouver-island-bc-satellite.png" alt="Vancouver Island - Satellite" width="200"></a><br>
      <sub>satellite</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-island-bc-sepia_vintage.png"><img src="examples/thumbnails/vancouver-island-bc-sepia_vintage.png" alt="Vancouver Island - Sepia Vintage" width="200"></a><br>
      <sub>sepia_vintage</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-island-bc-slate.png"><img src="examples/thumbnails/vancouver-island-bc-slate.png" alt="Vancouver Island - Slate" width="200"></a><br>
      <sub>slate</sub>
    </td>
    <td align="center">
      <a href="examples/full/vancouver-island-bc-yellow.png"><img src="examples/thumbnails/vancouver-island-bc-yellow.png" alt="Vancouver Island - Yellow" width="200"></a><br>
      <sub>yellow</sub>
    </td>
  </tr>
</table>

### Vestland, Norway

<table>
  <tr>
    <td align="center">
      <a href="examples/full/vestland-norway-blueprint.png"><img src="examples/thumbnails/vestland-norway-blueprint.png" alt="Vestland - Blueprint" width="200"></a><br>
      <sub>blueprint</sub>
    </td>
    <td align="center">
      <a href="examples/full/vestland-norway-burgundy.png"><img src="examples/thumbnails/vestland-norway-burgundy.png" alt="Vestland - Burgundy" width="200"></a><br>
      <sub>burgundy</sub>
    </td>
    <td align="center">
      <a href="examples/full/vestland-norway-copper.png"><img src="examples/thumbnails/vestland-norway-copper.png" alt="Vestland - Copper" width="200"></a><br>
      <sub>copper</sub>
    </td>
    <td align="center">
      <a href="examples/full/vestland-norway-coral.png"><img src="examples/thumbnails/vestland-norway-coral.png" alt="Vestland - Coral" width="200"></a><br>
      <sub>coral</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/vestland-norway-glacier.png"><img src="examples/thumbnails/vestland-norway-glacier.png" alt="Vestland - Glacier" width="200"></a><br>
      <sub>glacier</sub>
    </td>
    <td align="center">
      <a href="examples/full/vestland-norway-lava.png"><img src="examples/thumbnails/vestland-norway-lava.png" alt="Vestland - Lava" width="200"></a><br>
      <sub>lava</sub>
    </td>
    <td align="center">
      <a href="examples/full/vestland-norway-minimal_white.png"><img src="examples/thumbnails/vestland-norway-minimal_white.png" alt="Vestland - Minimal White" width="200"></a><br>
      <sub>minimal_white</sub>
    </td>
    <td align="center">
      <a href="examples/full/vestland-norway-natural.png"><img src="examples/thumbnails/vestland-norway-natural.png" alt="Vestland - Natural" width="200"></a><br>
      <sub>natural</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/vestland-norway-neon_cyber.png"><img src="examples/thumbnails/vestland-norway-neon_cyber.png" alt="Vestland - Neon Cyber" width="200"></a><br>
      <sub>neon_cyber</sub>
    </td>
    <td align="center">
      <a href="examples/full/vestland-norway-night.png"><img src="examples/thumbnails/vestland-norway-night.png" alt="Vestland - Night" width="200"></a><br>
      <sub>night</sub>
    </td>
    <td align="center">
      <a href="examples/full/vestland-norway-porcelain_ink.png"><img src="examples/thumbnails/vestland-norway-porcelain_ink.png" alt="Vestland - Porcelain Ink" width="200"></a><br>
      <sub>porcelain_ink</sub>
    </td>
    <td align="center">
      <a href="examples/full/vestland-norway-river_runs_red.png"><img src="examples/thumbnails/vestland-norway-river_runs_red.png" alt="Vestland - River Runs Red" width="200"></a><br>
      <sub>river_runs_red</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/vestland-norway-satellite.png"><img src="examples/thumbnails/vestland-norway-satellite.png" alt="Vestland - Satellite" width="200"></a><br>
      <sub>satellite</sub>
    </td>
    <td align="center">
      <a href="examples/full/vestland-norway-sepia_vintage.png"><img src="examples/thumbnails/vestland-norway-sepia_vintage.png" alt="Vestland - Sepia Vintage" width="200"></a><br>
      <sub>sepia_vintage</sub>
    </td>
    <td align="center">
      <a href="examples/full/vestland-norway-slate.png"><img src="examples/thumbnails/vestland-norway-slate.png" alt="Vestland - Slate" width="200"></a><br>
      <sub>slate</sub>
    </td>
    <td align="center">
      <a href="examples/full/vestland-norway-yellow.png"><img src="examples/thumbnails/vestland-norway-yellow.png" alt="Vestland - Yellow" width="200"></a><br>
      <sub>yellow</sub>
    </td>
  </tr>
</table>

### Route Map Examples

Route maps overlay a GPX track onto the map and include a stats panel with ride title, subtitle, and custom metrics. Two variants are supported: a region-bounded map (the map region is defined by a place name, with the GPX track drawn on top) and a GPX-derived map (the map region is derived directly from the GPX track bounding box, with no separate region argument required).

#### Edmonton Loop — Region + GPX Route

<table>
  <tr>
    <td align="center">
      <a href="examples/full/edmonton-ab-route-edmonton-110km-blueprint.png"><img src="examples/thumbnails/edmonton-ab-route-edmonton-110km-blueprint.png" alt="Edmonton Loop - Blueprint" width="200"></a><br>
      <sub>blueprint</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-route-edmonton-110km-burgundy.png"><img src="examples/thumbnails/edmonton-ab-route-edmonton-110km-burgundy.png" alt="Edmonton Loop - Burgundy" width="200"></a><br>
      <sub>burgundy</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-route-edmonton-110km-copper.png"><img src="examples/thumbnails/edmonton-ab-route-edmonton-110km-copper.png" alt="Edmonton Loop - Copper" width="200"></a><br>
      <sub>copper</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-route-edmonton-110km-coral.png"><img src="examples/thumbnails/edmonton-ab-route-edmonton-110km-coral.png" alt="Edmonton Loop - Coral" width="200"></a><br>
      <sub>coral</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/edmonton-ab-route-edmonton-110km-glacier.png"><img src="examples/thumbnails/edmonton-ab-route-edmonton-110km-glacier.png" alt="Edmonton Loop - Glacier" width="200"></a><br>
      <sub>glacier</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-route-edmonton-110km-lava.png"><img src="examples/thumbnails/edmonton-ab-route-edmonton-110km-lava.png" alt="Edmonton Loop - Lava" width="200"></a><br>
      <sub>lava</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-route-edmonton-110km-minimal_white.png"><img src="examples/thumbnails/edmonton-ab-route-edmonton-110km-minimal_white.png" alt="Edmonton Loop - Minimal White" width="200"></a><br>
      <sub>minimal_white</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-route-edmonton-110km-natural.png"><img src="examples/thumbnails/edmonton-ab-route-edmonton-110km-natural.png" alt="Edmonton Loop - Natural" width="200"></a><br>
      <sub>natural</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/edmonton-ab-route-edmonton-110km-neon_cyber.png"><img src="examples/thumbnails/edmonton-ab-route-edmonton-110km-neon_cyber.png" alt="Edmonton Loop - Neon Cyber" width="200"></a><br>
      <sub>neon_cyber</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-route-edmonton-110km-night.png"><img src="examples/thumbnails/edmonton-ab-route-edmonton-110km-night.png" alt="Edmonton Loop - Night" width="200"></a><br>
      <sub>night</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-route-edmonton-110km-porcelain_ink.png"><img src="examples/thumbnails/edmonton-ab-route-edmonton-110km-porcelain_ink.png" alt="Edmonton Loop - Porcelain Ink" width="200"></a><br>
      <sub>porcelain_ink</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-route-edmonton-110km-river_runs_red.png"><img src="examples/thumbnails/edmonton-ab-route-edmonton-110km-river_runs_red.png" alt="Edmonton Loop - River Runs Red" width="200"></a><br>
      <sub>river_runs_red</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/edmonton-ab-route-edmonton-110km-satellite.png"><img src="examples/thumbnails/edmonton-ab-route-edmonton-110km-satellite.png" alt="Edmonton Loop - Satellite" width="200"></a><br>
      <sub>satellite</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-route-edmonton-110km-sepia_vintage.png"><img src="examples/thumbnails/edmonton-ab-route-edmonton-110km-sepia_vintage.png" alt="Edmonton Loop - Sepia Vintage" width="200"></a><br>
      <sub>sepia_vintage</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-route-edmonton-110km-slate.png"><img src="examples/thumbnails/edmonton-ab-route-edmonton-110km-slate.png" alt="Edmonton Loop - Slate" width="200"></a><br>
      <sub>slate</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-ab-route-edmonton-110km-yellow.png"><img src="examples/thumbnails/edmonton-ab-route-edmonton-110km-yellow.png" alt="Edmonton Loop - Yellow" width="200"></a><br>
      <sub>yellow</sub>
    </td>
  </tr>
</table>

#### River Valley Loop — GPX-Derived Route

<table>
  <tr>
    <td align="center">
      <a href="examples/full/edmonton-50km-blueprint.png"><img src="examples/thumbnails/edmonton-50km-blueprint.png" alt="River Valley Loop - Blueprint" width="200"></a><br>
      <sub>blueprint</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-50km-burgundy.png"><img src="examples/thumbnails/edmonton-50km-burgundy.png" alt="River Valley Loop - Burgundy" width="200"></a><br>
      <sub>burgundy</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-50km-copper.png"><img src="examples/thumbnails/edmonton-50km-copper.png" alt="River Valley Loop - Copper" width="200"></a><br>
      <sub>copper</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-50km-coral.png"><img src="examples/thumbnails/edmonton-50km-coral.png" alt="River Valley Loop - Coral" width="200"></a><br>
      <sub>coral</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/edmonton-50km-glacier.png"><img src="examples/thumbnails/edmonton-50km-glacier.png" alt="River Valley Loop - Glacier" width="200"></a><br>
      <sub>glacier</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-50km-lava.png"><img src="examples/thumbnails/edmonton-50km-lava.png" alt="River Valley Loop - Lava" width="200"></a><br>
      <sub>lava</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-50km-minimal_white.png"><img src="examples/thumbnails/edmonton-50km-minimal_white.png" alt="River Valley Loop - Minimal White" width="200"></a><br>
      <sub>minimal_white</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-50km-natural.png"><img src="examples/thumbnails/edmonton-50km-natural.png" alt="River Valley Loop - Natural" width="200"></a><br>
      <sub>natural</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/edmonton-50km-neon_cyber.png"><img src="examples/thumbnails/edmonton-50km-neon_cyber.png" alt="River Valley Loop - Neon Cyber" width="200"></a><br>
      <sub>neon_cyber</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-50km-night.png"><img src="examples/thumbnails/edmonton-50km-night.png" alt="River Valley Loop - Night" width="200"></a><br>
      <sub>night</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-50km-porcelain_ink.png"><img src="examples/thumbnails/edmonton-50km-porcelain_ink.png" alt="River Valley Loop - Porcelain Ink" width="200"></a><br>
      <sub>porcelain_ink</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-50km-river_runs_red.png"><img src="examples/thumbnails/edmonton-50km-river_runs_red.png" alt="River Valley Loop - River Runs Red" width="200"></a><br>
      <sub>river_runs_red</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/edmonton-50km-satellite.png"><img src="examples/thumbnails/edmonton-50km-satellite.png" alt="River Valley Loop - Satellite" width="200"></a><br>
      <sub>satellite</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-50km-sepia_vintage.png"><img src="examples/thumbnails/edmonton-50km-sepia_vintage.png" alt="River Valley Loop - Sepia Vintage" width="200"></a><br>
      <sub>sepia_vintage</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-50km-slate.png"><img src="examples/thumbnails/edmonton-50km-slate.png" alt="River Valley Loop - Slate" width="200"></a><br>
      <sub>slate</sub>
    </td>
    <td align="center">
      <a href="examples/full/edmonton-50km-yellow.png"><img src="examples/thumbnails/edmonton-50km-yellow.png" alt="River Valley Loop - Yellow" width="200"></a><br>
      <sub>yellow</sub>
    </td>
  </tr>
</table>

#### South Shore Coastal Ride — GPX-Derived Route

<table>
  <tr>
    <td align="center">
      <a href="examples/full/south-shore-coastal-ride-blueprint.png"><img src="examples/thumbnails/south-shore-coastal-ride-blueprint.png" alt="South Shore Coastal Ride - Blueprint" width="200"></a><br>
      <sub>blueprint</sub>
    </td>
    <td align="center">
      <a href="examples/full/south-shore-coastal-ride-burgundy.png"><img src="examples/thumbnails/south-shore-coastal-ride-burgundy.png" alt="South Shore Coastal Ride - Burgundy" width="200"></a><br>
      <sub>burgundy</sub>
    </td>
    <td align="center">
      <a href="examples/full/south-shore-coastal-ride-copper.png"><img src="examples/thumbnails/south-shore-coastal-ride-copper.png" alt="South Shore Coastal Ride - Copper" width="200"></a><br>
      <sub>copper</sub>
    </td>
    <td align="center">
      <a href="examples/full/south-shore-coastal-ride-coral.png"><img src="examples/thumbnails/south-shore-coastal-ride-coral.png" alt="South Shore Coastal Ride - Coral" width="200"></a><br>
      <sub>coral</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/south-shore-coastal-ride-glacier.png"><img src="examples/thumbnails/south-shore-coastal-ride-glacier.png" alt="South Shore Coastal Ride - Glacier" width="200"></a><br>
      <sub>glacier</sub>
    </td>
    <td align="center">
      <a href="examples/full/south-shore-coastal-ride-lava.png"><img src="examples/thumbnails/south-shore-coastal-ride-lava.png" alt="South Shore Coastal Ride - Lava" width="200"></a><br>
      <sub>lava</sub>
    </td>
    <td align="center">
      <a href="examples/full/south-shore-coastal-ride-minimal_white.png"><img src="examples/thumbnails/south-shore-coastal-ride-minimal_white.png" alt="South Shore Coastal Ride - Minimal White" width="200"></a><br>
      <sub>minimal_white</sub>
    </td>
    <td align="center">
      <a href="examples/full/south-shore-coastal-ride-natural.png"><img src="examples/thumbnails/south-shore-coastal-ride-natural.png" alt="South Shore Coastal Ride - Natural" width="200"></a><br>
      <sub>natural</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/south-shore-coastal-ride-neon_cyber.png"><img src="examples/thumbnails/south-shore-coastal-ride-neon_cyber.png" alt="South Shore Coastal Ride - Neon Cyber" width="200"></a><br>
      <sub>neon_cyber</sub>
    </td>
    <td align="center">
      <a href="examples/full/south-shore-coastal-ride-night.png"><img src="examples/thumbnails/south-shore-coastal-ride-night.png" alt="South Shore Coastal Ride - Night" width="200"></a><br>
      <sub>night</sub>
    </td>
    <td align="center">
      <a href="examples/full/south-shore-coastal-ride-porcelain_ink.png"><img src="examples/thumbnails/south-shore-coastal-ride-porcelain_ink.png" alt="South Shore Coastal Ride - Porcelain Ink" width="200"></a><br>
      <sub>porcelain_ink</sub>
    </td>
    <td align="center">
      <a href="examples/full/south-shore-coastal-ride-river_runs_red.png"><img src="examples/thumbnails/south-shore-coastal-ride-river_runs_red.png" alt="South Shore Coastal Ride - River Runs Red" width="200"></a><br>
      <sub>river_runs_red</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/south-shore-coastal-ride-satellite.png"><img src="examples/thumbnails/south-shore-coastal-ride-satellite.png" alt="South Shore Coastal Ride - Satellite" width="200"></a><br>
      <sub>satellite</sub>
    </td>
    <td align="center">
      <a href="examples/full/south-shore-coastal-ride-sepia_vintage.png"><img src="examples/thumbnails/south-shore-coastal-ride-sepia_vintage.png" alt="South Shore Coastal Ride - Sepia Vintage" width="200"></a><br>
      <sub>sepia_vintage</sub>
    </td>
    <td align="center">
      <a href="examples/full/south-shore-coastal-ride-slate.png"><img src="examples/thumbnails/south-shore-coastal-ride-slate.png" alt="South Shore Coastal Ride - Slate" width="200"></a><br>
      <sub>slate</sub>
    </td>
    <td align="center">
      <a href="examples/full/south-shore-coastal-ride-yellow.png"><img src="examples/thumbnails/south-shore-coastal-ride-yellow.png" alt="South Shore Coastal Ride - Yellow" width="200"></a><br>
      <sub>yellow</sub>
    </td>
  </tr>
</table>

#### Boston-Emerald Necklace Bicycle Adventure — GPX-Derived Route

<table>
  <tr>
    <td align="center">
      <a href="examples/full/boston-emerald-necklace-bicycle-adventure-blueprint.png"><img src="examples/thumbnails/boston-emerald-necklace-bicycle-adventure-blueprint.png" alt="Boston-Emerald Necklace - Blueprint" width="200"></a><br>
      <sub>blueprint</sub>
    </td>
    <td align="center">
      <a href="examples/full/boston-emerald-necklace-bicycle-adventure-burgundy.png"><img src="examples/thumbnails/boston-emerald-necklace-bicycle-adventure-burgundy.png" alt="Boston-Emerald Necklace - Burgundy" width="200"></a><br>
      <sub>burgundy</sub>
    </td>
    <td align="center">
      <a href="examples/full/boston-emerald-necklace-bicycle-adventure-copper.png"><img src="examples/thumbnails/boston-emerald-necklace-bicycle-adventure-copper.png" alt="Boston-Emerald Necklace - Copper" width="200"></a><br>
      <sub>copper</sub>
    </td>
    <td align="center">
      <a href="examples/full/boston-emerald-necklace-bicycle-adventure-coral.png"><img src="examples/thumbnails/boston-emerald-necklace-bicycle-adventure-coral.png" alt="Boston-Emerald Necklace - Coral" width="200"></a><br>
      <sub>coral</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/boston-emerald-necklace-bicycle-adventure-glacier.png"><img src="examples/thumbnails/boston-emerald-necklace-bicycle-adventure-glacier.png" alt="Boston-Emerald Necklace - Glacier" width="200"></a><br>
      <sub>glacier</sub>
    </td>
    <td align="center">
      <a href="examples/full/boston-emerald-necklace-bicycle-adventure-lava.png"><img src="examples/thumbnails/boston-emerald-necklace-bicycle-adventure-lava.png" alt="Boston-Emerald Necklace - Lava" width="200"></a><br>
      <sub>lava</sub>
    </td>
    <td align="center">
      <a href="examples/full/boston-emerald-necklace-bicycle-adventure-minimal_white.png"><img src="examples/thumbnails/boston-emerald-necklace-bicycle-adventure-minimal_white.png" alt="Boston-Emerald Necklace - Minimal White" width="200"></a><br>
      <sub>minimal_white</sub>
    </td>
    <td align="center">
      <a href="examples/full/boston-emerald-necklace-bicycle-adventure-natural.png"><img src="examples/thumbnails/boston-emerald-necklace-bicycle-adventure-natural.png" alt="Boston-Emerald Necklace - Natural" width="200"></a><br>
      <sub>natural</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/boston-emerald-necklace-bicycle-adventure-neon_cyber.png"><img src="examples/thumbnails/boston-emerald-necklace-bicycle-adventure-neon_cyber.png" alt="Boston-Emerald Necklace - Neon Cyber" width="200"></a><br>
      <sub>neon_cyber</sub>
    </td>
    <td align="center">
      <a href="examples/full/boston-emerald-necklace-bicycle-adventure-night.png"><img src="examples/thumbnails/boston-emerald-necklace-bicycle-adventure-night.png" alt="Boston-Emerald Necklace - Night" width="200"></a><br>
      <sub>night</sub>
    </td>
    <td align="center">
      <a href="examples/full/boston-emerald-necklace-bicycle-adventure-porcelain_ink.png"><img src="examples/thumbnails/boston-emerald-necklace-bicycle-adventure-porcelain_ink.png" alt="Boston-Emerald Necklace - Porcelain Ink" width="200"></a><br>
      <sub>porcelain_ink</sub>
    </td>
    <td align="center">
      <a href="examples/full/boston-emerald-necklace-bicycle-adventure-river_runs_red.png"><img src="examples/thumbnails/boston-emerald-necklace-bicycle-adventure-river_runs_red.png" alt="Boston-Emerald Necklace - River Runs Red" width="200"></a><br>
      <sub>river_runs_red</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="examples/full/boston-emerald-necklace-bicycle-adventure-satellite.png"><img src="examples/thumbnails/boston-emerald-necklace-bicycle-adventure-satellite.png" alt="Boston-Emerald Necklace - Satellite" width="200"></a><br>
      <sub>satellite</sub>
    </td>
    <td align="center">
      <a href="examples/full/boston-emerald-necklace-bicycle-adventure-sepia_vintage.png"><img src="examples/thumbnails/boston-emerald-necklace-bicycle-adventure-sepia_vintage.png" alt="Boston-Emerald Necklace - Sepia Vintage" width="200"></a><br>
      <sub>sepia_vintage</sub>
    </td>
    <td align="center">
      <a href="examples/full/boston-emerald-necklace-bicycle-adventure-slate.png"><img src="examples/thumbnails/boston-emerald-necklace-bicycle-adventure-slate.png" alt="Boston-Emerald Necklace - Slate" width="200"></a><br>
      <sub>slate</sub>
    </td>
    <td align="center">
      <a href="examples/full/boston-emerald-necklace-bicycle-adventure-yellow.png"><img src="examples/thumbnails/boston-emerald-necklace-bicycle-adventure-yellow.png" alt="Boston-Emerald Necklace - Yellow" width="200"></a><br>
      <sub>yellow</sub>
    </td>
  </tr>
</table>

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

## Ocean Data

For coastal regions, the pipeline can derive an ocean layer from the **World Seas (IHO Sea Areas)** dataset. Download `World_Seas_IHO_v3.zip` from [marineregions.org/downloads.php](https://www.marineregions.org/downloads.php), extract it, and place the files into `downloads/ocean-boundaries/`. The build will skip ocean processing silently if this directory is absent.

## Project Structure

```text
schemes/                     # Color scheme definitions (YAML files)
  coral.yaml                 # Coral color scheme
  natural.yaml               # Natural color scheme
  burgundy.yaml              # Burgundy color scheme
  yellow.yaml                # Yellow color scheme
  copper.yaml                # Copper color scheme
  slate.yaml                 # Slate color scheme
  # ... other schemes

scripts/                     # Pipeline scripts

examples/                    # Example maps workspace (tracked in Git)
  configs/                   # Example map configs
  downloads/                 # Example map data
  output/                    # Example map outputs
  cache/                     # Example cache

user/                        # Your workspace (ignored by Git)
  downloads/
    regions/                 # Per-region data (auto-downloaded by build / build-route)
      edmonton-ab/
        area.geojson         # Boundary polygon
        dem.tif              # Digital elevation model
        satellite.tif        # Satellite imagery
        layers/*.gpkg        # Vector layers (roads, water, etc.)
    routes/                  # Per-GPX data (auto-downloaded by build-gpx)
      edmonton-50km/
        area.geojson
        dem.tif
        satellite.tif
        layers/*.gpkg
    ocean-boundaries/        # IHO World Seas source (manual download)
  configs/                   # Base configs and optional overlays
  output/                    # Rendered maps
  cache/                     # OSM query cache (safe to delete)
```

## Cache

OSM query responses are cached in your workspace's `cache/` directory (by default `user/cache/`). It can be deleted at any time to force fresh downloads.

## Author

Created by Paul Stothard.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
