#!/usr/bin/env python3
"""
Redact GPX files by trimming points from the start/end of each track/route.

This helps hide sensitive home/start locations before sharing GPX files.

Examples:
  python scripts/redact-gpx-start-end.py downloads/cycling-routes/*.gpx \
    --out-dir downloads/cycling-routes-redacted --trim-start-m 800 --trim-end-m 800

  python scripts/redact-gpx-start-end.py myride.gpx --in-place --trim-each-m 1000
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371008.8
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return r * c


def _lat_lon(elem: ET.Element) -> tuple[float, float] | None:
    lat = elem.attrib.get("lat")
    lon = elem.attrib.get("lon")
    if lat is None or lon is None:
        return None
    try:
        return float(lat), float(lon)
    except ValueError:
        return None


def _cumdist(points: list[ET.Element]) -> list[float]:
    d = [0.0]
    for i in range(1, len(points)):
        p0 = _lat_lon(points[i - 1])
        p1 = _lat_lon(points[i])
        if p0 is None or p1 is None:
            d.append(d[-1])
            continue
        d.append(d[-1] + _haversine_m(p0[0], p0[1], p1[0], p1[1]))
    return d


def _trim_point_list(
    points: list[ET.Element],
    trim_start_m: float,
    trim_end_m: float,
    min_points: int,
) -> list[ET.Element]:
    if len(points) <= min_points:
        return points

    cum = _cumdist(points)
    total = cum[-1]
    if total <= 0:
        return points

    start_keep_dist = max(0.0, float(trim_start_m))
    end_keep_dist = max(0.0, total - max(0.0, float(trim_end_m)))

    if end_keep_dist <= start_keep_dist:
        return points

    start_idx = 0
    while start_idx < len(cum) and cum[start_idx] < start_keep_dist:
        start_idx += 1

    end_idx = len(cum) - 1
    while end_idx >= 0 and cum[end_idx] > end_keep_dist:
        end_idx -= 1

    if end_idx - start_idx + 1 < min_points:
        return points

    return points[start_idx : end_idx + 1]


def _replace_children(
    parent: ET.Element, child_tag_name: str, new_children: list[ET.Element]
):
    old_children = [c for c in list(parent) if _local_name(c.tag) == child_tag_name]
    if not old_children:
        return

    first_idx = list(parent).index(old_children[0])
    for c in old_children:
        parent.remove(c)
    for i, c in enumerate(new_children):
        parent.insert(first_idx + i, c)


def redact_gpx_file(
    in_path: Path,
    out_path: Path,
    trim_start_m: float,
    trim_end_m: float,
    min_points: int,
) -> tuple[int, int]:
    tree = ET.parse(in_path)
    root = tree.getroot()

    total_before = 0
    total_after = 0

    # Track segments: trk -> trkseg -> trkpt
    for trk in [e for e in root.iter() if _local_name(e.tag) == "trk"]:
        for trkseg in [e for e in list(trk) if _local_name(e.tag) == "trkseg"]:
            pts = [e for e in list(trkseg) if _local_name(e.tag) == "trkpt"]
            if not pts:
                continue
            total_before += len(pts)
            trimmed = _trim_point_list(pts, trim_start_m, trim_end_m, min_points)
            total_after += len(trimmed)
            _replace_children(trkseg, "trkpt", trimmed)

    # Route points: rte -> rtept
    for rte in [e for e in root.iter() if _local_name(e.tag) == "rte"]:
        pts = [e for e in list(rte) if _local_name(e.tag) == "rtept"]
        if not pts:
            continue
        total_before += len(pts)
        trimmed = _trim_point_list(pts, trim_start_m, trim_end_m, min_points)
        total_after += len(trimmed)
        _replace_children(rte, "rtept", trimmed)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(out_path, encoding="utf-8", xml_declaration=True)
    return total_before, total_after


def main():
    parser = argparse.ArgumentParser(
        description="Redact GPX start/end locations by trimming route distance from each side"
    )
    parser.add_argument("gpx_files", nargs="+", help="Input GPX file(s)")
    parser.add_argument(
        "--trim-start-m",
        type=float,
        default=750.0,
        help="Meters to trim from start (default: 750)",
    )
    parser.add_argument(
        "--trim-end-m",
        type=float,
        default=750.0,
        help="Meters to trim from end (default: 750)",
    )
    parser.add_argument(
        "--trim-each-m",
        type=float,
        default=None,
        help="Meters to trim from both start and end (overrides --trim-start-m/--trim-end-m)",
    )
    parser.add_argument(
        "--min-points",
        type=int,
        default=20,
        help="Minimum remaining points required to apply trim (default: 20)",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="downloads/cycling-routes-redacted",
        help="Output directory for redacted GPX files (ignored with --in-place)",
    )
    parser.add_argument(
        "--suffix",
        type=str,
        default="-redacted",
        help="Suffix appended to output filename stem (default: -redacted)",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite input files instead of writing copies",
    )
    args = parser.parse_args()

    if args.trim_each_m is not None:
        trim_start_m = float(args.trim_each_m)
        trim_end_m = float(args.trim_each_m)
    else:
        trim_start_m = float(args.trim_start_m)
        trim_end_m = float(args.trim_end_m)

    out_dir = Path(args.out_dir)
    processed = 0

    for file_str in args.gpx_files:
        in_path = Path(file_str)
        if not in_path.exists():
            print(f"[skip] Missing file: {in_path}")
            continue

        if args.in_place:
            out_path = in_path
        else:
            out_name = f"{in_path.stem}{args.suffix}{in_path.suffix}"
            out_path = out_dir / out_name

        try:
            before, after = redact_gpx_file(
                in_path,
                out_path,
                trim_start_m=trim_start_m,
                trim_end_m=trim_end_m,
                min_points=args.min_points,
            )
            removed = max(0, before - after)
            processed += 1
            print(
                f"[ok] {in_path.name} -> {out_path} | points: {before} -> {after} (removed {removed})"
            )
        except (ET.ParseError, OSError, ValueError) as e:
            print(f"[fail] {in_path}: {e}")

    if processed == 0:
        raise SystemExit("No GPX files processed")


if __name__ == "__main__":
    main()
