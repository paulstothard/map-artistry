# map-artistry

A Python toolkit for crafting high-resolution, art-style maps from Shapefile and GeoJSON inputs. Configure color schemes, hillshade, and layer styling entirely via YAML, then render to PNG/PDF with precise control over line widths, fills, and typography.

## Usage

First create a virtual environment and install the required packages:

```bash
# edit the path to the desired Python executable as needed
/usr/local/bin/python3 -m venv venv
source venv/bin/activate
venv/bin/python -m pip install -r requirements.txt

```

## Generating a Map

To generate a full map from a place name:

```bash
./scripts/test-all.sh "Edmonton, Alberta" 2
```

This will:
1. Download a buffered GeoJSON boundary
2. Download a digital elevation model (DEM)
3. Download OpenStreetMap shapefiles
4. Download high-resolution satellite imagery
5. Generate a YAML config file
6. Render the final map to PNG

You can also run individual steps by providing a third argument:

- `"geojson"` – start at GeoJSON generation (default)
- `"dem"` – start at DEM download
- `"shapefiles"` – start at shapefile download
- `"satellite"` – start at satellite image download
- `"config"` – start at config generation
- `"map"` – start at map rendering