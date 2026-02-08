"""
Parse SVG XML, extract viewBox, and walk element tree to produce path data.
"""

import xml.etree.ElementTree as ET
from typing import List, Tuple, Optional

from .shapes import shape_to_path_d
from .path_parser import parse_path
from .path_normalizer import normalize_commands
from .transform import parse_transform, multiply, identity, apply_to_path_commands
from .use_resolver import resolve_uses

# SVG namespace
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

# Elements that can contain paths
PATH_ELEMENTS = {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon"}
GROUP_ELEMENTS = {"g", "svg", "defs", "symbol", "a", "switch", "clipPath", "mask"}


def _strip_ns(tag: str) -> str:
    """Remove XML namespace from tag name."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _get_attrib(elem: ET.Element, name: str, default: str = None) -> Optional[str]:
    """Get attribute value, checking both with and without namespace."""
    val = elem.get(name)
    if val is not None:
        return val
    # Try xlink namespace for href
    if name == "href":
        val = elem.get(f"{{{XLINK_NS}}}href")
    return val if val is not None else default


def parse_viewbox(svg_root: ET.Element) -> Tuple[float, float, float, float]:
    """Extract viewBox from SVG root element.

    Returns (minX, minY, width, height).
    Falls back to width/height attributes if viewBox not specified.
    """
    vb = svg_root.get("viewBox")
    if vb:
        parts = vb.replace(",", " ").split()
        if len(parts) >= 4:
            return (float(parts[0]), float(parts[1]),
                    float(parts[2]), float(parts[3]))

    # Fallback to width/height
    w = svg_root.get("width", "100")
    h = svg_root.get("height", "100")
    # Strip units (px, etc.)
    w = "".join(c for c in w if c.isdigit() or c == "." or c == "-")
    h = "".join(c for c in h if c.isdigit() or c == "." or c == "-")
    return (0, 0, float(w or 100), float(h or 100))


def _is_visible(elem: ET.Element) -> bool:
    """Check if element is visible (not hidden via display/visibility)."""
    display = elem.get("display", "")
    if display.lower() == "none":
        return False
    visibility = elem.get("visibility", "")
    if visibility.lower() == "hidden":
        return False
    return True


def _get_fill_info(elem: ET.Element) -> Tuple[bool, str]:
    """Determine if element has a fill and what fill-rule it uses.

    Returns (has_fill, fill_rule).
    fill_rule is 'evenodd' or 'nonzero'.
    """
    fill = elem.get("fill", "")
    style = elem.get("style", "")

    # Parse inline style for fill
    fill_from_style = None
    fill_rule_from_style = None
    for prop in style.split(";"):
        prop = prop.strip()
        if prop.startswith("fill:"):
            fill_from_style = prop.split(":", 1)[1].strip()
        elif prop.startswith("fill-rule:"):
            fill_rule_from_style = prop.split(":", 1)[1].strip()

    # Determine fill value (style overrides attribute)
    effective_fill = fill_from_style if fill_from_style is not None else fill
    if not effective_fill:
        effective_fill = "black"  # SVG default

    has_fill = effective_fill.lower() != "none"

    # Determine fill-rule
    fill_rule = elem.get("fill-rule", "")
    if fill_rule_from_style:
        fill_rule = fill_rule_from_style
    if fill_rule not in ("evenodd", "nonzero"):
        fill_rule = "nonzero"  # SVG default

    return has_fill, fill_rule


def _get_stroke_info(elem: ET.Element) -> Tuple[bool, float]:
    """Determine if element has a visible stroke and its width.

    Returns (has_stroke, stroke_width).
    """
    stroke = elem.get("stroke", "")
    style = elem.get("style", "")
    stroke_width_attr = elem.get("stroke-width", "")

    stroke_from_style = None
    stroke_width_from_style = None
    for prop in style.split(";"):
        prop = prop.strip()
        if prop.startswith("stroke:"):
            stroke_from_style = prop.split(":", 1)[1].strip()
        elif prop.startswith("stroke-width:"):
            stroke_width_from_style = prop.split(":", 1)[1].strip()

    effective_stroke = stroke_from_style if stroke_from_style is not None else stroke
    if not effective_stroke:
        effective_stroke = "none"

    has_stroke = effective_stroke.lower() not in ("none", "")

    sw_str = stroke_width_from_style if stroke_width_from_style is not None else stroke_width_attr
    try:
        sw_str_clean = "".join(c for c in sw_str if c.isdigit() or c == "." or c == "-")
        stroke_width = float(sw_str_clean) if sw_str_clean else 1.0
    except (ValueError, TypeError):
        stroke_width = 1.0

    return has_stroke, stroke_width


def walk_elements(
    elem: ET.Element,
    parent_transform: List[float] = None,
    include_strokes: bool = False,
) -> List[dict]:
    """Recursively walk SVG element tree, extracting path data.

    Returns list of dicts:
        {
            'commands': [(cmd, params), ...],  # Normalized absolute commands
            'fill_rule': 'evenodd' | 'nonzero',
        }
    When include_strokes is True, stroke-only paths are also returned with
    additional 'source': 'stroke' and 'stroke_width' keys.
    """
    if parent_transform is None:
        parent_transform = identity()

    tag = _strip_ns(elem.tag)

    if not _is_visible(elem):
        return []

    # Skip <defs> and <symbol> — their children are only rendered via <use>
    if tag in ("defs", "symbol"):
        return []

    # Compose transform
    local_transform = parse_transform(elem.get("transform", ""))
    combined = multiply(parent_transform, local_transform)

    results = []

    if tag in PATH_ELEMENTS:
        # Get path d string
        if tag == "path":
            d = elem.get("d", "")
        else:
            d = shape_to_path_d(tag, elem.attrib)

        if d:
            has_fill, fill_rule = _get_fill_info(elem)
            raw_cmds = parse_path(d)
            norm_cmds = normalize_commands(raw_cmds)

            if norm_cmds:
                transformed = apply_to_path_commands(combined, norm_cmds)

                if has_fill:
                    results.append({
                        "commands": transformed,
                        "fill_rule": fill_rule,
                    })
                elif include_strokes:
                    has_stroke, stroke_width = _get_stroke_info(elem)
                    if has_stroke:
                        results.append({
                            "commands": transformed,
                            "fill_rule": "nonzero",
                            "source": "stroke",
                            "stroke_width": stroke_width,
                        })

    # Recurse into children (for groups, svg, etc.)
    for child in elem:
        results.extend(walk_elements(child, combined, include_strokes))

    return results


def parse_svg(
    svg_content: str,
    include_strokes: bool = False,
) -> Tuple[Tuple[float, float, float, float], List[dict]]:
    """Parse SVG content string and extract path data.

    Args:
        svg_content: SVG file content as string.
        include_strokes: If True, also extract stroke-only paths.

    Returns:
        (viewbox, paths) where:
        - viewbox is (minX, minY, width, height)
        - paths is list of {'commands': [...], 'fill_rule': str}
    """
    root = ET.fromstring(svg_content)

    # Resolve <use> elements first
    resolve_uses(root)

    viewbox = parse_viewbox(root)
    paths = walk_elements(root, include_strokes=include_strokes)

    return viewbox, paths
