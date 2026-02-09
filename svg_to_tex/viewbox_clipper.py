"""
Clip SVG path commands to a rectangular viewBox boundary.

For seamless tiling, all geometry must be confined to the viewBox rectangle.
Paths entirely inside are kept as-is (preserving curves). Paths crossing
the boundary are flattened to polylines and clipped with Sutherland-Hodgman.

Pipeline position: after stroke_to_outlines(), before filter_filled_paths().
"""

import math
from typing import List, Tuple, Optional

from .stroke_outliner import flatten_cubic, flatten_arc

Point = Tuple[float, float]
Command = Tuple[str, List[float]]

# Epsilon for boundary-coincident point tests (SVG coordinate units).
# Points within this distance of the boundary are considered "inside".
_EPS = 0.01


def clip_paths_to_viewbox(
    paths: List[dict],
    viewbox: Tuple[float, float, float, float],
) -> List[dict]:
    """Clip all paths to the viewBox rectangle.

    Args:
        paths: List of {'commands': [...], 'fill_rule': str, ...}
        viewbox: (minX, minY, width, height)

    Returns:
        New list of path dicts with geometry clipped to viewBox.
        Paths fully outside are removed. Paths fully inside are
        returned unchanged.
    """
    min_x, min_y, w, h = viewbox
    rect = (min_x, min_y, min_x + w, min_y + h)
    result = []
    for path in paths:
        commands = path.get("commands", [])
        clipped = _clip_single_path(commands, rect)
        if clipped is not None and len(clipped) > 0:
            new_path = dict(path)
            new_path["commands"] = clipped
            result.append(new_path)
    return result


def _clip_single_path(
    commands: List[Command],
    rect: Tuple[float, float, float, float],
) -> Optional[List[Command]]:
    """Clip one path's commands to a rectangle.

    Returns None if the path is entirely outside.
    Returns original commands if entirely inside.
    Returns clipped M/L/Z commands if crossing boundary.
    """
    if not commands:
        return None

    subpaths = _split_into_subpaths(commands)
    if not subpaths:
        return None

    # Check if entire path is inside or outside
    all_inside = True
    all_outside = True
    for sp in subpaths:
        bbox = _subpath_bounds(sp)
        if bbox is None:
            continue
        if _is_inside_rect(bbox, rect):
            all_outside = False
        elif _is_outside_rect(bbox, rect):
            all_inside = False
        else:
            all_inside = False
            all_outside = False

    if all_outside:
        return None
    if all_inside:
        return commands

    # Some subpaths cross the boundary — flatten and clip each
    result_commands: List[Command] = []
    for sp in subpaths:
        bbox = _subpath_bounds(sp)
        if bbox is None:
            continue
        if _is_outside_rect(bbox, rect):
            continue
        if _is_inside_rect(bbox, rect):
            # Keep original commands for this subpath
            result_commands.extend(sp)
            continue

        # Flatten to polygon, clip, convert back
        polygon = _flatten_subpath_to_polygon(sp)
        if len(polygon) < 3:
            continue
        clipped_polys = _sutherland_hodgman_clip(polygon, rect)
        for poly in clipped_polys:
            result_commands.extend(_polygon_to_commands(poly))

    return result_commands if result_commands else None


def _split_into_subpaths(commands: List[Command]) -> List[List[Command]]:
    """Split a command list at M commands into individual subpaths."""
    subpaths: List[List[Command]] = []
    current: List[Command] = []

    for cmd, params in commands:
        if cmd == "M":
            if current:
                # Ensure previous subpath is closed
                if current[-1][0] != "Z":
                    current.append(("Z", []))
                subpaths.append(current)
            current = [("M", list(params))]
        else:
            current.append((cmd, list(params)))

    if current:
        if current[-1][0] != "Z":
            current.append(("Z", []))
        subpaths.append(current)

    return subpaths


def _subpath_bounds(
    commands: List[Command],
) -> Optional[Tuple[float, float, float, float]]:
    """Compute bounding box (minX, minY, maxX, maxY) of a subpath."""
    xs: List[float] = []
    ys: List[float] = []
    cx, cy = 0.0, 0.0

    for cmd, params in commands:
        if cmd == "M":
            cx, cy = params[0], params[1]
            xs.append(cx)
            ys.append(cy)
        elif cmd == "L":
            cx, cy = params[0], params[1]
            xs.append(cx)
            ys.append(cy)
        elif cmd == "C":
            # Include control points and endpoint
            xs.extend([params[0], params[2], params[4]])
            ys.extend([params[1], params[3], params[5]])
            cx, cy = params[4], params[5]
        elif cmd == "A":
            # Arc: cx, cy, r, startDeg, sweepDeg
            acx, acy, r = params[0], params[1], params[2]
            # Conservative bbox: center ± radius
            xs.extend([acx - r, acx + r])
            ys.extend([acy - r, acy + r])
            # Also include the actual endpoint
            start_rad = math.radians(params[3])
            sweep_rad = math.radians(params[4])
            end_rad = start_rad + sweep_rad
            xs.append(acx + r * math.cos(end_rad))
            ys.append(acy + r * math.sin(end_rad))
            cx = acx + r * math.cos(end_rad)
            cy = acy + r * math.sin(end_rad)

    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _is_inside_rect(
    bbox: Tuple[float, float, float, float],
    rect: Tuple[float, float, float, float],
) -> bool:
    """Check if a bounding box is entirely inside the clip rectangle."""
    bmin_x, bmin_y, bmax_x, bmax_y = bbox
    rmin_x, rmin_y, rmax_x, rmax_y = rect
    return (bmin_x >= rmin_x - _EPS and bmax_x <= rmax_x + _EPS and
            bmin_y >= rmin_y - _EPS and bmax_y <= rmax_y + _EPS)


