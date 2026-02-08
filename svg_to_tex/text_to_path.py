"""
Convert SVG <text> elements to <path> elements using fontTools.

Pre-processing step that modifies SVG XML tree in-place, replacing <text>
with <g><path/></g> before the SVG parser processes path elements.
"""

import os
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    from fontTools.ttLib import TTFont
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    HAS_FONTTOOLS = True
except ImportError:
    HAS_FONTTOOLS = False

NS = "http://www.w3.org/2000/svg"

# Common system font search paths
FONT_SEARCH_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
    # macOS
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    # Windows
    "C:/Windows/Fonts/arial.ttf",
]


def find_system_font(font_family=None):
    """Find a system font file. Returns path string or None."""
    if font_family:
        # Try to match font family name in common locations
        font_dirs = [
            "/usr/share/fonts",
            "/usr/local/share/fonts",
            str(Path.home() / ".fonts"),
            str(Path.home() / ".local/share/fonts"),
        ]
        name_lower = font_family.lower().replace(" ", "")
        for font_dir in font_dirs:
            if not os.path.isdir(font_dir):
                continue
            for root, _, files in os.walk(font_dir):
                for f in files:
                    if f.lower().endswith(('.ttf', '.otf')):
                        if name_lower in f.lower().replace(" ", ""):
                            return os.path.join(root, f)

    # Fall back to known system fonts
    for path in FONT_SEARCH_PATHS:
        if os.path.exists(path):
            return path
    return None


def _get_glyph_path_d(glyph_set, cmap, char, units_per_em, font_size, cursor_x, baseline_y):
    """Get SVG path d string for a single character.

    Returns (path_d, advance_width) or (None, advance_width) if glyph has no outline.
    """
    code = ord(char)
    glyph_name = cmap.get(code)
    if not glyph_name:
        # Try .notdef
        glyph_name = ".notdef"

    try:
        glyph = glyph_set[glyph_name]
    except KeyError:
        return None, font_size * 0.5  # fallback advance

    # Get advance width
    advance = glyph.width if hasattr(glyph, 'width') else 0
    advance_scaled = advance * font_size / units_per_em

    # Draw glyph to SVG path
    pen = SVGPathPen(glyph_set)
    scale = font_size / units_per_em
    # Transform: scale and flip Y (font Y goes up, SVG Y goes down)
    # Then translate to cursor position
    transform = (scale, 0, 0, -scale, cursor_x, baseline_y)
    t_pen = TransformPen(pen, transform)

    try:
        glyph.draw(t_pen)
    except Exception:
        return None, advance_scaled

    path_d = pen.getCommands()
    if not path_d:
        return None, advance_scaled

    return path_d, advance_scaled


def _get_text_content(elem):
    """Extract text content from a <text> or <tspan> element, including tail text."""
    parts = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        # Recursively get child text (tspan etc.)
        parts.extend(_get_text_content(child))
        if child.tail:
            parts.append(child.tail)
    return parts


def _get_attr(elem, name, default=None, inherited=None):
    """Get attribute from element, with style parsing and inheritance."""
    # Check inline style first
    style = elem.get("style", "")
    if style:
        for part in style.split(";"):
            part = part.strip()
            if ":" in part:
                k, v = part.split(":", 1)
                if k.strip() == name:
                    return v.strip()
    # Check direct attribute
    val = elem.get(name)
    if val is not None:
        return val
    # Check namespace-prefixed
    val = elem.get(f"{{{NS}}}{name}")
    if val is not None:
        return val
    # Inherited value
    if inherited is not None:
        return inherited
    return default


def _parse_font_size(val):
    """Parse font-size value to number (stripping units)."""
    if val is None:
        return 16.0
    val = str(val).strip()
    # Strip common units
    for suffix in ("px", "pt", "em", "rem", "%"):
        if val.endswith(suffix):
            val = val[:-len(suffix)]
            break
    try:
        return float(val)
    except ValueError:
        return 16.0


def convert_text_to_paths(root, font_path=None):
    """Convert all <text> elements in SVG tree to <path> elements.

    Modifies the tree in-place. Returns number of text elements converted.
    """
    if not HAS_FONTTOOLS:
        return 0

    # Find font
    if font_path is None:
        font_path = find_system_font()
    if font_path is None or not os.path.exists(font_path):
        return 0

    # Load font
    try:
        font = TTFont(font_path)
    except Exception:
        return 0

    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    if not cmap:
        font.close()
        return 0

    units_per_em = font['head'].unitsPerEm
    converted = 0

    # Find all <text> elements (with and without namespace)
    text_elements = []
    _find_text_elements(root, text_elements)

    for elem, parent in text_elements:
        group = _convert_text_element(elem, glyph_set, cmap, units_per_em)
        if group is not None:
            # Replace <text> with <g> in parent
            idx = list(parent).index(elem)
            parent.remove(elem)
            parent.insert(idx, group)
            converted += 1

    font.close()
    return converted


