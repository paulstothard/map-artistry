#!/usr/bin/env python3
# Copyright (c) 2026 Paul Stothard
# SPDX-License-Identifier: MIT
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
from typing import Any, Dict, List, Tuple


def merge_layers(
    base_layers: Dict[str, Any], overlay_layers: Dict[str, Any]
) -> Tuple[Dict[str, Any], List[str]]:
    """Merge only layer keys that already exist in the base config.

    Unknown overlay layer keys are skipped to avoid creating invalid partial
    layer entries that can break map rendering.
    """
    result = base_layers.copy()
    skipped: List[str] = []

    for layer_key, layer_value in overlay_layers.items():
        if layer_key not in result:
            skipped.append(layer_key)
            continue

        base_value = result[layer_key]
        if isinstance(base_value, dict) and isinstance(layer_value, dict):
            result[layer_key] = deep_merge(base_value, layer_value)
        else:
            result[layer_key] = layer_value

    return result, skipped


def deep_merge(
    base: Dict[str, Any],
    overlay: Dict[str, Any],
    warnings: List[str] | None = None,
) -> Dict[str, Any]:
    """
    Recursively merge overlay dict into base dict.

    - If both values are dicts, recurse
    - Otherwise, overlay value replaces base value
    """
    result = base.copy()

    for key, value in overlay.items():
        if (
            key == "layers"
            and key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            merged_layers, skipped_keys = merge_layers(result[key], value)
            result[key] = merged_layers
            if warnings is not None and skipped_keys:
                warnings.append(
                    "Skipped unknown overlay layer keys: "
                    + ", ".join(sorted(skipped_keys))
                )
        elif (
            key in result and isinstance(result[key], dict) and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value, warnings)
        else:
            result[key] = value

    return result


def validate_layers(config: Dict[str, Any]) -> List[str]:
    """Validate merged layer schema before writing config."""
    issues: List[str] = []
    layers = config.get("layers")
    if layers is None:
        return issues
    if not isinstance(layers, dict):
        return ["Top-level 'layers' must be a mapping"]

    for layer_key, layer_value in layers.items():
        if not isinstance(layer_value, dict):
            issues.append(f"layers.{layer_key} must be a mapping")
            continue
        if "default" not in layer_value:
            issues.append(f"layers.{layer_key} is missing required 'default' section")

    return issues


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
    warnings: List[str] = []
    merged = deep_merge(base, overlay, warnings)

    issues = validate_layers(merged)
    if issues:
        print("✗ Merged config is invalid:")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)

    # Write result
    with open(output_path, "w") as f:
        yaml.dump(merged, f, sort_keys=False, default_flow_style=False)

    print(f"✓ Merged {overlay_path.name} into {base_path.name} → {output_path}")
    for warning in warnings:
        print(f"⚠️  {warning}")


if __name__ == "__main__":
    main()
