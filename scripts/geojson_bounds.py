#!/usr/bin/env python3
# Copyright (c) 2026 Paul Stothard
# SPDX-License-Identifier: MIT

"""Utilities for working with GeoJSON boundaries near the antimeridian."""

from __future__ import annotations

import json
import math
from typing import Any

import geopandas as gpd
from shapely.geometry import box


def wrap_longitude(lon: float) -> float:
    """Wrap longitude to [-180, 180]."""
    while lon < -180.0:
        lon += 360.0
    while lon > 180.0:
        lon -= 360.0
    return lon


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return False


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _extract_center_lon(gdf: gpd.GeoDataFrame) -> float | None:
    if "center_lon" not in gdf.columns:
        return None

    for value in gdf["center_lon"]:
        parsed = _parse_float(value)
        if parsed is not None:
            return wrap_longitude(parsed)

    return None


def _parse_bbox(raw_bbox: Any) -> tuple[float, float, float, float] | None:
    if raw_bbox is None:
        return None

    bbox = raw_bbox

    if isinstance(raw_bbox, str):
        raw_bbox = raw_bbox.strip()
        if not raw_bbox:
            return None
        try:
            bbox = json.loads(raw_bbox)
        except json.JSONDecodeError:
            parts = [p.strip() for p in raw_bbox.split(",")]
            if len(parts) == 4:
                bbox = parts
            else:
                return None

    if not isinstance(bbox, (list, tuple)):
        if hasattr(bbox, "tolist"):
            bbox = bbox.tolist()
        elif hasattr(bbox, "__iter__") and not isinstance(bbox, (dict, bytes)):
            bbox = list(bbox)
        else:
            return None

    if len(bbox) != 4:
        return None

    try:
        south, north, west, east = (float(v) for v in bbox)
    except (TypeError, ValueError):
        return None

    if not all(math.isfinite(v) for v in (south, north, west, east)):
        return None

    return south, north, west, east


def _clean_segment(
    segment: tuple[float, float, float, float],
) -> tuple[float, float, float, float] | None:
    minx, miny, maxx, maxy = segment

    minx = max(-180.0, float(minx))
    maxx = min(180.0, float(maxx))
    miny = max(-90.0, float(miny))
    maxy = min(90.0, float(maxy))

    if minx >= maxx or miny >= maxy:
        return None

    return minx, miny, maxx, maxy


def get_bbox_segments(gdf: gpd.GeoDataFrame) -> list[tuple[float, float, float, float]]:
    """Return one or two bbox segments in EPSG:4326 (minx, miny, maxx, maxy)."""
    if gdf.empty:
        raise ValueError("Cannot compute bounds for empty GeoDataFrame")

    raw_bbox = None
    if "bbox" in gdf.columns:
        for value in gdf["bbox"]:
            parsed = _parse_bbox(value)
            if parsed is not None:
                raw_bbox = parsed
                break

    crosses_antimeridian = None
    if "crosses_antimeridian" in gdf.columns:
        for value in gdf["crosses_antimeridian"]:
            if value is not None and str(value).strip() != "":
                crosses_antimeridian = _to_bool(value)
                break

    if raw_bbox is not None:
        south, north, west, east = raw_bbox
        west = wrap_longitude(west)
        east = wrap_longitude(east)

        if crosses_antimeridian is None:
            crosses_antimeridian = west > east

        if not crosses_antimeridian:
            segment = _clean_segment((west, south, east, north))
            if segment is not None:
                return [segment]
        else:
            segments = []
            left = _clean_segment((west, south, 180.0, north))
            right = _clean_segment((-180.0, south, east, north))
            if left is not None:
                segments.append(left)
            if right is not None:
                segments.append(right)
            if segments:
                return segments

    minx, miny, maxx, maxy = gdf.total_bounds
    return [(float(minx), float(miny), float(maxx), float(maxy))]


def select_primary_bbox_segment(
    gdf: gpd.GeoDataFrame,
    segments: list[tuple[float, float, float, float]] | None = None,
) -> tuple[float, float, float, float]:
    """Choose the segment with the largest overlap area with the geometry."""
    if segments is None:
        segments = get_bbox_segments(gdf)

    if len(segments) == 1:
        return segments[0]

    center_lon = _extract_center_lon(gdf)
    if center_lon is not None:
        for segment in segments:
            if segment[0] <= center_lon <= segment[2]:
                return segment

    geometry_union = gdf.geometry.union_all()
    best_segment = segments[0]
    best_overlap = -1.0

    for segment in segments:
        seg_poly = box(segment[0], segment[1], segment[2], segment[3])
        overlap = float(geometry_union.intersection(seg_poly).area)
        if overlap > best_overlap:
            best_overlap = overlap
            best_segment = segment

    return best_segment


def clip_to_bbox_segment(
    gdf: gpd.GeoDataFrame,
    segment: tuple[float, float, float, float],
) -> gpd.GeoDataFrame:
    """Clip a GeoDataFrame to a single bbox segment."""
    clipper = gpd.GeoDataFrame(
        [{"geometry": box(segment[0], segment[1], segment[2], segment[3])}],
        crs=gdf.crs,
    )
    clipped = gpd.clip(gdf, clipper)
    clipped = clipped[clipped.geometry.notnull()]
    clipped = clipped[~clipped.is_empty]
    return clipped


def apply_primary_segment_clip(
    gdf: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, tuple[float, float, float, float] | None, bool]:
    """
    Clip antimeridian-crossing boundaries to a primary bbox segment.

    Returns (processed_gdf, primary_segment, was_antimeridian_split).
    """
    segments = get_bbox_segments(gdf)
    if len(segments) <= 1:
        return gdf, (segments[0] if segments else None), False

    primary = select_primary_bbox_segment(gdf, segments)
    clipped = clip_to_bbox_segment(gdf, primary)

    if clipped.empty:
        return gdf, primary, True

    return clipped, primary, True
