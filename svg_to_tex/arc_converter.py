"""
SVG arc endpoint-to-center conversion (SVG spec F.6.5) and
elliptical arc-to-cubic-bezier approximation.
"""

import math
from typing import List, Tuple


def endpoint_to_center(
    x1: float, y1: float,
    rx: float, ry: float,
    phi_deg: float,
    fa: float, fs: float,
    x2: float, y2: float,
) -> Tuple[float, float, float, float, float, float, float]:
    """Convert SVG arc endpoint parameterization to center parameterization.

    Implements SVG spec F.6.5.

    Args:
        x1, y1: Start point
        rx, ry: Radii
        phi_deg: X-axis rotation in degrees
        fa: Large arc flag (0 or 1)
        fs: Sweep flag (0 or 1)
        x2, y2: End point

    Returns:
        (cx, cy, rx, ry, theta1_deg, dtheta_deg, phi_deg)
        where theta1 is start angle and dtheta is sweep angle, both in degrees.
    """
    # F.6.5 step 1: handle degenerate cases
    if x1 == x2 and y1 == y2:
        return (x1, y1, 0, 0, 0, 0, 0)

    rx = abs(rx)
    ry = abs(ry)

    if rx == 0 or ry == 0:
        # Degenerate to line
        return (x1, y1, 0, 0, 0, 0, 0)

    phi = math.radians(phi_deg)
    cos_phi = math.cos(phi)
    sin_phi = math.sin(phi)

    # F.6.5.1: Compute (x1', y1')
    dx = (x1 - x2) / 2.0
    dy = (y1 - y2) / 2.0
    x1p = cos_phi * dx + sin_phi * dy
    y1p = -sin_phi * dx + cos_phi * dy

    # F.6.6.2: Ensure radii are large enough
    x1p_sq = x1p * x1p
    y1p_sq = y1p * y1p
    rx_sq = rx * rx
    ry_sq = ry * ry

    lam = x1p_sq / rx_sq + y1p_sq / ry_sq
    if lam > 1.0:
        lam_sqrt = math.sqrt(lam)
        rx *= lam_sqrt
        ry *= lam_sqrt
        rx_sq = rx * rx
        ry_sq = ry * ry

    # F.6.5.2: Compute (cx', cy')
    num = rx_sq * ry_sq - rx_sq * y1p_sq - ry_sq * x1p_sq
    den = rx_sq * y1p_sq + ry_sq * x1p_sq

    if den == 0:
        return (x1, y1, rx, ry, 0, 0, phi_deg)

    sq = max(0.0, num / den)
    sq = math.sqrt(sq)

    if fa == fs:
        sq = -sq

    cxp = sq * rx * y1p / ry
    cyp = -sq * ry * x1p / rx

    # F.6.5.3: Compute (cx, cy)
    cx = cos_phi * cxp - sin_phi * cyp + (x1 + x2) / 2.0
    cy = sin_phi * cxp + cos_phi * cyp + (y1 + y2) / 2.0

    # F.6.5.5/6: Compute theta1 and dtheta
    def angle(ux, uy, vx, vy):
        n = math.sqrt(ux * ux + uy * uy) * math.sqrt(vx * vx + vy * vy)
        if n == 0:
            return 0
        c = (ux * vx + uy * vy) / n
        c = max(-1.0, min(1.0, c))
        a = math.acos(c)
        if ux * vy - uy * vx < 0:
            a = -a
        return a

    theta1 = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dtheta = angle(
        (x1p - cxp) / rx, (y1p - cyp) / ry,
        (-x1p - cxp) / rx, (-y1p - cyp) / ry,
    )

    # Adjust dtheta per sweep flag
    if fs == 0 and dtheta > 0:
        dtheta -= 2 * math.pi
    elif fs == 1 and dtheta < 0:
        dtheta += 2 * math.pi

    return (cx, cy, rx, ry, math.degrees(theta1), math.degrees(dtheta), phi_deg)


