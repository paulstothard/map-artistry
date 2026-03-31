#!/usr/bin/env python3
# Copyright (c) 2026 Paul Stothard
# SPDX-License-Identifier: MIT
"""Build a mixed-panel montage from a CSV manifest.

Supports all panel types already available in `justfile`:
- region only (just build)
- region + GPX route (just build-route)
- GPX-only region derivation (just build-gpx)

The manifest supports comment lines that start with '#'.
"""

import argparse
import csv
from datetime import datetime
import math
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageColor


# Generated map outputs can legitimately exceed Pillow's default pixel limit.
Image.MAX_IMAGE_PIXELS = None


@dataclass
class Panel:
    index: int
    mode: str
    region: str
    gpx: str
    scheme: str
    buffer_km: str
    text_title: str
    text_subtitle: str
    text_location: str
    text_stats: str
    overlay_file: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create montage panels from mixed region / route manifest rows."
    )
    parser.add_argument(
        "--manifest",
        required=True,
        help="CSV manifest path (required)",
    )
    parser.add_argument(
        "--final-width-in",
        type=float,
        default=24.0,
        help="Final montage width in inches",
    )
    parser.add_argument(
        "--final-height-in",
        type=float,
        default=18.0,
        help="Final montage height in inches",
    )
    parser.add_argument("--final-dpi", type=int, default=300, help="Final montage DPI")
    parser.add_argument(
        "--spacing-px", type=int, default=10, help="Spacing between panels in pixels"
    )
    parser.add_argument(
        "--canvas-color",
        default="white",
        help=(
            "Canvas background color for spacing/letterbox areas "
            '(e.g., "white", "#f4f1ea", "rgb(20,20,20)")'
        ),
    )
    parser.add_argument(
        "--cols",
        default="auto",
        help='Grid columns number or "auto" (default: auto)',
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Final montage output file. Default resolves to "
            "<just output_dir>/montage-<run-name>.png (honors WORKSPACE_DIR)."
        ),
    )
    parser.add_argument(
        "--maps-dir",
        default=None,
        help=(
            "Directory where panel maps are rendered. Default resolves to "
            "<just output_dir>/montage-maps (honors WORKSPACE_DIR)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print computed plan without rendering",
    )
    return parser.parse_args()


def evaluate_just_path(expr: str) -> Path:
    """Resolve a justfile expression while inheriting current environment."""
    result = subprocess.run(
        ["just", "--evaluate", expr],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip())


def parse_positive_float(raw: str, field: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if value <= 0:
        raise ValueError(f"{field} must be greater than zero")
    return value


def validate_buffer_value(raw: str, field: str) -> str:
    """Validate per-row buffer value. Allowed: positive number or 'auto'."""
    value = raw.strip().lower()
    if value == "auto":
        return value
    parse_positive_float(value, field)
    return value


def parse_canvas_color(raw: str) -> tuple[int, int, int]:
    """Parse flexible canvas color values into an RGB tuple."""
    try:
        parsed = ImageColor.getrgb(raw)
    except ValueError as exc:
        raise SystemExit(
            "❌ Invalid --canvas-color value. "
            "Use a named color, hex code, or rgb(...)."
        ) from exc

    if len(parsed) == 4:
        return parsed[:3]
    return parsed


def read_manifest_rows(path: Path) -> list[dict[str, str]]:
    """Read CSV rows while allowing comment lines beginning with '#' ."""
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")

    with path.open("r", encoding="utf-8", newline="") as handle:
        filtered_lines: list[str] = []
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            filtered_lines.append(line)

    if not filtered_lines:
        raise ValueError("Manifest contains no usable CSV content")

    reader = csv.DictReader(filtered_lines)
    if not reader.fieldnames:
        raise ValueError("Manifest must include a header row")

    return [dict(row) for row in reader]


def read_manifest(path: Path) -> list[Panel]:
    panels: list[Panel] = []

    rows = read_manifest_rows(path)
    fields = {name.strip().lower() for name in rows[0].keys() if name}
    required_base = {"region", "gpx", "scheme", "buffer_km"}
    if not required_base.issubset(fields):
        raise ValueError("Manifest must include columns: region,gpx,scheme,buffer_km")

    for idx, row in enumerate(rows, start=2):
        normalized = {str(k).strip().lower(): (v or "").strip() for k, v in row.items()}

        if not any(normalized.values()):
            continue

        region = normalized.get("region", "")
        gpx = normalized.get("gpx", "")

        if not region and not gpx:
            continue

        if region and gpx:
            mode = "build-route"
        elif region:
            mode = "build"
        else:
            mode = "build-gpx"

        scheme = normalized.get("scheme", "")
        if not scheme:
            raise ValueError(f"row {idx} scheme is required")

        buffer_km = normalized.get("buffer_km", "")
        if not buffer_km:
            raise ValueError(f"row {idx} buffer_km is required")
        buffer_km = validate_buffer_value(buffer_km, f"row {idx} buffer_km")

        text_title = normalized.get("text_title", "")
        if not text_title:
            if region:
                text_title = region
            elif gpx:
                text_title = Path(gpx).stem.replace("-", " ").replace("_", " ").strip()

        panels.append(
            Panel(
                index=idx,
                mode=mode,
                region=region,
                gpx=gpx,
                scheme=scheme,
                buffer_km=buffer_km,
                text_title=text_title,
                text_subtitle=normalized.get("text_subtitle", ""),
                text_location=normalized.get("text_location", ""),
                text_stats=normalized.get("text_stats", ""),
                overlay_file=normalized.get("overlay_file", ""),
            )
        )

    if not panels:
        raise ValueError("No usable panel rows found in manifest")

    return panels


def resolve_manifest_path(raw_path: str, manifest_path: Path) -> Path:
    """Resolve manifest-provided relative paths against manifest location first."""
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    manifest_relative = (manifest_path.parent / candidate).resolve()
    if manifest_relative.exists():
        return manifest_relative
    return candidate


def validate_panels(panels: list[Panel], manifest_path: Path) -> None:
    """Run quick, permissive validation for required row inputs only."""
    issues: list[str] = []

    for panel in panels:
        row = panel.index

        # Exactly one of region-only, region+gpx, or gpx-only must be represented.
        if not panel.region and not panel.gpx:
            issues.append(f"row {row}: either region or gpx is required")

        if not panel.scheme:
            issues.append(f"row {row}: scheme is required")

        if not panel.buffer_km:
            issues.append(f"row {row}: buffer_km is required")

        # If GPX is referenced, ensure the file exists relative to cwd or absolute path.
        if panel.gpx:
            gpx_path = resolve_manifest_path(panel.gpx, manifest_path)
            if not gpx_path.exists():
                issues.append(f"row {row}: gpx file not found: {panel.gpx}")

        if panel.overlay_file:
            overlay_path = resolve_manifest_path(panel.overlay_file, manifest_path)
            if not overlay_path.exists():
                issues.append(
                    f"row {row}: overlay_file not found: {panel.overlay_file}"
                )

    if issues:
        joined = "\n  - " + "\n  - ".join(issues)
        raise SystemExit(
            "❌ Manifest validation failed. Fix the following issues:" + joined
        )


def choose_cols_auto(n: int, target_w: int, target_h: int) -> int:
    target_aspect = target_w / target_h
    best_cols = 1
    best_score = float("inf")
    for cols in range(1, n + 1):
        rows = math.ceil(n / cols)
        grid_aspect = cols / rows
        empty_slots = cols * rows - n
        score = abs(math.log(grid_aspect / target_aspect)) + (empty_slots * 0.20)
        if score < best_score:
            best_score = score
            best_cols = cols
    return best_cols


def shell_run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def select_single_panel_image(panel_dir: Path, panel_index: int) -> Path:
    """Select exactly one rendered image for a panel directory."""
    matches = sorted(panel_dir.rglob("*.png")) + sorted(panel_dir.rglob("*.jpg"))
    if not matches:
        raise SystemExit(
            f"❌ Panel {panel_index:03d}: no rendered image found in {panel_dir}"
        )
    if len(matches) > 1:
        listed = "\n      ".join(str(path) for path in matches)
        raise SystemExit(
            f"❌ Panel {panel_index:03d}: expected one image, found {len(matches)} in {panel_dir}:\n"
            f"      {listed}"
        )
    return matches[0]


def create_run_dir(base_dir: Path) -> Path:
    """Create a unique per-run directory without deleting previous runs."""
    base_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    candidate = base_dir / f"run-{stamp}"
    suffix = 1
    while candidate.exists():
        suffix += 1
        candidate = base_dir / f"run-{stamp}-{suffix}"

    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def compose_montage(
    images: list[Path],
    output_path: Path,
    cols: int,
    rows: int,
    spacing_px: int,
    tile_w_px: int,
    tile_h_px: int,
    target_w_px: int,
    target_h_px: int,
    dpi: int,
    canvas_color: tuple[int, int, int],
) -> None:
    """Compose final montage directly from selected panel images."""
    canvas = Image.new("RGB", (target_w_px, target_h_px), canvas_color)

    for idx, image_path in enumerate(images):
        row = idx // cols
        col = idx % cols

        cell_x = spacing_px + col * (tile_w_px + spacing_px)
        cell_y = spacing_px + row * (tile_h_px + spacing_px)

        with Image.open(image_path) as panel_img:
            panel_rgb = panel_img.convert("RGB")

            scale = min(tile_w_px / panel_rgb.width, tile_h_px / panel_rgb.height)
            new_w = max(1, int(round(panel_rgb.width * scale)))
            new_h = max(1, int(round(panel_rgb.height * scale)))

            if new_w != panel_rgb.width or new_h != panel_rgb.height:
                panel_rgb = panel_rgb.resize((new_w, new_h), Image.LANCZOS)

            x = cell_x + (tile_w_px - panel_rgb.width) // 2
            y = cell_y + (tile_h_px - panel_rgb.height) // 2
            canvas.paste(panel_rgb, (x, y))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, optimize=True, dpi=(dpi, dpi))


def build_panel(
    panel: Panel,
    map_w_in: float,
    map_h_in: float,
    dpi: int,
    panel_dir: Path,
    manifest_path: Path,
) -> None:
    panel_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "just",
        panel.mode,
        "--width",
        f"{map_w_in:.4f}",
        "--height",
        f"{map_h_in:.4f}",
        "--dpi",
        str(dpi),
        "--output-dir",
        str(panel_dir),
    ]

    # For 'auto', rely on just recipe defaults (matches generate-example-maps behavior).
    if panel.buffer_km != "auto":
        cmd.extend(["--buffer-km", panel.buffer_km])

    if panel.text_title:
        cmd.extend(["--text-title", panel.text_title])
    if panel.text_subtitle:
        cmd.extend(["--text-subtitle", panel.text_subtitle])
    if panel.text_location:
        cmd.extend(["--text-location", panel.text_location])
    if panel.text_stats:
        cmd.extend(["--text-stats", panel.text_stats])

    if panel.mode == "build":
        cmd.extend([panel.region, panel.scheme])
    elif panel.mode == "build-route":
        cmd.extend(
            [
                panel.region,
                str(resolve_manifest_path(panel.gpx, manifest_path)),
                panel.scheme,
            ]
        )
    else:
        cmd.extend([str(resolve_manifest_path(panel.gpx, manifest_path)), panel.scheme])

    shell_run(cmd)


