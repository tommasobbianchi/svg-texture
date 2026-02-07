"""
Filter to filled paths only, extract fill-rule, auto-close unclosed subpaths.
"""

from typing import List, Tuple


def auto_close_subpaths(
    commands: List[Tuple[str, List[float]]]
) -> List[Tuple[str, List[float]]]:
    """Ensure all subpaths are closed with Z command.

    For filled regions, unclosed subpaths are implicitly closed by the renderer.
    We make this explicit for FeatureScript which needs closed sketches.
    """
    if not commands:
        return commands

    result = []
    subpath_start = None
    cur_x, cur_y = 0.0, 0.0

    for cmd, params in commands:
        if cmd == "M":
            # Close previous subpath if it wasn't closed
            if subpath_start is not None:
                if (abs(cur_x - subpath_start[0]) > 1e-6 or
                        abs(cur_y - subpath_start[1]) > 1e-6):
                    result.append(("Z", []))
            subpath_start = (params[0], params[1])
            cur_x, cur_y = params[0], params[1]
            result.append((cmd, params))

        elif cmd == "Z":
            result.append((cmd, params))
            if subpath_start is not None:
                cur_x, cur_y = subpath_start
            subpath_start = None

        elif cmd == "L":
            cur_x, cur_y = params[0], params[1]
            result.append((cmd, params))

        elif cmd == "C":
            cur_x, cur_y = params[4], params[5]
            result.append((cmd, params))

        elif cmd == "A":
            # A cx, cy, r, startDeg, sweepDeg
            # Current point moves to arc endpoint
            import math
            cx, cy, r = params[0], params[1], params[2]
            start_deg, sweep_deg = params[3], params[4]
            end_deg = start_deg + sweep_deg
            cur_x = cx + r * math.cos(math.radians(end_deg))
            cur_y = cy + r * math.sin(math.radians(end_deg))
            result.append((cmd, params))

        else:
            result.append((cmd, params))

    # Close final subpath if needed
    if subpath_start is not None:
        if (abs(cur_x - subpath_start[0]) > 1e-6 or
                abs(cur_y - subpath_start[1]) > 1e-6):
            result.append(("Z", []))

    return result


def filter_filled_paths(paths: List[dict]) -> List[dict]:
    """Filter path list to only filled paths and auto-close subpaths.

    Args:
        paths: List of {'commands': [...], 'fill_rule': str}

    Returns:
        Filtered and processed list.
    """
    result = []
    for path in paths:
        commands = path.get("commands", [])
        if not commands:
            continue

        # Auto-close subpaths for filled regions
        closed = auto_close_subpaths(commands)
        if closed:
            result.append({
                "commands": closed,
                "fill_rule": path.get("fill_rule", "nonzero"),
            })

    return result


def estimate_entity_count(paths: List[dict], tiles_x: int = 1, tiles_y: int = 1) -> int:
    """Estimate the number of sketch entities for given paths and tiling.

    Useful for warning users about entity count limits.
    """
    count = 0
    for path in paths:
        for cmd, _ in path.get("commands", []):
            if cmd in ("L", "C", "A"):
                count += 1
    return count * tiles_x * tiles_y