def arc_to_beziers(
    cx: float, cy: float,
    rx: float, ry: float,
    theta1_deg: float,
    dtheta_deg: float,
    phi_deg: float,
) -> List[Tuple[str, List[float]]]:
    """Approximate an elliptical arc with cubic bezier curves.

    Splits into segments of max 90 degrees each.
    Returns list of ('C', [x1,y1,x2,y2,x,y]) commands.
    Error is ~0.027% for 90-degree segments.
    """
    if abs(dtheta_deg) < 1e-10:
        return []

    phi = math.radians(phi_deg)
    cos_phi = math.cos(phi)
    sin_phi = math.sin(phi)

    # Split into segments of max 90 degrees
    n_segs = max(1, int(math.ceil(abs(dtheta_deg) / 90.0)))
    d_theta = math.radians(dtheta_deg) / n_segs

    result = []
    theta = math.radians(theta1_deg)

    for _ in range(n_segs):
        t = math.tan(d_theta / 2.0)
        alpha = math.sin(d_theta) * (math.sqrt(4 + 3 * t * t) - 1) / 3.0

        cos_t1 = math.cos(theta)
        sin_t1 = math.sin(theta)
        cos_t2 = math.cos(theta + d_theta)
        sin_t2 = math.sin(theta + d_theta)

        # Endpoint 1 (on the ellipse)
        ex1 = rx * cos_t1
        ey1 = ry * sin_t1

        # Endpoint 2 (on the ellipse)
        ex2 = rx * cos_t2
        ey2 = ry * sin_t2

        # Derivative at t1
        dx1 = -rx * sin_t1
        dy1 = ry * cos_t1

        # Derivative at t2
        dx2 = -rx * sin_t2
        dy2 = ry * cos_t2

        # Control points (before rotation)
        cp1x = ex1 + alpha * dx1
        cp1y = ey1 + alpha * dy1
        cp2x = ex2 - alpha * dx2
        cp2y = ey2 - alpha * dy2

        # Apply rotation and translation
        def transform(px, py):
            x = cos_phi * px - sin_phi * py + cx
            y = sin_phi * px + cos_phi * py + cy
            return x, y

        x1, y1 = transform(cp1x, cp1y)
        x2, y2 = transform(cp2x, cp2y)
        x, y = transform(ex2, ey2)

        result.append(("C", [x1, y1, x2, y2, x, y]))
        theta += d_theta

    return result


def is_circular(rx: float, ry: float, phi_deg: float, tolerance: float = 0.001) -> bool:
    """Check if an elliptical arc is effectively circular (within 0.1%).

    Tighter tolerance (0.1% vs old 1%) ensures the radius averaging in
    center-param conversion stays well within CAD/3D-print tolerance.
    Truly elliptical arcs are converted to cubic Béziers instead.
    """
    return abs(rx - ry) / max(rx, ry, 1e-10) < tolerance


def arc_to_center_param(
    x1: float, y1: float,
    rx: float, ry: float,
    phi_deg: float,
    fa: float, fs: float,
    x2: float, y2: float,
) -> List[Tuple[str, List[float]]]:
    """Convert SVG arc to either center-param circular arc or bezier approximation.

    For circular arcs (rx ≈ ry): returns ('A', [cx, cy, r, startDeg, sweepDeg])
    For elliptical arcs: returns list of ('C', [...]) bezier commands.
    """
    cx, cy, rx_adj, ry_adj, theta1, dtheta, phi = endpoint_to_center(
        x1, y1, rx, ry, phi_deg, fa, fs, x2, y2
    )

    if rx_adj == 0 or ry_adj == 0:
        # Degenerate arc -> line
        return [("L", [x2, y2])]

    if is_circular(rx_adj, ry_adj, phi):
        # Circular arc: use native arc representation
        r = (rx_adj + ry_adj) / 2.0
        return [("A", [cx, cy, r, theta1, dtheta])]
    else:
        # Elliptical arc: approximate with cubic beziers
        return arc_to_beziers(cx, cy, rx_adj, ry_adj, theta1, dtheta, phi)