def region_slug(region: str) -> str:
    slug = region.lower()
    slug = re.sub(r"[, ]", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug


def route_slug_from_gpx(gpx_path: str, manifest_path: Path) -> str:
    stem = resolve_manifest_path(gpx_path, manifest_path).stem.lower()
    slug = re.sub(r"[^a-z0-9]", "-", stem)
    slug = re.sub(r"-+", "-", slug)
    return slug


def expected_overlay_filename(panel: Panel, manifest_path: Path) -> str:
    if panel.mode == "build":
        location = region_slug(panel.region)
        return f"{location}-{panel.scheme}-overlay.yaml"
    if panel.mode == "build-route":
        location = region_slug(panel.region)
        route_name = route_slug_from_gpx(panel.gpx, manifest_path)
        return f"{location}-route-{route_name}-{panel.scheme}-overlay.yaml"
    route_name = route_slug_from_gpx(panel.gpx, manifest_path)
    location = f"route-{route_name}"
    return f"{location}-{panel.scheme}-overlay.yaml"


def apply_overlay_if_needed(
    panel: Panel,
    manifest_path: Path,
    configs_dir: Path,
) -> tuple[Path | None, Path | None]:
    """Copy optional overlay preset into just-required overlay filename.

    Returns (target_overlay_path, backup_path_if_existing).
    """
    if not panel.overlay_file:
        return None, None

    source = resolve_manifest_path(panel.overlay_file, manifest_path)
    if not source.exists():
        raise SystemExit(
            f"❌ Overlay preset not found for row {panel.index}: {panel.overlay_file}"
        )

    configs_dir.mkdir(parents=True, exist_ok=True)
    target = configs_dir / expected_overlay_filename(panel, manifest_path)
    backup = None
    if target.exists():
        backup = target.with_suffix(target.suffix + ".montage-backup")
        shutil.copy2(target, backup)

    shutil.copy2(source, target)
    return target, backup


def restore_overlay(target: Path | None, backup: Path | None) -> None:
    """Restore previous overlay (if any) and remove montage temporary overlay."""
    if target is None:
        return

    if backup is not None and backup.exists():
        shutil.move(str(backup), str(target))
        return

    if target.exists():
        target.unlink()


def main() -> None:
    args = parse_args()

    if shutil.which("just") is None:
        raise SystemExit("❌ 'just' is required but was not found in PATH.")

    if args.final_width_in <= 0 or args.final_height_in <= 0:
        raise SystemExit(
            "❌ --final-width-in and --final-height-in must be greater than zero."
        )
    if args.final_dpi <= 0:
        raise SystemExit("❌ --final-dpi must be greater than zero.")
    if args.spacing_px < 0:
        raise SystemExit("❌ --spacing-px must be zero or greater.")
    canvas_color = parse_canvas_color(args.canvas_color)

    manifest_path = Path(args.manifest)

    # Resolve output defaults through just so WORKSPACE_DIR is respected.
    try:
        output_dir = evaluate_just_path("output_dir")
        configs_dir = evaluate_just_path("configs_dir")
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            "❌ Failed to resolve just output/configs paths. Ensure you run from repo root and justfile is available."
        ) from exc

    output_file_arg = Path(args.output) if args.output else None
    maps_dir = Path(args.maps_dir) if args.maps_dir else output_dir / "montage-maps"

    panels = read_manifest(manifest_path)
    validate_panels(panels, manifest_path)
    panel_count = len(panels)

    target_w_px = int(round(args.final_width_in * args.final_dpi))
    target_h_px = int(round(args.final_height_in * args.final_dpi))

    if args.cols.lower() == "auto":
        cols = choose_cols_auto(panel_count, target_w_px, target_h_px)
    else:
        try:
            cols = int(args.cols)
        except ValueError as exc:
            raise SystemExit("❌ --cols must be an integer or 'auto'.") from exc
        if cols <= 0:
            raise SystemExit("❌ --cols must be greater than zero.")

    rows = math.ceil(panel_count / cols)

    tile_w_px = (target_w_px - ((cols + 1) * args.spacing_px)) // cols
    tile_h_px = (target_h_px - ((rows + 1) * args.spacing_px)) // rows
    if tile_w_px <= 0 or tile_h_px <= 0:
        raise SystemExit(
            "❌ Tile dimensions are not positive. Adjust final size, dpi, spacing, or columns."
        )

    map_w_in = tile_w_px / args.final_dpi
    map_h_in = tile_h_px / args.final_dpi

    print("🧮 Montage layout")
    print(f"   Panels: {panel_count}")
    print(f"   Grid: {cols} cols x {rows} rows")
    print(
        f"   Final: {args.final_width_in}in x {args.final_height_in}in @ {args.final_dpi} DPI ({target_w_px}x{target_h_px}px)"
    )
    print(
        f"   Per-panel target: {map_w_in:.4f}in x {map_h_in:.4f}in ({tile_w_px}x{tile_h_px}px)"
    )
    print(f"   Canvas color: {args.canvas_color} -> rgb{canvas_color}")
    print("   Buffer rule: buffer_km is required in each manifest row")
    print(
        "   Workspace: output paths resolved through just output_dir (WORKSPACE_DIR-aware)"
    )
    print(f"   Manifest: {manifest_path}")
    print(f"   Workspace configs dir: {configs_dir}")
    print(f"   Panel run root: {maps_dir} (previous runs are preserved)")
    if output_file_arg is not None:
        print(f"   Output file: {output_file_arg}")
    else:
        print("   Output file: <just output_dir>/montage-<run-name>.png")
    print()

    if args.dry_run:
        print("🧪 Dry run only; no maps rendered.")
        return

    run_dir = create_run_dir(maps_dir)
    if output_file_arg is not None:
        output_file = output_file_arg
    else:
        output_file = output_dir / f"montage-{run_dir.name}.png"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    print("🗺️  Rendering panel maps...")
    rendered_images: list[Path] = []
    for i, panel in enumerate(panels, start=1):
        panel_dir = run_dir / f"panel-{i:03d}"
        mode_label = panel.mode.replace("build", "region").replace("-route", "+gpx")
        overlay_target_name = expected_overlay_filename(panel, manifest_path)
        if panel.overlay_file:
            print(
                f"   → Panel {i:03d}: {mode_label} | scheme={panel.scheme} | overlay={panel.overlay_file} -> {overlay_target_name}"
            )
        else:
            print(f"   → Panel {i:03d}: {mode_label} | scheme={panel.scheme}")

        target_overlay, backup_overlay = apply_overlay_if_needed(
            panel,
            manifest_path,
            configs_dir,
        )
        try:
            build_panel(
                panel,
                map_w_in,
                map_h_in,
                args.final_dpi,
                panel_dir,
                manifest_path,
            )
        finally:
            restore_overlay(target_overlay, backup_overlay)
        rendered_images.append(select_single_panel_image(panel_dir, i))

    print()
    print("🖼️  Composing montage directly from selected panel images...")
    compose_montage(
        images=rendered_images,
        output_path=output_file,
        cols=cols,
        rows=rows,
        spacing_px=args.spacing_px,
        tile_w_px=tile_w_px,
        tile_h_px=tile_h_px,
        target_w_px=target_w_px,
        target_h_px=target_h_px,
        dpi=args.final_dpi,
        canvas_color=canvas_color,
    )

    print()
    print("✅ Done")
    print(f"   Output montage: {output_file}")
    print(f"   Source maps (this run): {run_dir}")


if __name__ == "__main__":
    main()
