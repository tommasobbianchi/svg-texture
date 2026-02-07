"""
Convert SVG basic shape elements (rect, circle, ellipse, line, polyline, polygon)
to path `d` attribute strings.
"""

import math
from typing import Optional


def rect_to_path(
    x: float = 0, y: float = 0,
    width: float = 0, height: float = 0,
    rx: Optional[float] = None, ry: Optional[float] = None,
) -> str:
    """Convert rect element to path d string."""
    if width <= 0 or height <= 0:
        return ""

    # Handle rounded corners per SVG spec
    if rx is None and ry is None:
        rx = ry = 0
    elif rx is not None and ry is None:
        ry = rx
    elif ry is not None and rx is None:
        rx = ry

    rx = min(rx, width / 2)
    ry = min(ry, height / 2)

    if rx <= 0 or ry <= 0:
        # Simple rectangle
        return (
            f"M {x},{y} "
            f"L {x + width},{y} "
            f"L {x + width},{y + height} "
            f"L {x},{y + height} "
            f"Z"
        )

    # Rounded rectangle
    return (
        f"M {x + rx},{y} "
        f"L {x + width - rx},{y} "
        f"A {rx},{ry} 0 0 1 {x + width},{y + ry} "
        f"L {x + width},{y + height - ry} "
        f"A {rx},{ry} 0 0 1 {x + width - rx},{y + height} "
        f"L {x + rx},{y + height} "
        f"A {rx},{ry} 0 0 1 {x},{y + height - ry} "
        f"L {x},{y + ry} "
        f"A {rx},{ry} 0 0 1 {x + rx},{y} "
        f"Z"
    )


def circle_to_path(cx: float = 0, cy: float = 0, r: float = 0) -> str:
    """Convert circle element to path d string."""
    if r <= 0:
        return ""
    # Two semicircular arcs
    return (
        f"M {cx - r},{cy} "
        f"A {r},{r} 0 1 1 {cx + r},{cy} "
        f"A {r},{r} 0 1 1 {cx - r},{cy} "
        f"Z"
    )


def ellipse_to_path(
    cx: float = 0, cy: float = 0,
    rx: float = 0, ry: float = 0,
) -> str:
    """Convert ellipse element to path d string."""
    if rx <= 0 or ry <= 0:
        return ""
    return (
        f"M {cx - rx},{cy} "
        f"A {rx},{ry} 0 1 1 {cx + rx},{cy} "
        f"A {rx},{ry} 0 1 1 {cx - rx},{cy} "
        f"Z"
    )


def line_to_path(
    x1: float = 0, y1: float = 0,
    x2: float = 0, y2: float = 0,
) -> str:
    """Convert line element to path d string.

    Note: Lines have no fill area, so this will typically be filtered out.
    Included for completeness.
    """
    return f"M {x1},{y1} L {x2},{y2}"


def polyline_to_path(points_str: str) -> str:
    """Convert polyline points attribute to path d string."""
    coords = _parse_points(points_str)
    if len(coords) < 2:
        return ""
    parts = [f"M {coords[0][0]},{coords[0][1]}"]
    for x, y in coords[1:]:
        parts.append(f"L {x},{y}")
    return " ".join(parts)


def polygon_to_path(points_str: str) -> str:
    """Convert polygon points attribute to path d string."""
    d = polyline_to_path(points_str)
    if d:
        d += " Z"
    return d


def _parse_points(points_str: str) -> list:
    """Parse an SVG points attribute into list of (x, y) tuples."""
    import re
    nums = [float(n) for n in re.findall(
        r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?", points_str
    )]
    return [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]


def shape_to_path_d(tag: str, attribs: dict) -> str:
    """Convert any supported SVG shape element to a path d string.

    Args:
        tag: Element tag name (without namespace), e.g. 'rect', 'circle'
        attribs: Element attributes dict

    Returns:
        Path d string, or empty string if not a supported shape.
    """
    def g(key, default=0.0):
        val = attribs.get(key)
        if val is None:
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    if tag == "rect":
        rx_val = attribs.get("rx")
        ry_val = attribs.get("ry")
        return rect_to_path(
            g("x"), g("y"), g("width"), g("height"),
            float(rx_val) if rx_val is not None else None,
            float(ry_val) if ry_val is not None else None,
        )
    elif tag == "circle":
        return circle_to_path(g("cx"), g("cy"), g("r"))
    elif tag == "ellipse":
        return ellipse_to_path(g("cx"), g("cy"), g("rx"), g("ry"))
    elif tag == "line":
        return line_to_path(g("x1"), g("y1"), g("x2"), g("y2"))
    elif tag == "polyline":
        return polyline_to_path(attribs.get("points", ""))
    elif tag == "polygon":
        return polygon_to_path(attribs.get("points", ""))
    else:
        return ""
