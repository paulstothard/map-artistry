#!/usr/bin/env python3
# Copyright (c) 2026 Paul Stothard
# SPDX-License-Identifier: MIT

import argparse
import json
import math
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable, GeocoderServiceError


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _load_gpx_points(gpx_path: Path):
    tree = ET.parse(gpx_path)
    root = tree.getroot()

    points = []
    for elem in root.iter():
        name = _local_name(elem.tag)
        if name not in {"trkpt", "rtept"}:
            continue
        lat = elem.attrib.get("lat")
        lon = elem.attrib.get("lon")
        if lat is None or lon is None:
            continue
        try:
            points.append((float(lat), float(lon)))
        except ValueError:
            continue

    if not points:
        raise ValueError(f"No route points found in GPX file: {gpx_path}")

    return points


def _haversine_m(lat1, lon1, lat2, lon2):
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


def _sample_route_points(points, sample_count):
    if sample_count <= 0:
        return []
    if len(points) <= sample_count:
        return points

    cumulative = [0.0]
    for (lat1, lon1), (lat2, lon2) in zip(points[:-1], points[1:]):
        cumulative.append(cumulative[-1] + _haversine_m(lat1, lon1, lat2, lon2))

    total_m = cumulative[-1]
    if total_m <= 0:
        step = max(1, len(points) // sample_count)
        return points[::step][:sample_count]

    start_frac = 0.05
    end_frac = 0.95
    targets = [
        total_m * (start_frac + (end_frac - start_frac) * i / (sample_count - 1))
        for i in range(sample_count)
    ]

    sampled = []
    cursor = 0
    for target in targets:
        while cursor < len(cumulative) - 1 and cumulative[cursor] < target:
            cursor += 1
        sampled.append(points[cursor])

    return sampled


def _extract_region_label(location):
    if location is None:
        return None
    addr = location.raw.get("address", {}) if hasattr(location, "raw") else {}

    for key in [
        "state",
        "province",
        "region",
        "county",
        "city",
        "town",
        "municipality",
        "country",
    ]:
        value = addr.get(key)
        if value:
            return str(value)

    return (
        location.address.split(",")[-2].strip()
        if getattr(location, "address", None)
        else None
    )


def _extract_country_code(location):
    if location is None or not hasattr(location, "raw"):
        return None
    addr = location.raw.get("address", {})
    code = addr.get("country_code")
    if not code:
        return None
    return str(code).strip().upper()


def _reverse_with_retry(geolocator, lat, lon, retries, timeout_s):
    delay = 0.6
    last_error = None

    for attempt in range(retries + 1):
        try:
            result = geolocator.reverse(
                (lat, lon),
                exactly_one=True,
                language="en",
                addressdetails=True,
                timeout=timeout_s,
            )
            return result, None, attempt
        except (
            GeocoderTimedOut,
            GeocoderUnavailable,
            GeocoderServiceError,
            TimeoutError,
            OSError,
        ) as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(delay)
                delay *= 2.0
            continue
        except Exception as exc:
            last_error = str(exc)
            break

    return None, last_error, retries


def _check_route_vs_boundary(sampled_points, boundary_path: Path):
    try:
        import geopandas as gpd
        from shapely.geometry import Point

        gdf = gpd.read_file(boundary_path)
        if gdf.empty:
            return {
                "status": "warn",
                "message": "Boundary file is empty; clip check skipped",
                "outside_count": 0,
                "sample_count": len(sampled_points),
            }

        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        else:
            gdf = gdf.to_crs("EPSG:4326")

        geometry_series = gdf.geometry
        if hasattr(geometry_series, "union_all"):
            geom = geometry_series.union_all()
        else:
            geom = gdf.unary_union
        outside_count = 0
        for lat, lon in sampled_points:
            p = Point(lon, lat)
            if not (geom.contains(p) or geom.touches(p)):
                outside_count += 1

        if outside_count > 0:
            return {
                "status": "warn",
                "message": "Some sampled route points fall outside buffered/aspect boundary",
                "outside_count": outside_count,
                "sample_count": len(sampled_points),
            }

        return {
            "status": "ok",
            "message": "Route samples fall within buffered/aspect boundary",
            "outside_count": 0,
            "sample_count": len(sampled_points),
        }

    except Exception as exc:
        return {
            "status": "warn",
            "message": f"Boundary clip check skipped: {exc}",
            "outside_count": 0,
            "sample_count": len(sampled_points),
        }


def analyze_route_context(
    gpx_path: Path,
    sample_count=15,
    retries=2,
    timeout_s=4.0,
    early_stop=True,
    boundary_path=None,
):
    points = _load_gpx_points(gpx_path)
    sampled = _sample_route_points(points, sample_count)

    geolocator = Nominatim(user_agent="map-artistry-route-context")
    labels = []
    country_codes = []
    errors = 0
    retries_used = 0

    for idx, (lat, lon) in enumerate(sampled):
        location, error, attempt_count = _reverse_with_retry(
            geolocator=geolocator,
            lat=lat,
            lon=lon,
            retries=retries,
            timeout_s=timeout_s,
        )
        retries_used += attempt_count

        if location is None:
            errors += 1
            continue

        label = _extract_region_label(location)
        if label:
            labels.append(label)

        country_code = _extract_country_code(location)
        if country_code:
            country_codes.append(country_code)

        if early_stop and len(labels) >= 7:
            counts = Counter(labels)
            _, top_count = counts.most_common(1)[0]
            if top_count >= math.ceil(len(labels) * 0.7):
                break

        if idx < len(sampled) - 1:
            time.sleep(0.25)

    label_counts = Counter(labels)
    country_counts = Counter(country_codes)
    best_label = label_counts.most_common(1)[0][0] if label_counts else None
    best_votes = label_counts.most_common(1)[0][1] if label_counts else 0
    best_country_code = country_counts.most_common(1)[0][0] if country_counts else None
    best_country_votes = country_counts.most_common(1)[0][1] if country_counts else 0
    success_count = len(labels)
    attempted = len(sampled)
    confidence = (best_votes / success_count) if success_count else 0.0
    country_confidence = (
        (best_country_votes / len(country_codes)) if country_codes else 0.0
    )

    boundary_check = None
    if boundary_path:
        boundary_check = _check_route_vs_boundary(sampled, Path(boundary_path))

    return {
        "status": "ok" if success_count > 0 else "warn",
        "gpx": str(gpx_path),
        "sample_count_requested": sample_count,
        "sample_count_used": attempted,
        "success_count": success_count,
        "error_count": errors,
        "retries_used": retries_used,
        "best_region": best_label,
        "best_votes": best_votes,
        "confidence": round(confidence, 3),
        "candidates": dict(label_counts.most_common(5)),
        "best_country_code": best_country_code,
        "best_country_votes": best_country_votes,
        "country_confidence": round(country_confidence, 3),
        "country_candidates": dict(country_counts.most_common(5)),
        "boundary_check": boundary_check,
    }


def _print_human(result):
    good = "✓"
    warn = "⚠"

    status = result.get("status", "warn")
    success_count = result.get("success_count", 0)
    sample_count_used = result.get("sample_count_used", 0)
    retries_used = result.get("retries_used", 0)
    best_region = result.get("best_region")
    best_votes = result.get("best_votes", 0)
    confidence = result.get("confidence", 0.0)
    best_country_code = result.get("best_country_code")
    best_country_votes = result.get("best_country_votes", 0)
    country_confidence = result.get("country_confidence", 0.0)
    candidates = result.get("candidates") or {}

    print("🧭 Route Context")
    print(
        f"   {good if status == 'ok' else warn} Reverse geocode: "
        f"{success_count}/{sample_count_used} successful "
        f"(retries used: {retries_used})"
    )

    if best_region:
        confidence_pct = int(round(confidence * 100))
        print(
            f"   {good} Best region: {best_region} "
            f"({best_votes} votes, {confidence_pct}% consensus)"
        )
    else:
        print(f"   {warn} No region consensus (continuing)")

    if best_country_code:
        cc_pct = int(round(country_confidence * 100))
        print(
            f"   {good} Best country: {best_country_code} "
            f"({best_country_votes} votes, {cc_pct}% consensus)"
        )

    if candidates:
        top = ", ".join(f"{name}:{count}" for name, count in candidates.items())
        print(f"   • Candidates: {top}")

    boundary_check = result.get("boundary_check")
    if boundary_check:
        icon = good if boundary_check["status"] == "ok" else warn
        message = boundary_check.get("message", "Boundary check complete")
        outside_count = boundary_check.get("outside_count", 0)
        sample_count = boundary_check.get("sample_count", 0)
        if outside_count > 0:
            print(f"   {icon} {message} ({outside_count}/{sample_count} outside)")
        else:
            print(f"   {icon} {message}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze GPX route context by reverse-geocoding sampled points"
    )
    parser.add_argument("--gpx", required=True, help="Path to GPX route file")
    parser.add_argument(
        "--boundary",
        default=None,
        help="Optional GeoJSON boundary to check route-in-boundary coverage",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=15,
        help="Number of distributed route sample points for reverse geocoding",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Retry attempts per reverse-geocode request",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=4.0,
        help="Per-request timeout (seconds)",
    )
    parser.add_argument(
        "--no-early-stop",
        action="store_true",
        help="Disable early-stop when consensus is already strong",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON only",
    )
    args = parser.parse_args()

    try:
        result = analyze_route_context(
            gpx_path=Path(args.gpx),
            sample_count=max(1, args.samples),
            retries=max(0, args.retries),
            timeout_s=max(0.5, args.timeout),
            early_stop=not args.no_early_stop,
            boundary_path=args.boundary,
        )
    except Exception as exc:
        result = {
            "status": "warn",
            "gpx": str(args.gpx),
            "error": str(exc),
            "message": "Route context analysis failed; continuing",
        }

    if args.json:
        print(json.dumps(result))
    else:
        _print_human(result)
        if result.get("status") == "warn" and result.get("error"):
            print(f"   ⚠ {result['message']}: {result['error']}")


if __name__ == "__main__":
    main()
