"""
Convert stroked paths to filled outlines.

Takes path commands (M, L, C, A, Z) with a stroke width and produces
closed filled path commands representing the outline of the stroke.

Algorithm:
1. Split path into subpaths (at M commands)
2. Flatten curves (C, A) into polylines
3. Offset polyline edges by ± stroke_width/2
4. Join offset edges with miter joins (bevel fallback)
5. Cap open subpaths with square caps
6. Close subpath outlines
"""

import math
from typing import List, Tuple

Point = Tuple[float, float]
Command = Tuple[str, List[float]]


def flatten_cubic(
    x0: float, y0: float,
    x1: float, y1: float,
    x2: float, y2: float,
    x3: float, y3: float,
    num_segments: int = 12,
) -> List[Point]:
    """Subdivide a cubic bezier into line segments.

    Returns list of points (excluding start point).
    """
    points = []
    for i in range(1, num_segments + 1):
        t = i / num_segments
        mt = 1.0 - t
        px = (mt * mt * mt * x0 +
              3 * mt * mt * t * x1 +
              3 * mt * t * t * x2 +
              t * t * t * x3)
        py = (mt * mt * mt * y0 +
              3 * mt * mt * t * y1 +
              3 * mt * t * t * y2 +
              t * t * t * y3)
        points.append((px, py))
    return points


def flatten_arc(
    cx: float, cy: float, r: float,
    start_deg: float, sweep_deg: float,
    num_segments: int = 12,
) -> List[Point]:
    """Subdivide a circular arc into line segments.

    Uses internal arc format: A cx, cy, r, startDeg, sweepDeg.
    Returns list of points (excluding start point).
    """
    points = []
    start_rad = math.radians(start_deg)
    sweep_rad = math.radians(sweep_deg)
    for i in range(1, num_segments + 1):
        t = i / num_segments
        angle = start_rad + t * sweep_rad
        px = cx + r * math.cos(angle)
        py = cy + r * math.sin(angle)
        points.append((px, py))
    return points


def split_subpaths(
    commands: List[Command],
) -> List[Tuple[List[Point], bool]]:
    """Split path commands into subpaths, each as a polyline.

    Flattens C and A commands into line segments.

    Returns list of (points, is_closed) tuples.
    """
    subpaths = []
    current_points: List[Point] = []
    cur_x, cur_y = 0.0, 0.0
    subpath_start_x, subpath_start_y = 0.0, 0.0
    is_closed = False

    def finish_subpath():
        nonlocal current_points, is_closed
        if len(current_points) >= 2:
            subpaths.append((list(current_points), is_closed))
        current_points = []
        is_closed = False

    for cmd, params in commands:
        if cmd == "M":
            finish_subpath()
            cur_x, cur_y = params[0], params[1]
            subpath_start_x, subpath_start_y = cur_x, cur_y
            current_points = [(cur_x, cur_y)]
            is_closed = False

        elif cmd == "L":
            cur_x, cur_y = params[0], params[1]
            current_points.append((cur_x, cur_y))

        elif cmd == "C":
            pts = flatten_cubic(
                cur_x, cur_y,
                params[0], params[1],
                params[2], params[3],
                params[4], params[5],
            )
            current_points.extend(pts)
            cur_x, cur_y = params[4], params[5]

        elif cmd == "A":
            pts = flatten_arc(
                params[0], params[1], params[2],
                params[3], params[4],
            )
            current_points.extend(pts)
            end_rad = math.radians(params[3] + params[4])
            cur_x = params[0] + params[2] * math.cos(end_rad)
            cur_y = params[1] + params[2] * math.sin(end_rad)

        elif cmd == "Z":
            is_closed = True
            cur_x, cur_y = subpath_start_x, subpath_start_y
            if current_points:
                sx, sy = current_points[0]
                lx, ly = current_points[-1]
                if abs(lx - sx) > 1e-6 or abs(ly - sy) > 1e-6:
                    current_points.append((sx, sy))

    finish_subpath()
    return subpaths


def offset_segment(
    p0: Point, p1: Point, offset: float
) -> Tuple[Point, Point]:
    """Compute offset line for a segment p0->p1.

    Offset is perpendicular, to the left when looking from p0 toward p1.
    """
    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    length = math.sqrt(dx * dx + dy * dy)
    if length < 1e-10:
        return (p0, p1)

    nx = -dy / length
    ny = dx / length

    q0 = (p0[0] + nx * offset, p0[1] + ny * offset)
    q1 = (p1[0] + nx * offset, p1[1] + ny * offset)
    return (q0, q1)


def line_intersection(
    p1: Point, p2: Point,
    p3: Point, p4: Point,
) -> Point:
    """Find intersection of lines (p1-p2) and (p3-p4).

    Returns midpoint of p2/p3 if lines are parallel.
    """
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4

    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-10:
        return ((p2[0] + p3[0]) / 2, (p2[1] + p3[1]) / 2)

    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom

    ix = x1 + t * (x2 - x1)
    iy = y1 + t * (y2 - y1)
    return (ix, iy)


