# Next Steps

## Recently Completed

✅ **Text System Refactor** (March 22, 2026)

- Replaced complex halo/overlay text system with clean bordered info panel
- Implemented new layout: uniform thin borders + integrated footer panel
- Fixed map aspect ratio calculations for proper alignment
- Panel and map content now same width with exact mathematical precision
- Removed ~420 lines of obsolete code

---

## Immediate Next Steps

### 1. Test & Validate Text System

- [ ] Generate multiple maps with different dimensions to verify border/panel flexibility
- [ ] Test with various title lengths and stat combinations
- [ ] Confirm proper rendering at different DPI settings (300, 600)
- [ ] Verify consistent appearance across different aspect ratios

### 2. Apply Panel System to Other Styles

- [ ] Update remaining color schemes to use `info_panel` structure
- [ ] Test bordered layout with dark styles (dark_relief, lava)
- [ ] Adjust frame colors per style (e.g., lighter frame for dark backgrounds)
- [ ] Consider frameless option for styles that don't need borders

### 3. Physical Line Weights (High Priority)

- [ ] Implement point-based (pt) width system for all features
- [ ] Convert: `px = (pt / 72) * DPI`
- [ ] Update roads, buildings, waterways, borders to use physical units
- [ ] Test line weight consistency across print sizes (12x12, 18x18, 24x24)

---

## Medium-Term Goals

### 4. GPX Route System

- [ ] Implement GPX-first workflow (derive bbox from route bounds)
- [ ] Add configurable padding around route
- [ ] Create route rendering with hillshade-aware shading
- [ ] Design `porcelain_ink_route` as first curated route style
- [ ] **Start/end point markers**
  - Start: concentric circles
  - End: checkered flag circle pattern
  - Implement using matplotlib patches for clean, scalable rendering
  - Style-aware colors (adapt to map background and frame)
  - Handle overlap detection for loop routes (merge or offset when too close)
  - Ensure markers scale properly with map size and DPI
- [ ] **Elevation profile as integrated border element**
  - Filled silhouette that replaces/becomes bottom border (0.03-0.05 height)
  - Sits between map area and text panel
  - Width matches map (aligned like panel)
  - Style-aware coloring (matches frame aesthetic)
  - Acts as visual separator, not traditional chart
  - No axes or gridlines - pure compositional element

### 5. Export System Refinement

- [ ] Validate 300 DPI output for all standard sizes
- [ ] Add PDF export option
- [ ] Implement safe margin calculations
- [ ] Test deterministic output (same inputs = same output)

### 6. Style Locking & Presets

- [ ] Finalize 4-5 core styles for initial Etsy launch
- [ ] Lock internal parameters (no user tweaking)
- [ ] Document each style's visual identity
- [ ] Create style comparison images for listings

---

## Long-Term Considerations

### 7. Location Framing Intelligence

- [ ] Automatic bbox derivation from place names
- [ ] Square-first framing with smart padding
- [ ] Consistent visual centering across locations

### 8. Smart Text Placement

- [ ] Terrain-aware positioning (avoid placing text over mountains)
- [ ] Dynamic position adjustment based on map features

### 9. Etsy Listing Preparation

- [ ] Generate hero images for initial listings (Banff, Vancouver Island, Iceland)
- [ ] Create style comparison mockups
- [ ] Prepare room mockups and detail shots
- [ ] Draft personalization examples

---

## Technical Debt / Cleanup

- [ ] Review and consolidate DEM caching strategy
- [ ] Optimize memory usage for large maps (24x24 at 600 DPI)
- [ ] Add comprehensive error handling for missing data
- [ ] Document configuration file structure and options
- [ ] Create example configs for common use cases

---

## Questions to Resolve

1. Should frame be optional per style, or always present when panel enabled?
2. What's the minimum panel height before text becomes unreadable?
3. Should stats support more than 3 items? Auto-wrap or fixed layout?
4. Border thickness: should it scale with canvas size or stay constant in physical units?
5. Route rendering: single universal approach or style-specific rendering modes?

---

## Notes

- Focus on **consistency** and **repeatability** first
- Avoid feature creep - stick to curated preset approach
- Test each change across multiple styles and sizes
- Document what works before moving to next feature
