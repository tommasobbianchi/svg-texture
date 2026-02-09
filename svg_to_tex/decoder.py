"""
Decode SVGTEX format back into Python data structures.

Mirrors the FeatureScript parseSvgTex() function to validate
the format contract between encoder and parser.

SVGTEX format:
    V<minX>,<minY>,<width>,<height>|<fillRule><commands>|...

Fill rule prefix: E (evenodd) or N (nonzero)
Commands: M x,y | L x,y | C x1,y1,x2,y2,x,y | A cx,cy,r,startDeg,sweepDeg | Z
"""

import re
from typing import List, Tuple, Optional


class SvgtexDecodeError(ValueError):
    """Raised when SVGTEX text cannot be parsed."""
    pass


def decode_viewbox(segment: str) -> Tuple[float, float, float, float]:
    """Parse viewbox segment 'V<minX>,<minY>,<w>,<h>' into a 4-tuple."""
    if not segment.startswith("V"):
        raise SvgtexDecodeError(f"Viewbox segment must start with 'V', got: {segment!r}")
    parts = segment[1:].split(",")
    if len(parts) != 4:
        raise SvgtexDecodeError(f"Viewbox must have 4 comma-separated values, got {len(parts)}: {segment!r}")
    try:
        return tuple(float(p) for p in parts)
    except ValueError as e:
        raise SvgtexDecodeError(f"Invalid viewbox number: {e}") from e


def decode_commands(cmd_str: str) -> List[Tuple[str, List[float]]]:
    """Parse a command string like 'M0,0 L10,20 C1,2,3,4,5,6 Z' into command tuples."""
    commands = []
    tokens = cmd_str.split()
    for token in tokens:
        if not token:
            continue
        cmd_letter = token[0]
        if cmd_letter == "Z":
            commands.append(("Z", []))
        elif cmd_letter in ("M", "L", "C", "A"):
            params_str = token[1:]
            try:
                params = [float(p) for p in params_str.split(",")]
            except ValueError as e:
                raise SvgtexDecodeError(f"Invalid parameter in {cmd_letter} command: {e}") from e

            expected = {"M": 2, "L": 2, "C": 6, "A": 5}
            if len(params) != expected[cmd_letter]:
                raise SvgtexDecodeError(
                    f"{cmd_letter} command expects {expected[cmd_letter]} params, got {len(params)}: {token!r}"
                )
            commands.append((cmd_letter, params))
        else:
            raise SvgtexDecodeError(f"Unknown command letter: {cmd_letter!r} in token {token!r}")
    return commands


def decode_path(segment: str) -> dict:
    """Parse a path segment '<fillRule><commands>' into a dict.

    Returns:
        {'commands': [...], 'fill_rule': 'evenodd'|'nonzero'}
    """
    if not segment:
        raise SvgtexDecodeError("Empty path segment")

    prefix = segment[0]
    if prefix == "E":
        fill_rule = "evenodd"
    elif prefix == "N":
        fill_rule = "nonzero"
    else:
        raise SvgtexDecodeError(f"Path must start with 'E' or 'N' fill rule, got: {prefix!r}")

    cmd_str = segment[1:]
    commands = decode_commands(cmd_str)

    return {"commands": commands, "fill_rule": fill_rule}


def decode_svgtex(text: str) -> Tuple[Tuple[float, float, float, float], List[dict]]:
    """Decode a complete SVGTEX string.

    Args:
        text: Complete SVGTEX string (pipe-delimited).

    Returns:
        (viewbox, paths) where viewbox is (minX, minY, w, h) and
        paths is a list of {'commands': [...], 'fill_rule': str}.

    Raises:
        SvgtexDecodeError: If the format is invalid.
    """
    if not text or not text.strip():
        raise SvgtexDecodeError("Empty SVGTEX input")

    text = text.strip()
    segments = text.split("|")

    if len(segments) < 1:
        raise SvgtexDecodeError("SVGTEX must have at least a viewbox segment")

    viewbox = decode_viewbox(segments[0])

    paths = []
    for seg in segments[1:]:
        if seg:  # skip empty segments
            paths.append(decode_path(seg))

    return viewbox, paths


def estimate_entity_count(paths: List[dict]) -> int:
    """Count drawing entities (L, C, A commands) in decoded paths.

    This mirrors region_analyzer.estimate_entity_count for a single tile.
    """
    count = 0
    for path in paths:
        for cmd, _ in path.get("commands", []):
            if cmd in ("L", "C", "A"):
                count += 1
    return count
