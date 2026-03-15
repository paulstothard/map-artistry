# Config Overlays

## Naming Convention

To customize a map, create an overlay file in this directory named:

```
{location}-{scheme}-overlay.yaml
```

**Examples:**

- `victoria-coral-overlay.yaml`
- `edmonton-natural-overlay.yaml`
- `vancouver-island-satellite-overlay.yaml`

## Workflow

1. Run a map to generate the base config (e.g., `just victoria-coral`)
2. Copy `output/victoria-coral/config.yaml` to `configs/victoria-coral-overlay.yaml`
3. Edit the overlay file to change only what you want to customize
4. Run the map again - your overlay will be automatically merged

The overlay is merged into the base config, so you only need to include the values you want to
change.
