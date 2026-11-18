"""Geometry shared by the Python exporter and the TypeScript canvas contract."""

from __future__ import annotations

import math

DIRECTIONS = {
    "left": (-1, 0),
    "right": (1, 0),
    "top": (0, -1),
    "bottom": (0, 1),
    "top-left": (-1, -1),
    "top-right": (1, -1),
    "bottom-left": (-1, 1),
    "bottom-right": (1, 1),
}


def anchor(box: dict, port: str) -> tuple[float, float]:
    x, y, w, h = (box[k] for k in ("x", "y", "width", "height"))
    return {
        "left": (x, y + h / 2),
        "right": (x + w, y + h / 2),
        "top": (x + w / 2, y),
        "bottom": (x + w / 2, y + h),
        "top-left": (x, y),
        "top-right": (x + w, y),
        "bottom-left": (x, y + h),
        "bottom-right": (x + w, y + h),
    }[port]


def route_points(doc: dict, edge: dict) -> list[tuple[float, float]]:
    view = doc["layout"]["edges"][edge["id"]]
    start = anchor(doc["layout"]["nodes"][edge["source"]], view["source_port"])
    end = anchor(doc["layout"]["nodes"][edge["target"]], view["target_port"])
    points = [(p["x"], p["y"]) for p in view["points"]]
    if view["route"] == "straight":
        return [start, end]
    if view["route"] == "orthogonal":
        if not points:
            if view["source_port"] in ("left", "right"):
                mid = (start[0] + end[0]) / 2
                points = [(mid, start[1]), (mid, end[1])]
            else:
                mid = (start[1] + end[1]) / 2
                points = [(start[0], mid), (end[0], mid)]
        return [start, *points, end]
    if not points:
        distance = max(40, math.dist(start, end) / 2)
        a, b = DIRECTIONS[view["source_port"]], DIRECTIONS[view["target_port"]]
        points = [
            (start[0] + a[0] * distance, start[1] + a[1] * distance),
            (end[0] + b[0] * distance, end[1] + b[1] * distance),
        ]
    return [start, *points, end]


def point_on_route(points: list, route: str, t: float) -> tuple[float, float]:
    if route == "bezier":
        a, b, c, d = points
        return tuple(
            (1 - t) ** 3 * a[i]
            + 3 * (1 - t) ** 2 * t * b[i]
            + 3 * (1 - t) * t * t * c[i]
            + t**3 * d[i]
            for i in (0, 1)
        )
    lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
    remaining = sum(lengths) * t
    for a, b, length in zip(points, points[1:], lengths):
        if remaining <= length and length:
            return (
                a[0] + (b[0] - a[0]) * remaining / length,
                a[1] + (b[1] - a[1]) * remaining / length,
            )
        remaining -= length
    return points[-1]


def attachment_position(doc: dict, attachment: dict) -> tuple[float, float]:
    if attachment["kind"] == "node":
        box = doc["layout"]["nodes"][attachment["id"]]
        return box["x"] + box["width"] / 2, box["y"]
    if attachment["kind"] == "edge":
        edge = next(e for e in doc["edges"] if e["id"] == attachment["id"])
        return point_on_route(
            route_points(doc, edge), doc["layout"]["edges"][edge["id"]]["route"], 0.5
        )
    path = next(p for p in doc["paths"] if p["id"] == attachment["id"])
    boxes = [
        doc["layout"]["nodes"][n]
        for n in path["node_ids"]
        if not any(v["id"] == n and v["kind"] == "source" for v in doc["nodes"])
    ]
    if not boxes:
        return 0, 0
    return (
        (min(b["x"] for b in boxes) + max(b["x"] + b["width"] for b in boxes)) / 2,
        min(b["y"] for b in boxes) - 20,
    )
