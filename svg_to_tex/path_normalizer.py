"""
Normalize SVG path commands to absolute M/L/C/A/Z only.

Conversions:
- H, h -> L (horizontal line to absolute line-to)
- V, v -> L (vertical line to absolute line-to)
- S, s -> C (smooth cubic to full cubic)
- Q, q -> C (quadratic to cubic via degree elevation)
- T, t -> C (smooth quadratic to cubic via degree elevation)
- All relative commands (lowercase) -> absolute (uppercase)
- SVG arc (A/a) -> center-param circular arc or cubic bezier approximation
"""

from typing import List, Tuple
from .arc_converter import arc_to_center_param


def normalize_commands(
    commands: List[Tuple[str, List[float]]]
) -> List[Tuple[str, List[float]]]:
    """Normalize parsed path commands to absolute M/L/C/A/Z only.

    Args:
        commands: List of (command_letter, params) from path_parser.

    Returns:
        List of (command_letter, params) using only M, L, C, A, Z.
    """
    result = []
    cur_x, cur_y = 0.0, 0.0       # Current point
    start_x, start_y = 0.0, 0.0   # Start of current subpath
    prev_cmd = None
    prev_cp_x, prev_cp_y = 0.0, 0.0  # Previous control point for S/T

    for cmd, params in commands:
        is_relative = cmd.islower()
        CMD = cmd.upper()

        if CMD == "M":
            if is_relative:
                x, y = cur_x + params[0], cur_y + params[1]
            else:
                x, y = params[0], params[1]
            result.append(("M", [x, y]))
            cur_x, cur_y = x, y
            start_x, start_y = x, y
            prev_cmd = "M"

        elif CMD == "L":
            if is_relative:
                x, y = cur_x + params[0], cur_y + params[1]
            else:
                x, y = params[0], params[1]
            result.append(("L", [x, y]))
            cur_x, cur_y = x, y
            prev_cmd = "L"

        elif CMD == "H":
            if is_relative:
                x = cur_x + params[0]
            else:
                x = params[0]
            result.append(("L", [x, cur_y]))
            cur_x = x
            prev_cmd = "H"

        elif CMD == "V":
            if is_relative:
                y = cur_y + params[0]
            else:
                y = params[0]
            result.append(("L", [cur_x, y]))
            cur_y = y
            prev_cmd = "V"

        elif CMD == "C":
            if is_relative:
                x1 = cur_x + params[0]
                y1 = cur_y + params[1]
                x2 = cur_x + params[2]
                y2 = cur_y + params[3]
                x = cur_x + params[4]
                y = cur_y + params[5]
            else:
                x1, y1 = params[0], params[1]
                x2, y2 = params[2], params[3]
                x, y = params[4], params[5]
            result.append(("C", [x1, y1, x2, y2, x, y]))
            prev_cp_x, prev_cp_y = x2, y2
            cur_x, cur_y = x, y
            prev_cmd = "C"

        elif CMD == "S":
            # Smooth cubic: reflect previous control point
            if prev_cmd in ("C", "S"):
                x1 = 2 * cur_x - prev_cp_x
                y1 = 2 * cur_y - prev_cp_y
            else:
                x1, y1 = cur_x, cur_y

            if is_relative:
                x2 = cur_x + params[0]
                y2 = cur_y + params[1]
                x = cur_x + params[2]
                y = cur_y + params[3]
            else:
                x2, y2 = params[0], params[1]
                x, y = params[2], params[3]
            result.append(("C", [x1, y1, x2, y2, x, y]))
            prev_cp_x, prev_cp_y = x2, y2
            cur_x, cur_y = x, y
            prev_cmd = "S"

        elif CMD == "Q":
            # Quadratic to cubic via degree elevation
            if is_relative:
                qx = cur_x + params[0]
                qy = cur_y + params[1]
                x = cur_x + params[2]
                y = cur_y + params[3]
            else:
                qx, qy = params[0], params[1]
                x, y = params[2], params[3]

            # Degree elevation: C1 = P0 + 2/3*(Q1-P0), C2 = P2 + 2/3*(Q1-P2)
            c1x = cur_x + 2.0 / 3.0 * (qx - cur_x)
            c1y = cur_y + 2.0 / 3.0 * (qy - cur_y)
            c2x = x + 2.0 / 3.0 * (qx - x)
            c2y = y + 2.0 / 3.0 * (qy - y)
            result.append(("C", [c1x, c1y, c2x, c2y, x, y]))
            prev_cp_x, prev_cp_y = qx, qy
            cur_x, cur_y = x, y
            prev_cmd = "Q"

        elif CMD == "T":
            # Smooth quadratic: reflect previous quadratic control point
            if prev_cmd in ("Q", "T"):
                qx = 2 * cur_x - prev_cp_x
                qy = 2 * cur_y - prev_cp_y
            else:
                qx, qy = cur_x, cur_y

            if is_relative:
                x = cur_x + params[0]
                y = cur_y + params[1]
            else:
                x, y = params[0], params[1]

            c1x = cur_x + 2.0 / 3.0 * (qx - cur_x)
            c1y = cur_y + 2.0 / 3.0 * (qy - cur_y)
            c2x = x + 2.0 / 3.0 * (qx - x)
            c2y = y + 2.0 / 3.0 * (qy - y)
            result.append(("C", [c1x, c1y, c2x, c2y, x, y]))
            prev_cp_x, prev_cp_y = qx, qy
            cur_x, cur_y = x, y
            prev_cmd = "T"

        elif CMD == "A":
            if is_relative:
                rx, ry = params[0], params[1]
                phi = params[2]
                fa, fs = params[3], params[4]
                x = cur_x + params[5]
                y = cur_y + params[6]
            else:
                rx, ry = params[0], params[1]
                phi = params[2]
                fa, fs = params[3], params[4]
                x, y = params[5], params[6]

            arc_cmds = arc_to_center_param(
                cur_x, cur_y, rx, ry, phi, fa, fs, x, y
            )
            result.extend(arc_cmds)
            cur_x, cur_y = x, y
            prev_cmd = "A"

        elif CMD == "Z":
            result.append(("Z", []))
            cur_x, cur_y = start_x, start_y
            prev_cmd = "Z"

        # Reset prev control point for commands that don't set it
        if CMD not in ("C", "S", "Q", "T"):
            prev_cp_x, prev_cp_y = cur_x, cur_y

    return result
