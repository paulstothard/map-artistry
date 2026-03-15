# Config Overlays

## Overview

Overlay files let you customize specific maps without editing the auto-generated configs. They are merged with the base configuration during the build process.

## Naming Convention

Overlay files must follow this pattern:

```
{location}-{scheme}-overlay.yaml
```

**Examples:**

- `victoria-coral-overlay.yaml`
- `edmonton-natural-overlay.yaml`
- `vancouver-island-satellite-overlay.yaml`

## Quick Workflow

### Create a new overlay

```bash
# 1. Build a map first to generate the base config
just edmonton coral

# 2. Create overlay template (copies the base config)
just create-overlay edmonton coral

# 3. Edit the overlay file
# configs/edmonton-coral-overlay.yaml

# 4. Rebuild to apply your changes
just edmonton coral
```

The `create-overlay` command will:
- ✅ Copy `config-base.yaml` from output as a starting template
- ✅ Never overwrite existing overlays
- ❌ Fail if the base config doesn't exist yet (run the map first)

## How It Works

When you run a map build:

1. **Base config generated**: `output/{location}-{scheme}/config-base.yaml`
   - Auto-generated from your data and color scheme
   - Recreated on every build

2. **Overlay applied** (if exists): `configs/{location}-{scheme}-overlay.yaml`
   - Your custom modifications
   - Merged into the base config

3. **Final config created**: `output/{location}-{scheme}/config.yaml`
   - Result of base + overlay merge
   - Used to render the map

## What to Include in Overlays

You only need to include the specific values you want to change. The overlay is merged recursively, so you can override individual properties without repeating the entire config.

**Example overlay** (`edmonton-coral-overlay.yaml`):

```yaml
map:
  info:
    text: "Custom Title"
    show: true
  hillshade:
    azimuth: 270
    altitude: 60

layers:
  water:
    linewidth: 0.5
    color: "#FF0000"
```

This will only change those specific values while keeping everything else from the base config.

## Tips

- Start with `create-overlay` to get a full template
- Delete everything you don't want to customize
- Smaller overlays are easier to maintain
- Test changes by rebuilding: `just {location} {scheme}`
