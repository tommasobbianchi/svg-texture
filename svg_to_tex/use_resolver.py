"""
Resolve <use> references by inlining cloned content.
"""

import copy
import xml.etree.ElementTree as ET
from typing import Dict, Optional

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"


def _strip_ns(tag: str) -> str:
    """Remove XML namespace from tag name."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _build_id_map(root: ET.Element) -> Dict[str, ET.Element]:
    """Build a mapping of id -> element for the entire tree."""
    id_map = {}
    for elem in root.iter():
        elem_id = elem.get("id")
        if elem_id:
            id_map[elem_id] = elem
    return id_map


def _get_href(elem: ET.Element) -> Optional[str]:
    """Get href from a <use> element, checking both href and xlink:href."""
    href = elem.get("href")
    if href is None:
        href = elem.get(f"{{{XLINK_NS}}}href")
    return href


def resolve_uses(root: ET.Element, max_depth: int = 10) -> None:
    """Resolve all <use> elements in the SVG tree by inlining cloned content.

    Modifies the tree in place. Handles nested <use> elements up to max_depth.

    The <use> element is replaced with a <g> element containing:
    - A transform combining the use's x/y offset and any existing transform
    - A deep copy of the referenced element's content
    """
    for _ in range(max_depth):
        id_map = _build_id_map(root)
        uses_found = False

        # Find all <use> elements and their parents
        uses = []
        for parent in root.iter():
            for i, child in enumerate(list(parent)):
                if _strip_ns(child.tag) == "use":
                    uses.append((parent, i, child))

        if not uses:
            break

        uses_found = True
        for parent, idx, use_elem in uses:
            href = _get_href(use_elem)
            if not href or not href.startswith("#"):
                # Remove unresolvable use elements
                parent.remove(use_elem)
                continue

            ref_id = href[1:]  # Strip '#'
            ref_elem = id_map.get(ref_id)
            if ref_elem is None:
                parent.remove(use_elem)
                continue

            # Create a <g> to replace the <use>
            g = ET.Element("g")

            # Build transform from x, y attributes and existing transform
            x = use_elem.get("x", "0")
            y = use_elem.get("y", "0")
            transforms = []

            existing_transform = use_elem.get("transform")
            if existing_transform:
                transforms.append(existing_transform)

            try:
                x_val = float(x)
                y_val = float(y)
                if x_val != 0 or y_val != 0:
                    transforms.append(f"translate({x_val},{y_val})")
            except ValueError:
                pass

            if transforms:
                g.set("transform", " ".join(transforms))

            # Copy non-structural attributes from <use> to <g>
            skip_attrs = {"x", "y", "width", "height", "href",
                          f"{{{XLINK_NS}}}href", "transform", "id"}
            for attr, val in use_elem.attrib.items():
                if attr not in skip_attrs:
                    g.set(attr, val)

            # Deep copy the referenced element
            ref_copy = copy.deepcopy(ref_elem)

            # If the referenced element is a <symbol>, treat like <svg>
            ref_tag = _strip_ns(ref_copy.tag)
            if ref_tag == "symbol":
                # Symbols act like nested SVGs - copy children into g
                for child in list(ref_copy):
                    g.append(child)
                # Apply symbol's viewBox if present (simplified handling)
                vb = ref_copy.get("viewBox")
                if vb:
                    g.set("viewBox", vb)
            else:
                # Remove id from copy to avoid duplicates
                if "id" in ref_copy.attrib:
                    del ref_copy.attrib["id"]
                g.append(ref_copy)

            # Replace <use> with <g> in parent
            parent.remove(use_elem)
            parent.insert(idx, g)

        if not uses_found:
            break
