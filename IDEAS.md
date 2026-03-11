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

## Crater Improvements (Completed)

- ✅ Increased crater ripple strength
- ✅ Enhanced floor debris prominence
- ✅ Applied unsharp mask to lava pools
- ✅ Irregular crater shapes (subtle distortion)
- ✅ Variable rim heights (0.12-0.25 ratio)
- ✅ Extended scree to inner wall zone for large flat floors
