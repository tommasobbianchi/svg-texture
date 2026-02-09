"""
CLI entry point for SVG to SVGTEX converter.

Usage:
    python -m svg_to_tex input.svg [-o output.txt] [--stdout] [--precision 2] [--copy]

Note: The FeatureScript plugin can now parse SVG files directly.
This CLI is optional, for users who prefer pre-converting to SVGTEX format.
"""

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from .svg_parser import parse_svg
from .region_analyzer import filter_filled_paths, estimate_entity_count
from .encoder import encode_svgtex
from .stroke_outliner import stroke_to_outlines
from .viewbox_clipper import clip_paths_to_viewbox


def _check_svg_warnings(svg_content: str):
    """Check for SVG features that may cause issues and print warnings."""
    warnings = []

    try:
        root = ET.fromstring(svg_content)
    except ET.ParseError:
        return warnings

    ns = "{http://www.w3.org/2000/svg}"

    # Check for <style> blocks
    for elem in root.iter(f"{ns}style"):
        warnings.append("SVG contains <style> CSS blocks. Basic class/id selectors are supported, but complex CSS may cause missing geometry.")
        break
    for elem in root.iter("style"):
        warnings.append("SVG contains <style> CSS blocks. Basic class/id selectors are supported, but complex CSS may cause missing geometry.")
        break

    # Check for <text> elements
    has_text = False
    for elem in root.iter(f"{ns}text"):
        has_text = True
        break
    if not has_text:
        for elem in root.iter("text"):
            has_text = True
            break
    if has_text:
        try:
            from .text_to_path import HAS_FONTTOOLS
            if HAS_FONTTOOLS:
                warnings.append("SVG contains <text> elements (will be converted to paths using system font).")
            else:
                warnings.append("SVG contains <text> elements. Install fonttools for text-to-path conversion: pip install fonttools")
        except ImportError:
            warnings.append("SVG contains <text> elements. Install fonttools for text-to-path conversion: pip install fonttools")

    # Check for gradient/pattern fills (url references)
    url_pattern = re.compile(r'url\s*\(')
    for elem in root.iter():
        for attr in ("fill", "stroke"):
            val = elem.get(attr, "")
            if url_pattern.search(val):
                warnings.append("SVG uses gradient/pattern fills (url references). These paths may produce empty output.")
                break
        style = elem.get("style", "")
        if url_pattern.search(style):
            warnings.append("SVG uses gradient/pattern fills in CSS styles. These paths may produce empty output.")
            break

    # Deduplicate
    return list(dict.fromkeys(warnings))


def main():
    parser = argparse.ArgumentParser(
        description="Convert SVG files to SVGTEX format for FeatureScript texture feature.",
        prog="svg_to_tex",
    )
    parser.add_argument(
        "input",
        help="Input SVG file path",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file path (default: <input_name>.txt)",
        default=None,
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print output to stdout instead of writing a file",
    )
    parser.add_argument(
        "--precision",
        type=int,
        default=2,
        help="Decimal precision for coordinates (default: 2)",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Copy output to system clipboard (requires pyperclip)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print statistics to stderr",
    )
    parser.add_argument(
        "--no-strokes",
        action="store_true",
        help="Disable stroke-to-outline conversion (strokes are converted by default)",
    )
    # Keep --include-strokes for backward compat (now a no-op since it's default)
    parser.add_argument(
        "--include-strokes",
        action="store_true",
        help=argparse.SUPPRESS,  # Hidden: strokes are now included by default
    )
    parser.add_argument(
        "--stroke-width",
        type=float,
        default=None,
        help="Override stroke width for all stroked paths (default: use SVG attribute)",
    )
    parser.add_argument(
        "--max-entities",
        type=int,
        default=None,
        help="Maximum sketch entities. Paths are dropped to stay within limit.",
    )
    parser.add_argument(
        "--font",
        type=str,
        default=None,
        help="Path to TTF/OTF font file for text-to-path conversion",
    )
    parser.add_argument(
        "--no-text",
        action="store_true",
        help="Skip text-to-path conversion (text elements will be ignored)",
    )
    parser.add_argument(
        "--no-clip",
        action="store_true",
        help="Disable viewBox clipping (clipping is on by default for seamless tiling)",
    )

    args = parser.parse_args()

    # Read input SVG
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    svg_content = input_path.read_text(encoding="utf-8")

    # Check for potential issues
    warnings = _check_svg_warnings(svg_content)
    for w in warnings:
        print(f"Warning: {w}", file=sys.stderr)

    # Strokes are now included by default (unless --no-strokes)
    include_strokes = not args.no_strokes

    # Text conversion
    convert_text = not args.no_text

    # Process
    try:
        viewbox, paths = parse_svg(svg_content, include_strokes=include_strokes,
                                    font_path=args.font, convert_text=convert_text)
    except Exception as e:
        print(f"Error parsing SVG: {e}", file=sys.stderr)
        sys.exit(1)

    # Convert strokes to outlines
    if include_strokes:
        paths = stroke_to_outlines(paths, stroke_width_override=args.stroke_width)

    # Clip paths to viewBox for seamless tiling
    if not args.no_clip:
        paths = clip_paths_to_viewbox(paths, viewbox)

    # Filter to filled paths
    filled_paths = filter_filled_paths(paths)

    if not filled_paths:
        print("Warning: No filled paths found in SVG.", file=sys.stderr)

    # Max entities truncation
    if args.max_entities is not None and filled_paths:
        entity_count = estimate_entity_count(filled_paths)
        if entity_count > args.max_entities:
            # Drop paths from the end until under limit
            truncated = []
            running = 0
            for path in filled_paths:
                path_entities = sum(1 for cmd, _ in path.get("commands", []) if cmd in ("L", "C", "A"))
                if running + path_entities <= args.max_entities:
                    truncated.append(path)
                    running += path_entities
            dropped = len(filled_paths) - len(truncated)
            print(f"Warning: Truncated from {entity_count} to {running} entities "
                  f"({dropped} paths dropped to stay within --max-entities {args.max_entities}).",
                  file=sys.stderr)
            filled_paths = truncated

    # Encode
    svgtex = encode_svgtex(viewbox, filled_paths, args.precision)

    # Stats (always show entity count now)
    entity_count = estimate_entity_count(filled_paths)
    if entity_count > 2500:
        print(f"Warning: {entity_count} sketch entities. May be slow or exceed Onshape limits with tiling.",
              file=sys.stderr)

    if args.stats:
        print(f"ViewBox: {viewbox}", file=sys.stderr)
        print(f"Paths: {len(filled_paths)}", file=sys.stderr)
        print(f"Sketch entities: {entity_count}", file=sys.stderr)
        print(f"Output size: {len(svgtex)} chars", file=sys.stderr)

    # Output
    if args.stdout:
        print(svgtex)
    else:
        output_path = Path(args.output) if args.output else input_path.with_suffix(".txt")
        output_path.write_text(svgtex, encoding="utf-8")
        print(f"Written to {output_path}", file=sys.stderr)

    # Clipboard
    if args.copy:
        try:
            import pyperclip
            pyperclip.copy(svgtex)
            print("Copied to clipboard.", file=sys.stderr)
        except ImportError:
            print("Warning: pyperclip not installed. Cannot copy to clipboard.", file=sys.stderr)
            print("Install with: pip install pyperclip", file=sys.stderr)


if __name__ == "__main__":
    main()