def _is_outside_rect(
    bbox: Tuple[float, float, float, float],
    rect: Tuple[float, float, float, float],
) -> bool:
    """Check if a bounding box is entirely outside the clip rectangle."""
    bmin_x, bmin_y, bmax_x, bmax_y = bbox
    rmin_x, rmin_y, rmax_x, rmax_y = rect
    return (bmax_x < rmin_x - _EPS or bmin_x > rmax_x + _EPS or
            bmax_y < rmin_y - _EPS or bmin_y > rmax_y + _EPS)


def _flatten_subpath_to_polygon(
    commands: List[Command],
    segments_per_curve: int = 16,
) -> List[Point]:
    """Convert a subpath's commands to a polygon (list of points)."""
    points: List[Point] = []
    cx, cy = 0.0, 0.0

    for cmd, params in commands:
        if cmd == "M":
            cx, cy = params[0], params[1]
            points.append((cx, cy))
        elif cmd == "L":
            cx, cy = params[0], params[1]
            points.append((cx, cy))
        elif cmd == "C":
            pts = flatten_cubic(
                cx, cy,
                params[0], params[1],
                params[2], params[3],
                params[4], params[5],
                num_segments=segments_per_curve,
            )
            points.extend(pts)
            cx, cy = params[4], params[5]
        elif cmd == "A":
            pts = flatten_arc(
                params[0], params[1], params[2],
                params[3], params[4],
                num_segments=segments_per_curve,
            )
            points.extend(pts)
            if pts:
                cx, cy = pts[-1]
        # Z: close path (polygon is implicitly closed)

    return points


def _sutherland_hodgman_clip(
    polygon: List[Point],
    rect: Tuple[float, float, float, float],
) -> List[List[Point]]:
    """Clip a polygon against a rectangle using Sutherland-Hodgman.

    Returns a list of polygons (typically one, but degenerate cases
    may yield zero).
    """
    rmin_x, rmin_y, rmax_x, rmax_y = rect

    # Clip edges: each defined as (inside_test, intersect_fn)
    # Left edge: x >= rmin_x
    # Right edge: x <= rmax_x
    # Bottom edge: y >= rmin_y  (SVG y-axis: min_y is top)
    # Top edge: y <= rmax_y
    clip_edges = [
        (lambda p: p[0] >= rmin_x - _EPS,
         lambda p1, p2: _intersect_x(p1, p2, rmin_x)),
        (lambda p: p[0] <= rmax_x + _EPS,
         lambda p1, p2: _intersect_x(p1, p2, rmax_x)),
        (lambda p: p[1] >= rmin_y - _EPS,
         lambda p1, p2: _intersect_y(p1, p2, rmin_y)),
        (lambda p: p[1] <= rmax_y + _EPS,
         lambda p1, p2: _intersect_y(p1, p2, rmax_y)),
    ]

    output = list(polygon)

    for is_inside, intersect in clip_edges:
        if len(output) < 2:
            return []
        clipped: List[Point] = []
        n = len(output)
        for i in range(n):
            curr = output[i]
            prev = output[i - 1]
            curr_in = is_inside(curr)
            prev_in = is_inside(prev)

            if prev_in and curr_in:
                clipped.append(curr)
            elif prev_in and not curr_in:
                clipped.append(intersect(prev, curr))
            elif not prev_in and curr_in:
                clipped.append(intersect(prev, curr))
                clipped.append(curr)
            # both outside: skip

        output = clipped

    if len(output) < 3:
        return []

    # Remove consecutive duplicate points
    cleaned: List[Point] = [output[0]]
    for p in output[1:]:
        if abs(p[0] - cleaned[-1][0]) > 0.001 or abs(p[1] - cleaned[-1][1]) > 0.001:
            cleaned.append(p)
    # Check last vs first
    if len(cleaned) > 1 and abs(cleaned[-1][0] - cleaned[0][0]) < 0.001 and abs(cleaned[-1][1] - cleaned[0][1]) < 0.001:
        cleaned.pop()

    if len(cleaned) < 3:
        return []

    return [cleaned]


def _intersect_x(
    p1: Point, p2: Point, x: float,
) -> Point:
    """Find intersection of line p1-p2 with vertical line x=const."""
    dx = p2[0] - p1[0]
    if abs(dx) < 1e-12:
        return (x, p1[1])
    t = (x - p1[0]) / dx
    t = max(0.0, min(1.0, t))
    return (x, p1[1] + t * (p2[1] - p1[1]))


def _intersect_y(
    p1: Point, p2: Point, y: float,
) -> Point:
    """Find intersection of line p1-p2 with horizontal line y=const."""
    dy = p2[1] - p1[1]
    if abs(dy) < 1e-12:
        return (p1[0], y)
    t = (y - p1[1]) / dy
    t = max(0.0, min(1.0, t))
    return (p1[0] + t * (p2[0] - p1[0]), y)


def _polygon_to_commands(polygon: List[Point]) -> List[Command]:
    """Convert a clipped polygon back to M/L/Z command tuples."""
    if len(polygon) < 3:
        return []
    commands: List[Command] = [("M", [polygon[0][0], polygon[0][1]])]
    for p in polygon[1:]:
        commands.append(("L", [p[0], p[1]]))
    commands.append(("Z", []))
    return commands
