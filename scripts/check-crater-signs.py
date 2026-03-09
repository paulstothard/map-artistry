#!/usr/bin/env python3
"""Quick check of crater elevation values"""

import numpy as np

# Simulate crater D parameters
radius_km = 1.5
depth_m = radius_km * 1000 * 0.3  # 450m
rim_height_ratio = 0.08
rim_height = depth_m * rim_height_ratio  # 36m

print(f"Crater D parameters:")
print(f"  Radius: {radius_km} km")
print(f"  Depth: {depth_m} m (relative to baseline)")
print(f"  Rim height: {rim_height} m (above baseline)")
print(f"  Rim/Depth ratio: {rim_height/depth_m:.3f}")
print()

# Show crater profile values
print("Crater profile (delta from baseline):")
print(f"  Floor center: {-depth_m} m (deepest point)")
print(f"  Bowl edge: ~{-depth_m * 0.01} m (nearly baseline)")
print(f"  Wall: ~{-depth_m * 0.01 * 0.5 * 0.5} m (slight dip)")
print(f"  Rim peak: +{rim_height} m (above baseline)")
print(f"  Rim outer: 0 m (returns to baseline)")
print(f"  Ejecta: 0 m (flat at baseline)")
print()

print("Total relief (rim to floor):")
print(f"  {rim_height + depth_m} m")
print()

print("DIAGNOSIS:")
if rim_height / depth_m > 0.15:
    print("  ⚠️  Rim might look too high (>15% of depth)")
else:
    print("  ✓ Rim ratio looks reasonable")
    
if depth_m > 400:
    print("  ⚠️  Depth might be excessive for this size crater")
else:
    print("  ✓ Depth looks reasonable")
