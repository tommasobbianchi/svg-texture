"""
CLI entry point for SVG to SVGTEX converter.

Usage:
    python -m svg_to_tex input.svg [-o output.txt] [--stdout] [--precision 2] [--copy]
"""

import argparse
import sys
from pathlib import Path

from .svg_parser import parse_svg
from .region_analyzer import filter_filled_paths, estimate_entity_count
from .encoder import encode_svgtex


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

    args = parser.parse_args()

    # Read input SVG
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    svg_content = input_path.read_text(encoding="utf-8")

    # Process
    try:
        viewbox, paths = parse_svg(svg_content)
    except Exception as e:
        print(f"Error parsing SVG: {e}", file=sys.stderr)
        sys.exit(1)

    # Filter to filled paths
    filled_paths = filter_filled_paths(paths)

    if not filled_paths:
        print("Warning: No filled paths found in SVG.", file=sys.stderr)

    # Encode
    svgtex = encode_svgtex(viewbox, filled_paths, args.precision)

    # Stats
    if args.stats:
        entity_count = estimate_entity_count(filled_paths)
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
