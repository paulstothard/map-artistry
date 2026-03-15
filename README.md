# map-artistry

Artistic topographic map generator using OpenStreetMap, satellite imagery, and digital elevation
models. Generates high-resolution, stylized maps via a customizable pipeline.

## Dependencies

- [just](https://github.com/casey/just) — command runner (`brew install just` on macOS)
- Python 3

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
just build "Edmonton, AB" coral
just build "Vancouver Island, BC" natural
just build "Iceland" river_runs_red 36 24
just build "Victoria, BC" natural 24 24 600 png 20   # with explicit buffer
just schemes                                          # list available color schemes
```

All settings (buffer size, DEM source, satellite zoom, layer source) are calculated automatically
based on region size. Pass an explicit `BUFFER_KM` as the last argument to override.

## Color Schemes

- `coral` — dark red elevation coloring, white water features
- `river_runs_red` — dark brown/black elevation coloring, red water features
- `natural` — hypsometric tints (green → brown → grey → white), bluish water
- `lava` — fiery elevation coloring, orange water
- `satellite` — satellite imagery base with terrain overlay

## Customizing a Map

Each build produces two auto-generated files:

- `configs/{location}-base.yaml` — full generated config
- `configs/{location}-{scheme}-final.yaml` — final merged config (used for rendering)

Create an overlay file named `configs/{location}-{scheme}.yaml` and place it in `configs/`. The
build detects it automatically and deep-merges it over the base config to produce the final config.

```bash
# 1. Build the map first to generate the base config
just build "Edmonton, AB" coral

# 2. Copy the base config as your overlay starting point
cp configs/edmonton-ab-base.yaml configs/edmonton-ab-coral.yaml

# 3. Edit it — change whatever you like; leave everything else as-is
vi configs/edmonton-ab-coral.yaml

# 4. Rebuild — the overlay is applied automatically
just build "Edmonton, AB" coral
```

Leaving unchanged keys in the overlay is fine — the merge just keeps the same value. The
`{location}` is the region name lowercased with spaces and commas replaced by hyphens (e.g.
`Edmonton, AB` → `edmonton-ab`).

## Ocean Data

For coastal regions, the pipeline can derive an ocean layer from the **World Seas (IHO Sea Areas)**
dataset. Download `World_Seas_IHO_v3.zip` from
[marineregions.org/downloads.php](https://www.marineregions.org/downloads.php), extract it, and
place the files into `downloads/ocean-boundaries/`. The build will skip ocean processing silently if
this directory is absent.

## Project Structure

```text
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
