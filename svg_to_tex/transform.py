"""
Parse, compose, and apply 2D affine transforms.

Supports: translate, rotate, scale, skewX, skewY, matrix.
Transforms are represented as 3x3 matrices stored as [a, b, c, d, e, f]
corresponding to the matrix:
    | a c e |
    | b d f |
    | 0 0 1 |
"""

import math
import re
from typing import List, Optional, Tuple


def identity() -> List[float]:
    """Return identity transform [a, b, c, d, e, f]."""
    return [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def multiply(m1: List[float], m2: List[float]) -> List[float]:
    """Multiply two affine transforms: m1 * m2.

    Each is [a, b, c, d, e, f] representing:
        | a c e |
        | b d f |
        | 0 0 1 |
    """
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return [
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    ]


def apply_to_point(m: List[float], x: float, y: float) -> Tuple[float, float]:
    """Apply transform to a point."""
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def make_translate(tx: float, ty: float = 0.0) -> List[float]:
    return [1.0, 0.0, 0.0, 1.0, tx, ty]


def make_scale(sx: float, sy: Optional[float] = None) -> List[float]:
    if sy is None:
        sy = sx
    return [sx, 0.0, 0.0, sy, 0.0, 0.0]


def make_rotate(angle_deg: float, cx: float = 0.0, cy: float = 0.0) -> List[float]:
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    if cx == 0.0 and cy == 0.0:
        return [cos_a, sin_a, -sin_a, cos_a, 0.0, 0.0]
    # rotate around (cx, cy): translate to origin, rotate, translate back
    m = make_translate(cx, cy)
    m = multiply(m, [cos_a, sin_a, -sin_a, cos_a, 0.0, 0.0])
    m = multiply(m, make_translate(-cx, -cy))
    return m


def make_skew_x(angle_deg: float) -> List[float]:
    return [1.0, 0.0, math.tan(math.radians(angle_deg)), 1.0, 0.0, 0.0]


def make_skew_y(angle_deg: float) -> List[float]:
    return [1.0, math.tan(math.radians(angle_deg)), 0.0, 1.0, 0.0, 0.0]


def parse_transform(transform_str: str) -> List[float]:
    """Parse an SVG transform attribute string into a combined affine matrix.

    Supports: translate, scale, rotate, skewX, skewY, matrix.
    Multiple transforms are composed left-to-right (SVG spec).
    """
    if not transform_str:
        return identity()

    result = identity()

    # Match function calls like "translate(10, 20)" or "rotate(45)"
    pattern = r"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)"
    for match in re.finditer(pattern, transform_str):
        func = match.group(1)
        args_str = match.group(2)
        args = [float(x) for x in re.findall(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?", args_str)]

        if func == "matrix" and len(args) == 6:
            m = args
        elif func == "translate":
            tx = args[0] if len(args) >= 1 else 0.0
            ty = args[1] if len(args) >= 2 else 0.0
            m = make_translate(tx, ty)
        elif func == "scale":
            sx = args[0] if len(args) >= 1 else 1.0
            sy = args[1] if len(args) >= 2 else sx
            m = make_scale(sx, sy)
        elif func == "rotate":
            angle = args[0] if len(args) >= 1 else 0.0
            cx = args[1] if len(args) >= 3 else 0.0
            cy = args[2] if len(args) >= 3 else 0.0
            m = make_rotate(angle, cx, cy)
        elif func == "skewX" and len(args) >= 1:
            m = make_skew_x(args[0])
        elif func == "skewY" and len(args) >= 1:
            m = make_skew_y(args[0])
        else:
            continue

        result = multiply(result, m)

    return result


def apply_to_path_commands(
    matrix: List[float], commands: list
) -> list:
    """Apply affine transform to a list of (command, params) tuples.

    Handles M, L, C, A, Z commands (absolute coords only).
    For A commands, transforms center point and adjusts radius (circular arcs only).
    """
    if matrix == identity():
        return commands

    result = []
    for cmd, params in commands:
        if cmd in ("M", "L"):
            x, y = apply_to_point(matrix, params[0], params[1])
            result.append((cmd, [x, y]))
        elif cmd == "C":
            x1, y1 = apply_to_point(matrix, params[0], params[1])
            x2, y2 = apply_to_point(matrix, params[2], params[3])
            x, y = apply_to_point(matrix, params[4], params[5])
            result.append((cmd, [x1, y1, x2, y2, x, y]))
        elif cmd == "A":
            # A cx, cy, r, startDeg, sweepDeg (our internal arc format)
            cx, cy = apply_to_point(matrix, params[0], params[1])
            r = params[2]
            # Scale radius by the average scale factor
            a, b, c, d = matrix[0], matrix[1], matrix[2], matrix[3]
            sx = math.sqrt(a * a + b * b)
            sy = math.sqrt(c * c + d * d)
            avg_scale = (sx + sy) / 2.0
            r_scaled = r * avg_scale

            # Adjust angles for rotation/reflection
            # Compute how the transform affects the angle
            rotation_angle = math.atan2(b, a)
            start_deg = params[3]
            sweep_deg = params[4]

            # Adjust start angle by the rotation
            new_start = start_deg + math.degrees(rotation_angle)

            # If transform has a reflection (negative determinant), flip sweep
            det = a * d - b * c
            if det < 0:
                sweep_deg = -sweep_deg

            result.append((cmd, [cx, cy, r_scaled, new_start, sweep_deg]))
        elif cmd in ("Z", "z"):
            result.append((cmd, []))
        else:
            # Pass through unknown commands unchanged
            result.append((cmd, params))

    return result
