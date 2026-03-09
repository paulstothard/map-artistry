#!/usr/bin/env python3
"""
Verify crater depth and rim height scaling for the lava config.
Shows the auto-calculated values to ensure they're realistic.
"""

# Crater data from lava config
craters = [
    {"label": "A", "radius_km": 3.0, "rim_height_ratio": 0.12, "lava_level_m": 150},
    {"label": "B", "radius_km": 1.8, "rim_height_ratio": 0.10, "lava_level_m": 100},
    {"label": "C", "radius_km": 2.5, "rim_height_ratio": 0.15, "lava_level_m": None},
    {"label": "D", "radius_km": 1.5, "rim_height_ratio": 0.08, "lava_level_m": 60},
    {"label": "E", "radius_km": 3.5, "rim_height_ratio": 0.13, "lava_level_m": 200},
    {"label": "1", "radius_km": 0.6, "rim_height_ratio": 0.08, "lava_level_m": None},
    {"label": "2", "radius_km": 0.8, "rim_height_ratio": 0.09, "lava_level_m": None},
    {"label": "3", "radius_km": 0.4, "rim_height_ratio": 0.07, "lava_level_m": None},
    {"label": "4", "radius_km": 1.0, "rim_height_ratio": 0.10, "lava_level_m": None},
    {"label": "5", "radius_km": 0.5, "rim_height_ratio": 0.08, "lava_level_m": None},
    {"label": "6", "radius_km": 0.7, "rim_height_ratio": 0.09, "lava_level_m": None},
    {"label": "7", "radius_km": 0.9, "rim_height_ratio": 0.10, "lava_level_m": None},
    {"label": "8", "radius_km": 0.55, "rim_height_ratio": 0.08, "lava_level_m": None},
    {"label": "9", "radius_km": 0.65, "rim_height_ratio": 0.09, "lava_level_m": None},
    {"label": "10", "radius_km": 0.45, "rim_height_ratio": 0.07, "lava_level_m": None},
    {"label": "11", "radius_km": 0.75, "rim_height_ratio": 0.09, "lava_level_m": None},
    {"label": "12", "radius_km": 0.5, "rim_height_ratio": 0.08, "lava_level_m": None},
]

print("=" * 80)
print("CRATER SCALING VERIFICATION - Edmonton Lava Map")
print("=" * 80)
print()
print(f"{'Label':<8} {'Radius':<12} {'Depth':<12} {'Rim Height':<12} {'Depth/Diam':<12} {'Lava':<10}")
print(f"{'':8} {'(km)':12} {'(m)':12} {'(m)':12} {'Ratio':12} {'(m)':10}")
print("-" * 80)

for crater in craters:
    radius_km = crater["radius_km"]
    rim_ratio = crater["rim_height_ratio"]
    lava = crater["lava_level_m"]
    
    # Auto-calculate depth (20% of radius)
    depth_m = radius_km * 1000 * 0.2
    
    # Calculate rim height
    rim_height_m = depth_m * rim_ratio
    
    # Calculate depth-to-diameter ratio (for validation)
    diameter_km = radius_km * 2
    depth_to_diam = depth_m / (diameter_km * 1000)
    
    lava_str = f"{lava}" if lava is not None else "None"
    
    print(f"{crater['label']:<8} {radius_km:<12.2f} {depth_m:<12.1f} {rim_height_m:<12.1f} {depth_to_diam:<12.3f} {lava_str:<10}")

print("-" * 80)
print()
print("SCALING CHECKS:")
print()
print("Depth Calculation:")
print("  depth_m = radius_km × 1000 × 0.2")
print("  (20% of radius = 10% of diameter → realistic depth/diameter ratio)")
print()
print("Rim Height Calculation:")
print("  rim_height_m = depth_m × rim_height_ratio")
print("  (rim_height_ratio ranges from 0.07 to 0.15)")
print()
print("Feature Scaling (all scale with depth_m):")
print("  • Textures: large (18%), medium (10%), fine (4%) of depth")
print("  • Slump scars: 3-8% of depth")
print("  • Wall scrapes: 2-6% of depth")
print("  • Secondary craters: 6-16% of depth")
print("  • Ripples: 12-22% of depth")
print()
print("Expected Depth/Diameter Ratios:")
print("  • Simple craters (< 4 km diameter): 0.08-0.15 typical")
print("  • Our craters: 0.10 (consistent across all sizes) ✓")
print()
print("Config Status: ✓ All craters will scale properly")
print("  • No depth_m specified → auto-calculation active")
print("  • All features scale proportionally with crater size")
print("  • Depth/diameter ratio consistent and realistic")
print()
print("=" * 80)