def offset_polyline(
    points: List[Point],
    offset: float,
    miter_limit: float = 4.0,
) -> List[Point]:
    """Offset a polyline by a perpendicular distance.

    Uses miter joins at vertices, with bevel fallback when miter
    ratio exceeds miter_limit.
    """
    n = len(points)
    if n < 2:
        return list(points)

    segments = []
    for i in range(n - 1):
        seg = offset_segment(points[i], points[i + 1], offset)
        segments.append(seg)

    if not segments:
        return list(points)

    result = [segments[0][0]]

    for i in range(len(segments) - 1):
        inter = line_intersection(
            segments[i][0], segments[i][1],
            segments[i + 1][0], segments[i + 1][1],
        )

        corner = points[i + 1]
        miter_dx = inter[0] - corner[0]
        miter_dy = inter[1] - corner[1]
        miter_len = math.sqrt(miter_dx * miter_dx + miter_dy * miter_dy)

        if abs(offset) > 1e-10 and miter_len / abs(offset) > miter_limit:
            # Bevel fallback
            result.append(segments[i][1])
            result.append(segments[i + 1][0])
        else:
            result.append(inter)

    result.append(segments[-1][1])
    return result


def outline_open_subpath(
    points: List[Point],
    half_width: float,
) -> List[Command]:
    """Create outline for an open subpath with square end caps.

    Traces left side forward, end cap, right side backward, start cap, close.
    """
    if len(points) < 2:
        return []

    left = offset_polyline(points, half_width)
    right = offset_polyline(points, -half_width)

    # Square cap at the end
    p_last = points[-1]
    p_prev = points[-2]
    dx = p_last[0] - p_prev[0]
    dy = p_last[1] - p_prev[1]
    length = math.sqrt(dx * dx + dy * dy)
    if length > 1e-10:
        cap_dx = dx / length * half_width
        cap_dy = dy / length * half_width
    else:
        cap_dx, cap_dy = 0.0, 0.0

    end_cap_left = (left[-1][0] + cap_dx, left[-1][1] + cap_dy)
    end_cap_right = (right[-1][0] + cap_dx, right[-1][1] + cap_dy)

    # Square cap at the start
    p_first = points[0]
    p_second = points[1]
    dx0 = p_first[0] - p_second[0]
    dy0 = p_first[1] - p_second[1]
    length0 = math.sqrt(dx0 * dx0 + dy0 * dy0)
    if length0 > 1e-10:
        cap_dx0 = dx0 / length0 * half_width
        cap_dy0 = dy0 / length0 * half_width
    else:
        cap_dx0, cap_dy0 = 0.0, 0.0

    start_cap_left = (left[0][0] + cap_dx0, left[0][1] + cap_dy0)
    start_cap_right = (right[0][0] + cap_dx0, right[0][1] + cap_dy0)

    # Build path: left forward → end cap → right backward → start cap → close
    cmds: List[Command] = []
    cmds.append(("M", [left[0][0], left[0][1]]))
    for pt in left[1:]:
        cmds.append(("L", [pt[0], pt[1]]))
    cmds.append(("L", [end_cap_left[0], end_cap_left[1]]))
    cmds.append(("L", [end_cap_right[0], end_cap_right[1]]))
    cmds.append(("L", [right[-1][0], right[-1][1]]))
    for pt in reversed(right[:-1]):
        cmds.append(("L", [pt[0], pt[1]]))
    cmds.append(("L", [start_cap_right[0], start_cap_right[1]]))
    cmds.append(("L", [start_cap_left[0], start_cap_left[1]]))
    cmds.append(("Z", []))

    return cmds


def outline_closed_subpath(
    points: List[Point],
    half_width: float,
) -> List[Command]:
    """Create outline for a closed subpath.

    Produces outer + inner loops with evenodd fill rule.
    """
    if len(points) < 3:
        return outline_open_subpath(points, half_width)

    # Ensure closed
    pts = list(points)
    if (abs(pts[0][0] - pts[-1][0]) > 1e-6 or
            abs(pts[0][1] - pts[-1][1]) > 1e-6):
        pts.append(pts[0])

    # Wrap for proper miter at closure point
    wrapped = [pts[-2]] + pts + [pts[1]]

    left_wrapped = offset_polyline(wrapped, half_width)
    right_wrapped = offset_polyline(wrapped, -half_width)

    # Strip wrapping points
    left = left_wrapped[1:-1]
    right = right_wrapped[1:-1]

    # Outer loop (left offset, forward)
    cmds: List[Command] = []
    cmds.append(("M", [left[0][0], left[0][1]]))
    for pt in left[1:]:
        cmds.append(("L", [pt[0], pt[1]]))
    cmds.append(("Z", []))

    # Inner loop (right offset, forward)
    cmds.append(("M", [right[0][0], right[0][1]]))
    for pt in right[1:]:
        cmds.append(("L", [pt[0], pt[1]]))
    cmds.append(("Z", []))

    return cmds


def stroke_to_outlines(
    paths: List[dict],
    stroke_width_override: float = None,
) -> List[dict]:
    """Convert stroked paths to filled outline paths.

    Non-stroke paths are passed through unchanged.
    Stroke paths (source='stroke') are expanded into filled outlines.
    """
    result = []
    for path in paths:
        if path.get("source") != "stroke":
            result.append(path)
            continue

        sw = stroke_width_override if stroke_width_override is not None else path.get("stroke_width", 1.0)
        half_w = sw / 2.0

        if half_w < 1e-10:
            continue

        commands = path["commands"]
        subpaths = split_subpaths(commands)

        for points, is_closed in subpaths:
            if len(points) < 2:
                continue

            if is_closed:
                outline_cmds = outline_closed_subpath(points, half_w)
                fill_rule = "evenodd"
            else:
                outline_cmds = outline_open_subpath(points, half_w)
                fill_rule = "nonzero"

            if outline_cmds:
                result.append({
                    "commands": outline_cmds,
                    "fill_rule": fill_rule,
                })

    return result
