#!/usr/bin/env python3
"""
Merge a config overlay into a base config file.

Usage:
    merge-config.py base.yaml overlay.yaml output.yaml

The overlay is deep-merged into the base config, allowing you to override
specific settings without rewriting the entire config file.
"""

import sys
import yaml
from pathlib import Path
from typing import Any, Dict


def deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge overlay dict into base dict.

    - If both values are dicts, recurse
    - Otherwise, overlay value replaces base value
    """
    result = base.copy()

    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def main():
    if len(sys.argv) != 4:
        print("Usage: merge-config.py base.yaml overlay.yaml output.yaml")
        sys.exit(1)

    base_path = Path(sys.argv[1])
    overlay_path = Path(sys.argv[2])
    output_path = Path(sys.argv[3])

    # Load base config
    with open(base_path, "r") as f:
        base = yaml.safe_load(f)

    # Load overlay config
    with open(overlay_path, "r") as f:
        overlay = yaml.safe_load(f)

    # Merge
    merged = deep_merge(base, overlay)

    # Write result
    with open(output_path, "w") as f:
        yaml.dump(merged, f, sort_keys=False, default_flow_style=False)

    print(f"✓ Merged {overlay_path.name} into {base_path.name} → {output_path}")


if __name__ == "__main__":
    main()
