# Ideas and Future Features

## Interactive GeoJSON Mask Creator

**Goal**: Visual tool to define map boundaries instead of manually creating GeoJSON files.

### Features

- Display rudimentary basemap of general region (OpenStreetMap tiles or simple DEM preview)
- Pan and zoom navigation
- Define canvas shape and aspect ratio:
  - Square (1:1)
  - Standard ratios (4:3, 16:9, etc.)
  - Custom dimensions
- **Canvas rotation**: Rotate the bounding rectangle to any angle
  - Slider or numeric input for rotation angle (0-360°)
  - Real-time preview of rotated bounds
  - Use case: Align angled geographic features (e.g., Vancouver Island) with canvas edges to
    maximize coverage
  - Shows rotated rectangle overlay on basemap
- Visual rectangle/polygon drawing tool
- Real-time preview of bounds
- Export to GeoJSON mask file (rotated polygon coordinates)

### Technical Implementation

- **Framework options:**
  - Folium (Python) - simple, generates HTML
  - Leaflet.js with Python backend (Flask/FastAPI)
  - Matplotlib with interactive widgets
  - ipyleaflet in Jupyter notebook
- **Basemap source**: OpenStreetMap tiles via contextily or custom WMS
- **Output**: Write coordinates to GeoJSON feature collection
- **Rotation handling:**
  - Define rectangle in local coordinates (width × height)
  - Apply rotation matrix around center point
  - Convert rotated corners to lat/lon polygon
  - Store rotation angle as metadata in YAML config for map generation
  - Map renderer uses rotation angle to:
    - Rotate vector layers (Shapely affine transforms)
    - Rotate final raster output (PIL/Pillow)
- **Bonus**: Load existing GeoJSON to edit

### Workflow

1. Launch tool, specify general region (city name or lat/lon)
2. Navigate to area of interest
3. Select aspect ratio or custom dimensions
4. Draw/adjust rectangle or polygon
5. **Rotate canvas** to optimize feature alignment (e.g., angle Vancouver Island to maximize canvas
   usage)
6. Preview coverage
7. Save to `data/geojson/my-map.geojson` and optionally to YAML config with rotation angle
8. Use with existing YAML configs - rotation applied during map generation

---

## Route Overlays (Strava, GPX, etc.)

**Goal**: Add GPS tracks, routes, and activities to maps (cycling routes, hikes, runs).

### Data Sources

- **Strava**: Export GPX/TCX from activities or routes API
- **Garmin/GPX files**: Standard GPS exchange format
- **Google Maps/KML**: Convert to GeoJSON
- **Custom routes**: Hand-draw or upload from route planners

### Implementation

- Add new layer type to YAML config: `route_layers`
- Support GPX, TCX, KML, and GeoJSON formats
- Rendering options:
  - Line color, width, opacity
  - Gradient coloring by elevation or speed
  - Arrows showing direction
  - Start/end markers
  - Distance/elevation labels
  - Drop shadow for visibility on varied backgrounds

### YAML Config Example

```yaml
route_layers:
  - name: "Morning Ride"
    file: "data/routes/strava_activity_12345.gpx"
    color: "#FF4500"
    width: 3
    opacity: 0.8
    show_direction: true
    gradient_by: "elevation" # or "speed", "none"
    z_order: 200
```

### Technical Considerations

- Parse GPX/TCX using `gpxpy` library
- Convert all formats to GeoDataFrame for consistent handling
- Layer compositing order (routes typically above terrain, below labels)
- Multi-segment routes (breaks for stops, multiple days)
- Elevation profile sidebar/inset option

---

## River Strip Maps

**Goal**: Create a vertical strip map following a meandering river (e.g., North Saskatchewan River
through Edmonton).

### Concept

- Multiple narrow sub-maps, each showing a segment of the river
- Each segment rotated so the river flows consistently (e.g., left-to-right)
- Stack vertically into one composite print
- Each "row" spans a different length of river

### Technical Approach (Recommended)

**Hybrid rotation approach:**

1. Divide river geometry into N segments of roughly equal path length
2. For each segment:
   - Calculate rotation angle from river bearing (averaged along segment)
   - Calculate expanded axis-aligned bounds that encompass rotated view
   - Render normally with `generate-map.py` (slightly oversized)
   - Post-process: rotate output image using PIL/Pillow
   - Crop to final strip dimensions
