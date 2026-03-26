# Next Steps

## Multi-Route GPX Support (Single Region)

### Goal
Allow a map build for one region to render multiple GPX rides in the same output, with clear visual differentiation on both the map and the elevation profile.

### Primary Use Case
For a city (example: Edmonton), render a single map that shows a rider's favorite routes together so they can compare coverage, overlap, and terrain context at a glance.

### Why
Current route workflows support one GPX track per render. For route collections (e.g., training blocks, event variants, comparison rides), we need to visualize several rides together while keeping each ride identifiable.

### Product Requirements
- Accept multiple GPX inputs for region-based route builds.
- Draw all routes on the map in distinct styles (at minimum: distinct colors).
- Represent all included routes in the elevation profile in a way that preserves route identity.
- Provide a clear legend/key that links route identity across map lines and elevation profile lines.
- Support user-controlled route metadata display (e.g., custom labels, total distance, elevation gain), rather than hard-coding one format.
- Preserve existing single-GPX behavior as a backward-compatible path.

### UX / Visualization Options
- **Map layer:** assign each route a color from a route palette, with optional per-route outline.
- **Elevation profile:**
  - Option A: overlay all profiles with matching route colors.
  - Option B: stacked/small-multiple profiles (one mini-profile per route).
  - Option C: combined profile with route-segment coloring and explicit ordering markers.
- **Legend:** route name + color swatch + optional distance/elevation stats per route.

### Technical Scope
- `justfile`
  - Add/extend route build commands to accept multiple GPX files (repeatable arg or delimiter format).
- `scripts/generate-config.py`
  - Support route arrays in config output.
  - Emit per-route style metadata (color, label, ordering).
- `scripts/generate-map.py`
  - Render multiple route geometries.
  - Render multi-route elevation profile and legend.
- Route context/stats scripts
  - Support per-route and aggregate metrics where relevant.
- `README.md`
  - Document new CLI usage and examples.
  - Explain profile rendering mode(s) and legend behavior.

### Data / Config Design Notes
- Add a `routes` collection in config (instead of single `route_gpx` only), for example:
  - route id
  - source gpx path
  - display name
  - color / outline
  - enabled flag
- Add route metadata display settings (global and per-route), for example:
  - `show_metadata` toggle
  - metadata fields to include (`distance`, `elev_gain`, custom text)
  - aggregate summary option (e.g., total distance across all routes)
- Keep support for existing `route_gpx` and auto-upgrade to one-item `routes` internally.

### Phased Implementation Plan

#### Phase 0 — Design Finalization (No Code)
- Lock CLI shape for multi-GPX input.
- Choose default elevation profile mode (overlay vs stacked).
- Define metadata model: per-route fields vs aggregate summary vs both.
- Define visual rules for color assignment (auto palette + optional user overrides).

#### Phase 1 — Config & CLI Foundation
- Extend `justfile` route command interface to accept multiple GPX sources.
- Extend `scripts/generate-config.py` to emit `routes[]` while preserving `route_gpx` compatibility.
- Add validation rules for duplicate/invalid GPX paths and empty route lists.
- Keep rendering behavior unchanged for single-route calls.

#### Phase 2 — Multi-Route Map Rendering
- Update `scripts/generate-map.py` to draw all routes in deterministic order.
- Apply per-route styles (color/outline) with readable defaults.
- Add map legend entries mapping route name ↔ color.
- Handle overlap/readability cases (alpha, z-order, optional outlines).

#### Phase 3 — Elevation Profile for Multiple Routes
- Implement selected profile mode:
  - Overlay profiles with route-matched colors, or
  - Stacked mini-profiles for readability.
- Add route identity markers so users can distinguish lines unambiguously.
- Validate behavior for short/long and heavily overlapping routes.

#### Phase 4 — Metadata Display System
- Add configurable metadata block(s) for multi-route outputs.
- Support both user-defined text and computed metrics (distance/elevation).
- Add optional aggregate metrics (e.g., total distance) for route collections.

#### Phase 5 — Docs, Examples, and Hardening
- Update `README.md` with multi-GPX command patterns and screenshots.
- Add at least one Edmonton multi-route example set.
- Add regression checks to ensure single-route outputs are unchanged.
- Validate performance and visual clarity with larger route counts.

### Open Questions
- Preferred CLI shape for multiple GPX files:
  - repeated flag (e.g., `--gpx file1 --gpx file2`)
  - list arg (e.g., comma-separated)
  - glob/folder input
- Default profile mode: overlay vs stacked?
- How to handle route ordering semantics (input order vs distance/date sorting)?
- How many routes should be supported before readability degrades?
- What metadata should be default-visible (none, per-route metrics, aggregate totals)?
- Should metadata prioritize user-entered values, computed values, or both when present?

### Acceptance Criteria
- A region build with 3+ GPX files renders successfully.
- Each route is visually distinguishable on-map and in-profile.
- Legend clearly maps route names to colors.
- Metadata display is user-configurable and supports both per-route and aggregate summaries.
- Single-route builds render identically to today.
- Docs include at least one multi-route command example.