def _find_text_elements(elem, result, parent=None):
    """Recursively find all <text> elements and their parents."""
    for child in list(elem):
        tag = child.tag
        if isinstance(tag, str):
            local = tag.split("}")[-1] if "}" in tag else tag
            if local == "text":
                result.append((child, elem))
            else:
                _find_text_elements(child, result, elem)
        else:
            _find_text_elements(child, result, elem)


def _convert_text_element(text_elem, glyph_set, cmap, units_per_em):
    """Convert a single <text> element to a <g> of <path> elements."""
    # Get text position and style
    x = float(_get_attr(text_elem, "x", "0"))
    y = float(_get_attr(text_elem, "y", "0"))
    font_size = _parse_font_size(_get_attr(text_elem, "font-size", "16"))
    text_anchor = _get_attr(text_elem, "text-anchor", "start")
    fill = _get_attr(text_elem, "fill", "black")
    transform = text_elem.get("transform", "")

    # Collect all text segments with their positions
    segments = []
    _collect_text_segments(text_elem, x, y, font_size, text_anchor, fill, segments)

    if not segments:
        return None

    # Create group element
    ns_prefix = f"{{{NS}}}" if "}" in text_elem.tag else ""
    group = ET.Element(f"{ns_prefix}g")
    if transform:
        group.set("transform", transform)

    for seg in segments:
        paths = _render_text_segment(
            seg["text"], seg["x"], seg["y"], seg["fontSize"],
            seg["textAnchor"], seg["fill"],
            glyph_set, cmap, units_per_em
        )
        for path_d in paths:
            path_elem = ET.SubElement(group, f"{ns_prefix}path")
            path_elem.set("d", path_d)
            path_elem.set("fill", seg["fill"])

    return group if len(group) > 0 else None


def _collect_text_segments(elem, parent_x, parent_y, parent_font_size,
                            parent_anchor, parent_fill, segments):
    """Collect text segments from <text> and nested <tspan> elements."""
    # Direct text content
    if elem.text and elem.text.strip():
        segments.append({
            "text": elem.text.strip(),
            "x": parent_x,
            "y": parent_y,
            "fontSize": parent_font_size,
            "textAnchor": parent_anchor,
            "fill": parent_fill,
        })

    # Process children (tspan etc.)
    cursor_x = parent_x
    for child in elem:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "tspan":
            # tspan can override position and style
            tx = float(_get_attr(child, "x", str(cursor_x)))
            ty = float(_get_attr(child, "y", str(parent_y)))
            dx = float(_get_attr(child, "dx", "0"))
            dy = float(_get_attr(child, "dy", "0"))
            fs = _parse_font_size(_get_attr(child, "font-size", str(parent_font_size)))
            anchor = _get_attr(child, "text-anchor", parent_anchor)
            fill = _get_attr(child, "fill", parent_fill)

            tx += dx
            ty += dy

            if child.text and child.text.strip():
                segments.append({
                    "text": child.text.strip(),
                    "x": tx,
                    "y": ty,
                    "fontSize": fs,
                    "textAnchor": anchor,
                    "fill": fill,
                })

            # Recurse into nested tspans
            _collect_text_segments(child, tx, ty, fs, anchor, fill, segments)

        # Tail text after child element
        if child.tail and child.tail.strip():
            segments.append({
                "text": child.tail.strip(),
                "x": cursor_x,
                "y": parent_y,
                "fontSize": parent_font_size,
                "textAnchor": parent_anchor,
                "fill": parent_fill,
            })


def _render_text_segment(text, x, y, font_size, text_anchor, fill,
                          glyph_set, cmap, units_per_em):
    """Render a text segment to a list of SVG path d strings."""
    # Pre-compute total width for text-anchor
    total_width = 0
    for ch in text:
        _, adv = _get_glyph_path_d(glyph_set, cmap, ch, units_per_em, font_size, 0, 0)
        total_width += adv

    offset_x = 0
    if text_anchor == "middle":
        offset_x = -total_width / 2
    elif text_anchor == "end":
        offset_x = -total_width

    cursor_x = x + offset_x
    paths = []

    for ch in text:
        path_d, adv = _get_glyph_path_d(
            glyph_set, cmap, ch, units_per_em, font_size, cursor_x, y
        )
        if path_d:
            paths.append(path_d)
        cursor_x += adv

    return paths