3. Stack rotated strips vertically using image composition

### Challenges

- **Raster rotation**: DEM/satellite imagery requires resampling when rotated
- **Vector rotation**: Easier - use shapely affine transforms
- **Angle calculation**: Determine optimal rotation for each river segment
- **Bounds calculation**: Figure out oversized bounds needed before rotation
- **Consistent scale**: Ensure all strips use same scale/DPI

### Range Definition

**Problem**: How to specify which portion of river to map?

**Options:**

1. **Distance from landmark**: "300 km before and after Edmonton"

   - Use geocoding to find landmark (city center)
   - Calculate point on river nearest to landmark
   - Measure 300 km upstream and downstream along river geometry
   - Requires: `shapely.ops.line_locate_point()` and `line_substring()`

2. **Named sections**: "Edmonton to Fort Saskatchewan"

   - Geocode both locations
   - Find intersection points with river
   - Extract segment between points

3. **Lat/lon bounds**: Specify bounding box, extract river within

4. **Percentage**: "Middle 40% of river" or "First 25%"

**Recommended**: Distance from landmark (most intuitive for users)

### Lake Handling

**Problem**: When river widens into a lake, narrow strip looks incomplete.

**Solution**: Lake detection and special handling

- Detect where river becomes lake (width threshold or water polygon detection)
- For lake sections: switch to full-width view instead of narrow strip
- Options:

  - **Expand strip width**: Gradually widen the strip bounds
  - **Full lake inset**: Show entire lake in one wider panel
  - **Detail panel**: Small inset showing full lake with indicator of position

**Detection methods:**

- Width analysis: If river width > threshold (e.g., 500m), treat as lake
- Separate water polygons: Check if river intersects lake features in data
- Named features: Reference lake names in OSM data

**Example layout:**

```
[===== Narrow river strip =====]
[===== Narrow river strip =====]
[========= WIDE LAKE ===========]  ← Expanded panel
[===== Narrow river strip =====]
[===== Narrow river strip =====]
```

### Range Specification Tool

**Proposed interface:**

```python
# Command-line tool
python scripts/create-river-map.py \
  --river "North Saskatchewan River" \
  --landmark "Edmonton, AB" \
  --upstream 300 \
  --downstream 300 \
  --strip-width 5km \
  --segment-length 50km \
  --output river-map.png
```

Or YAML config:

```yaml
river_strip_map:
  river: "North Saskatchewan River"
  reference_point:
    landmark: "Edmonton, AB, Canada"
    # or: {lat: 53.5461, lon: -113.4938}
  extent:
    upstream_km: 300
    downstream_km: 300
  strip_width_km: 5
  segment_length_km: 50
  lake_handling: "expand" # or "full", "inset"
  rotation: "auto" # rotate each segment to flow left-to-right
```

### Design Decisions Needed

- Strip width relative to river (just banks vs. wider context)
- Overlap between segments (for continuity)
- Label placement (segment identification, distance markers)
- Angle quantization (round to 15° or 30° increments?)
- Flow direction consistency (always left-to-right, or alternate?)
- Lake width threshold (when to expand strips)

### Fast Preview Mode

**Goal**: Quickly iterate on river range selection and segment layout without waiting for full
rendering.

**Problem**: Full map rendering with terrain, craters, roads, labels takes significant time. When
designing strip layout, users need rapid feedback on:

- Whether the river range looks right
- How segments are divided
- Rotation angles per segment
- Overall composition

**Solution**: Water-only preview rendering mode

- Skip all layers except water bodies and rivers
- Render water as simple blue/black fills or outlines
- No DEM processing, hillshading, or detail layers
- Show segment boundaries and rotation indicators
- Display distance markers and landmarks

**Implementation options:**

1. **Minimal config flag**: `--preview-mode` or `preview: true` in YAML

   - Skip loading DEM entirely
   - Render only water features from vector data
   - Use simple flat colors (no gradients/shading)
   - Add overlay showing: segment IDs, rotation angles, distance labels

