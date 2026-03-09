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

Then generate a map with:

```bash
./map-pipeline.sh "PLACE NAME"
```

Replace `"PLACE NAME"` with your desired location (e.g., `"Edmonton, AB"`). Output will be written
to the `output/` directory by default.

### Options

Run `./map-pipeline.sh --help` to see available options for zoom level, image size, design scheme,
and more.

### Recommended Zoom Levels

| Zoom | Detail Level                     | Suggested Use                         |
| ---- | -------------------------------- | ------------------------------------- |
| 5    | Very low (province scale)        | Large areas like Vancouver Island     |
| 6    | Low (regional scale)             | Entire cities with surroundings       |
| 7    | Medium (town/neighborhood scale) | City cores or small regions           |
| 8+   | High (street-level detail)       | Close-up views, custom crops required |

To include ocean features (useful for coastal maps), add the `--with-ocean` flag:

```bash
./map-pipeline.sh "Victoria, BC" output/victoria-coral --with-ocean
```

This requires downloading the **World Seas (IHO Sea Areas)** shapefile from
[https://www.marineregions.org/downloads.php](https://www.marineregions.org/downloads.php).

Download `World_Seas_IHO_v3.zip`, extract it, and place all the files (`.shp`, `.dbf`, `.shx`, etc.)
into a folder named `data/ocean/` within the project directory.

> **Note:** The `ogr2ogr` tool (part of the GDAL suite) is required for converting ocean shapefiles.
> On Ubuntu/Debian, install it with:
>
> ```bash
> sudo apt install gdal-bin
> ```
>
> On macOS (with Homebrew), use:
>
> ```bash
> brew install gdal
> ```
>
> Ensure it is accessible from your terminal (`ogr2ogr --version`).

### Cache

When generating OSM layers, the pipeline uses OSMnx to query the Overpass API. To avoid repeated
downloads and reduce load on the API, responses are cached locally in a `cache/` folder in the
project directory. This folder can safely be deleted at any time, though doing so will cause fresh
downloads on the next run.
