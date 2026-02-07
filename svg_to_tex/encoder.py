"""
Emit SVGTEX format string with precision control.

SVGTEX format:
    V<minX>,<minY>,<width>,<height>       # Header: viewBox dimensions
    <fillRule><commands>                    # One line per path

Fill rule prefix: E (evenodd) or N (nonzero)
Commands: M x,y | L x,y | C x1,y1,x2,y2,x,y | A cx,cy,r,startDeg,sweepDeg | Z
"""

from typing import List, Tuple


def _fmt(val: float, precision: int = 2) -> str:
    """Format a number with given precision, stripping trailing zeros."""
    s = f"{val:.{precision}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    # Handle negative zero
    if s == "-0":
        s = "0"
    return s


def encode_viewbox(
    min_x: float, min_y: float,
    width: float, height: float,
    precision: int = 2,
) -> str:
    """Encode viewBox as SVGTEX header line."""
    return f"V{_fmt(min_x, precision)},{_fmt(min_y, precision)},{_fmt(width, precision)},{_fmt(height, precision)}"


def encode_commands(
    commands: List[Tuple[str, List[float]]],
    precision: int = 2,
) -> str:
    """Encode a list of path commands as SVGTEX command string."""
    parts = []
    for cmd, params in commands:
        if cmd == "M":
            parts.append(f"M{_fmt(params[0], precision)},{_fmt(params[1], precision)}")
        elif cmd == "L":
            parts.append(f"L{_fmt(params[0], precision)},{_fmt(params[1], precision)}")
        elif cmd == "C":
            parts.append(
                f"C{_fmt(params[0], precision)},{_fmt(params[1], precision)},"
                f"{_fmt(params[2], precision)},{_fmt(params[3], precision)},"
                f"{_fmt(params[4], precision)},{_fmt(params[5], precision)}"
            )
        elif cmd == "A":
            parts.append(
                f"A{_fmt(params[0], precision)},{_fmt(params[1], precision)},"
                f"{_fmt(params[2], precision)},{_fmt(params[3], precision)},"
                f"{_fmt(params[4], precision)}"
            )
        elif cmd == "Z":
            parts.append("Z")
    return " ".join(parts)


def encode_path(
    commands: List[Tuple[str, List[float]]],
    fill_rule: str = "nonzero",
    precision: int = 2,
) -> str:
    """Encode a single path as a SVGTEX line.

    Prefix: E (evenodd) or N (nonzero)
    """
    prefix = "E" if fill_rule == "evenodd" else "N"
    cmd_str = encode_commands(commands, precision)
    return f"{prefix}{cmd_str}"


def encode_svgtex(
    viewbox: Tuple[float, float, float, float],
    paths: List[dict],
    precision: int = 2,
) -> str:
    """Encode complete SVGTEX string.

    Args:
        viewbox: (minX, minY, width, height)
        paths: List of {'commands': [...], 'fill_rule': str}
        precision: Number of decimal places

    Returns:
        Complete SVGTEX string ready for pasting into FeatureScript.
    """
    lines = []

    # Header
    lines.append(encode_viewbox(*viewbox, precision))

    # Path lines
    for path in paths:
        line = encode_path(
            path["commands"],
            path.get("fill_rule", "nonzero"),
            precision,
        )
        lines.append(line)

    result = "\n".join(lines)

    # Add warnings as comments
    warnings = []
    if len(result) > 8000:
        warnings.append(f"# WARNING: Output is {len(result)} chars. Onshape string param limit is ~10000.")
    if len(result) > 10000:
        warnings.append("# WARNING: Output exceeds recommended limit. Consider simplifying the SVG.")

    total_entities = sum(
        sum(1 for cmd, _ in p["commands"] if cmd in ("L", "C", "A"))
        for p in paths
    )
    if total_entities > 500:
        warnings.append(f"# WARNING: {total_entities} sketch entities. Tiling may exceed Onshape limits.")

    if warnings:
        result = "\n".join(warnings) + "\n" + result

    return result