2. **Separate preview script**: `scripts/preview-river-strip.py`
   - Lightweight, only requires vector data (no rasters)
   - Fast matplotlib rendering (no PIL/Pillow processing)
   - Output format: simple PNG or SVG
   - Optional: show oversized bounds before rotation

**Preview output features:**

- River centerline in bright color
- Water bodies in blue
- Segment boundaries as dashed lines
- Rotation angle text labels
- Distance markers (e.g., "km 0", "km 50", "km 100")
- Landmark indicators (city locations)
- Scale consistency reference

**Workflow:**

1. Run preview: `just preview-river-strip edmonton-river.yaml`
2. Check segment layout and rotation angles
3. Adjust YAML config (segment length, lake thresholds)
4. Re-run preview (fast iteration)
5. When satisfied, run full render: `just river-strip edmonton-river.yaml`

**Time savings**: Preview ~5-10 seconds vs. full render ~5-10 minutes (estimated)

### Implementation Components

1. River segmentation script
2. Rotation angle calculator
3. Expanded bounds calculator
4. Image rotation/cropping post-processor
5. Vertical stacking compositor

---

## Higher Resolution DEM Sources

**Goal**: Support higher-resolution elevation data for close-up/detailed maps while keeping 30m SRTM for general use.

### Current Status

- Using SRTM data (~30m resolution) from `elevation-tiles-prod`
- Works well for most maps at standard scales
- Insufficient detail for close-up regions or small-area maps

### Higher Resolution Options

#### 1. Copernicus DEM GLO-30
- **Resolution**: 30m (better quality than SRTM)
- **Coverage**: Global
- **Source**: https://portal.opentopography.org/
- **Notes**: More accurate than SRTM, especially in vegetated areas and high latitudes

#### 2. CDEM (Canadian Digital Elevation Model)
- **Resolution**: 20m or better
- **Coverage**: Canada (ideal for Edmonton and other Canadian locations)
- **Source**: https://open.canada.ca/data/en/dataset/7f245e4d-76c2-4caa-951a-45d1d2051333
- **Notes**: Best option for Canadian maps

#### 3. USGS 3DEP
- **Resolution**: 10m (some areas 1/3 arc-second or ~3m)
- **Coverage**: United States
- **Source**: OpenTopography API or `elevation` Python library
- **Notes**: Excellent for US locations

#### 4. OpenTopography API
- **Resolution**: Varies by dataset (can be 1m or better for some areas with LiDAR)
- **Coverage**: Selected regions with very high-resolution data
- **Source**: https://portal.opentopography.org/ (requires free API key)
- **Notes**: Best quality for supported regions

### Implementation Plan

- Add optional `dem_source` parameter to YAML config and download script
- Default to SRTM for backward compatibility
- Support multiple sources:
  - `srtm` (current default, ~30m)
  - `copernicus` (30m, better quality)
  - `cdem` (20m, Canada)
  - `3dep` (10m, USA)
  - `opentopography` (variable, requires API key)
- Auto-select best available source based on location
- Cache handling for different resolutions

### Technical Considerations

- Different download URLs and authentication methods
- Varying file formats (HGT, GeoTIFF, etc.)
- API rate limits and quota management
- Larger file sizes for high-resolution data
- Processing time increases with resolution
- Consider downsampling option for preview renders

---

## Selective Layer Downloading (Layer-Aware Data Acquisition)

**Goal**: Only download geospatial data for layers that will actually be rendered, reducing bandwidth, storage, and processing overhead.

### Problem

Current pipeline downloads all available feature types (buildings, roads, waterways, landuse, etc.) regardless of whether they appear in the map configuration. For large geographic areas or minimal "natural terrain" maps, this results in:

- Unnecessary download time for unused data
- Wasted disk space in cache
- Slower processing of irrelevant features
- Practical limit on map size due to data volume

### Solution

**Parse YAML configuration before downloading** to determine which OSM feature types are needed.

#### Examples of Selective Downloads

**Natural terrain map** (terrain + water only):
```yaml
layers:
  terrain: true
  water: true
  buildings: false
  roads: false
  labels: false
```
→ Download only: DEM data, natural water features (rivers, lakes)  
→ Skip: buildings, roads, landuse polygons, place names

