"""The simulated body as a stick figure, worked out from the sheet's lengths and nothing else.

The body's own frame: x forward, y left, z up, with its middle at the origin. A link runs along its own x.
Every length is in metres and every angle in degrees.
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence

Vec = tuple[float, float, float]
Mat = tuple[Vec, Vec, Vec]

IDENTITY: Mat = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def rot(axis: str, deg: float) -> Mat:
    """pitch turns forward toward up; yaw turns forward toward left; roll turns left toward up."""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    if axis == "pitch":
        return ((c, 0.0, -s), (0.0, 1.0, 0.0), (s, 0.0, c))
    if axis == "yaw":
        return ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))
    return ((1.0, 0.0, 0.0), (0.0, c, -s), (0.0, s, c))


def mul(a: Mat, b: Mat) -> Mat:
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def apply(m: Mat, v: Sequence[float]) -> Vec:
    return tuple(sum(m[i][k] * v[k] for k in range(3)) for i in range(3))


def skeleton(frame, pose: Mapping[str, float]) -> list[dict]:
    """Each link as a line in the body's own frame: where it starts, where it ends."""
    turned: dict[str, Mat] = {"body": IDENTITY}
    ends: dict[str, Vec] = {}
    lines = []
    for link in frame.links:
        angle = link.zero_deg + link.turns * pose.get(link.joint, 0.0) if link.joint else link.zero_deg
        m = mul(turned[link.parent], rot(link.axis, angle))
        start = link.at_m if link.parent == "body" else ends[link.parent]
        along = apply(m, (link.length_m, 0.0, 0.0))
        end = (start[0] + along[0], start[1] + along[1], start[2] + along[2])
        turned[link.id], ends[link.id] = m, end
        lines.append({"id": link.id, "a": start, "b": end, "joint": link.joint, "foot": link.foot})
    return lines


def stance(lines: list[dict]) -> tuple[float, float]:
    """How the body leans when its feet are on level ground: (roll, pitch).

    Roll is positive with the right side down, pitch with the nose up. The ground is the plane that best fits
    the feet; a body with fewer than three feet is taken to stand level.
    """
    feet = [line["b"] for line in lines if line["foot"]]
    if len(feet) < 3:
        return 0.0, 0.0
    n = len(feet)
    sx = sum(p[0] for p in feet)
    sy = sum(p[1] for p in feet)
    sz = sum(p[2] for p in feet)
    sxx = sum(p[0] * p[0] for p in feet)
    syy = sum(p[1] * p[1] for p in feet)
    sxy = sum(p[0] * p[1] for p in feet)
    sxz = sum(p[0] * p[2] for p in feet)
    syz = sum(p[1] * p[2] for p in feet)
    # z = a x + b y + c, by least squares
    det = sxx * (syy * n - sy * sy) - sxy * (sxy * n - sy * sx) + sx * (sxy * sy - syy * sx)
    if abs(det) < 1e-12:
        return 0.0, 0.0
    a = (sxz * (syy * n - sy * sy) - sxy * (syz * n - sy * sz) + sx * (syz * sy - syy * sz)) / det
    b = (sxx * (syz * n - sy * sz) - sxz * (sxy * n - sy * sx) + sx * (sxy * sz - syz * sx)) / det
    return math.degrees(math.atan(-b)), math.degrees(math.atan(-a))


def tilt(roll_deg: float, pitch_deg: float) -> float:
    """How far the body's up is from the world's up."""
    c = math.cos(math.radians(roll_deg)) * math.cos(math.radians(pitch_deg))
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def figure(frame, pose: Mapping[str, float], roll_deg: float, pitch_deg: float) -> dict:
    """The figure standing in the world, its lowest point on the ground: lines to draw, in metres."""
    lines = skeleton(frame, pose)
    world = mul(rot("pitch", pitch_deg), rot("roll", roll_deg))
    half_l, half_w = frame.length_m / 2, frame.width_m / 2
    corners = [(half_l, half_w, 0.0), (half_l, -half_w, 0.0), (-half_l, -half_w, 0.0), (-half_l, half_w, 0.0)]
    outline = [apply(world, c) for c in corners]
    placed = [{**line, "a": apply(world, line["a"]), "b": apply(world, line["b"])} for line in lines]
    lowest = min([p[2] for p in outline] + [p[2] for line in placed for p in (line["a"], line["b"])])

    def lift(p: Vec) -> list[float]:
        return [round(p[0], 5), round(p[1], 5), round(p[2] - lowest, 5)]

    return {
        "outline": [lift(c) for c in outline],
        "lines": [{**line, "a": lift(line["a"]), "b": lift(line["b"])} for line in placed],
    }