**Minimalist urban map** (roads + water):
```yaml
layers:
  water: true
  roads: true
  buildings: false
```
→ Download: water features, road networks  
→ Skip: building footprints, rail, landuse

**Full detailed map**:
```yaml
layers:
  terrain: true
  water: true
  buildings: true
  roads: true
  labels: true
```
→ Download everything (current behavior)

### Implementation Strategy

1. **Config parser**: Read YAML and identify enabled layer types
2. **Feature mapping**: Map layer names to required OSM feature classes
   - `buildings` → `buildings` tag
   - `roads` → `highway` tag
   - `water` → `natural=water`, `waterway=*`
   - `landuse` → `landuse=*`, `natural=*`
3. **Targeted Overpass queries**: Modify OSM download to request only needed features
4. **Conditional DEM download**: Skip DEM if `terrain: false` (rare but possible)
5. **Cache organization**: Store different feature types separately for reuse

### Benefits

- **Larger maps possible**: Without building/road data, can process much bigger areas
- **Faster iteration**: Natural terrain maps render quickly without parsing urban features
- **Reduced bandwidth**: Important for remote/mobile workflows or API rate limits
- **Smaller cache**: Disk space savings for frequently updated areas
- **Energy efficiency**: Less data transfer and processing

### Technical Considerations

- Maintain backward compatibility (default to downloading all if not specified)
- Handle dependencies (e.g., labels might need roads/buildings for placement)
- Cache invalidation when config changes to include new layers
- Clear messaging when cached data lacks newly enabled layers
- Consider "download profiles": `minimal`, `natural`, `urban`, `full`

### Example Size Reduction

**100km² urban area** (estimated):
- Full download: ~200MB (buildings, roads, landuse, water, amenities)
- Natural only: ~5MB (DEM + water features)
- **Savings**: 97.5% reduction

This could enable rendering an entire province/state at natural terrain level without hitting data limits.

---

## Tiled Rendering for Large Maps

**Goal**: Break large map areas into smaller tiles, render each independently, then seamlessly stitch them together into a final high-resolution output.

### Problem

Rendering very large geographic areas at high resolution can exceed:
- Available system memory (RAM)
- Image processing limits (PIL/Pillow max image dimensions)
- Practical rendering time for single-pass operations
- GPU memory for terrain processing

### Solution

**Divide-and-conquer approach**: Split the GeoJSON boundary into a grid of overlapping tiles, render each tile separately, then merge into final composite image.

### Workflow

1. **Tile Grid Generation**
   - Parse input GeoJSON boundary
   - Calculate optimal tile size based on target DPI and memory limits
   - Create overlapping tile boundaries (e.g., 10% overlap for seamless blending)
   - Generate sub-GeoJSON files for each tile

2. **Parallel Rendering**
   - Render each tile using existing `generate-map.py` pipeline
   - All tiles use identical style configuration
   - Process tiles in parallel (multi-core) or sequentially
   - Save individual tile images

3. **Seamless Stitching**
   - Blend overlapping regions to avoid visible seams
   - Handle edge cases (partial tiles at boundaries)
   - Optional: feather/gradient blend in overlap zones
   - Crop to exact final boundary
   - Output single high-resolution composite image

### Configuration Example

```yaml
tiled_rendering:
  enabled: true
  tile_size_pixels: 8000  # Max dimension per tile
  overlap_percent: 10     # Overlap for seamless blending
  parallel: true          # Render tiles in parallel
  max_workers: 4          # Number of parallel processes
  
  # Optional: manual grid specification
  # grid: {rows: 3, cols: 4}
```

Or command-line:
```bash
python scripts/generate-map-tiled.py \
  --boundary data/large-region.geojson \
  --config maps/large-map.yaml \
  --tile-size 8000 \
  --overlap 10 \
  --parallel 4 \
  --output output/large-composite.tif
```

### Benefits

- **Memory efficiency**: Each tile uses manageable memory regardless of total map size
- **Parallelization**: Leverage multi-core CPUs to render tiles simultaneously
- **Fault tolerance**: If one tile fails, re-render only that tile
- **Resume capability**: Cache completed tiles, resume from failures
- **Extreme resolution**: No practical limit on final output size
- **Preview tiles**: Render low-res tiles first to verify layout before full render

### Technical Considerations

#### Overlap Handling
- **Why overlap?** Prevents visible seams from edge artifacts, filter effects, hillshading
- **Blend methods**: 
  - Linear gradient in overlap zone
  - Alpha feathering
  - Distance-weighted averaging
- **Minimum overlap**: Depends on filter sizes (unsharp mask, crater effects)

#### Data Continuity
- **DEM**: Download slightly beyond tile bounds to ensure hillshading continuity
- **Vector features**: Roads/rivers crossing tile boundaries need consistent rendering
- **Labels**: Avoid duplicate labels in overlap zones
- **Craters**: Handle craters that span tile boundaries
  - Option 1: Assign to one tile based on center point
  - Option 2: Render partial craters in each tile (may cause seam issues)

#### Elevation Normalization (Critical!)
**Problem**: If each tile normalizes DEM colors independently, elevation-to-color mapping will be inconsistent across tiles. A 2000m peak might appear dark brown in one tile but light tan in another if that tile contains a 3000m peak.

**Solution**: Global elevation range must be calculated before rendering any tiles.

**Implementation:**
1. **Pre-processing pass**: Download/sample DEM for entire region
2. **Calculate global min/max elevation** across all tiles
3. **Pass as parameters** to each tile renderer:
   ```yaml
   # Injected into each tile's render config
   terrain:
     elevation_range:
       min: 650  # meters - global minimum
       max: 3450 # meters - global maximum
     normalization: "global"  # or "local" for independent tiles
   ```
4. **Consistent color mapping**: All tiles use same elevation→color transfer function
5. **Hillshading consistency**: Use same light angle and intensity parameters

**Alternative approaches:**
- **Percentile-based**: Use 2nd-98th percentile instead of absolute min/max (handles outliers)
- **Adaptive zones**: For very large areas with distinct regions (mountains + plains), allow multiple elevation zones
- **Manual override**: Let user specify elevation range in config for full control

**Performance consideration**: Global DEM scan adds upfront cost but essential for visual consistency. Can use downsampled DEM for this first pass to speed it up.

#### Tile Size Optimization
- **Too small**: More tiles, longer total time, more seams to blend
- **Too large**: Defeats memory savings purpose
- **Optimal**: Match typical safe memory limit (~4-8GB for PIL), around 8000-12000px per tile

#### Parallel Processing
- I/O contention: Limit workers to avoid disk thrashing
- Memory monitoring: Don't launch more workers than available RAM
- Progress tracking: Show overall % complete across all tiles

### Implementation Components

1. **Tile grid calculator**: `scripts/calculate-tile-grid.py`
   - Input: GeoJSON boundary, target tile size
   - Output: Grid of tile boundaries (GeoJSON collection)

2. **Tiled renderer**: `scripts/generate-map-tiled.py`
   - Orchestrates tile generation
   - Manages parallel workers
   - Tracks progress

3. **Image stitcher**: `scripts/stitch-tiles.py`
   - Loads rendered tile images
   - Blends overlaps
   - Outputs final composite
   - Supports TIFF, PNG with optional compression

4. **Preview mode**: Low-res tiles for quick layout verification

### Example Use Cases

- **Province/state-scale natural terrain maps**: Render entire Alberta at 300 DPI
- **Multi-city urban maps**: Show several cities with surrounding terrain
- **Poster-size prints**: 48" × 96" at 600 DPI = 28800 × 57600 pixels
- **Mural projects**: Wall-sized maps for public spaces
- **Stitched panoramas**: Extra-wide aspect ratios (10:1 or wider)

### Cache Strategy

- Tile images cached separately: `cache/tiles/{map_name}/tile_{row}_{col}.tif`
- Invalidation: Re-render only tiles affected by config/data changes
- Smart detection: Check if style config changed (re-render all) vs. data update (re-render affected tiles)

---

## Crater Improvements (Completed)

- ✅ Increased crater ripple strength
- ✅ Enhanced floor debris prominence
- ✅ Applied unsharp mask to lava pools
- ✅ Irregular crater shapes (subtle distortion)
- ✅ Variable rim heights (0.12-0.25 ratio)
- ✅ Extended scree to inner wall zone for large flat floors
