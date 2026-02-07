"""Integration tests: SVG -> SVGTEX end-to-end."""

import pytest
from svg_to_tex.svg_parser import parse_svg
from svg_to_tex.region_analyzer import filter_filled_paths
from svg_to_tex.encoder import encode_svgtex


def process_svg(svg_content: str, precision: int = 2) -> str:
    """Full pipeline: SVG string -> SVGTEX string."""
    viewbox, paths = parse_svg(svg_content)
    filled = filter_filled_paths(paths)
    return encode_svgtex(viewbox, filled, precision)


class TestSimpleSVGs:
    def test_rect(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <rect x="10" y="10" width="80" height="80" fill="black"/>
        </svg>'''
        result = process_svg(svg)
        assert result.startswith("V0,0,100,100")
        assert "M" in result
        assert "Z" in result

    def test_circle(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="25" fill="red"/>
        </svg>'''
        result = process_svg(svg)
        assert "V0,0,100,100" in result
        # Circle produces arcs or beziers
        assert "M" in result

    def test_no_fill(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <rect x="10" y="10" width="80" height="80" fill="none" stroke="black"/>
        </svg>'''
        result = process_svg(svg)
        lines = [l for l in result.strip().split("\n") if not l.startswith("#")]
        # Should only have viewbox, no paths
        assert len(lines) == 1

    def test_path_element(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <path d="M 10,10 L 90,10 L 90,90 L 10,90 Z" fill="blue"/>
        </svg>'''
        result = process_svg(svg)
        assert "M" in result
        assert "L" in result
        assert "Z" in result


class TestTransforms:
    def test_translated_rect(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
            <g transform="translate(50, 50)">
                <rect x="0" y="0" width="50" height="50" fill="black"/>
            </g>
        </svg>'''
        result = process_svg(svg)
        # The rect should be translated: first M should be around 50,50
        assert "M50" in result or "M 50" in result

    def test_scaled_rect(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
            <g transform="scale(2)">
                <rect x="10" y="10" width="20" height="20" fill="black"/>
            </g>
        </svg>'''
        result = process_svg(svg)
        # Rect at (10,10) scaled by 2 = (20,20)
        assert "M20,20" in result


class TestGroups:
    def test_nested_groups(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <g transform="translate(10,10)">
                <g transform="translate(5,5)">
                    <rect x="0" y="0" width="20" height="20" fill="black"/>
                </g>
            </g>
        </svg>'''
        result = process_svg(svg)
        # Should have combined translate of (15,15)
        assert "M15,15" in result


class TestUseElements:
    def test_simple_use(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">
            <defs>
                <rect id="myRect" x="0" y="0" width="40" height="40" fill="black"/>
            </defs>
            <use href="#myRect" x="10" y="10"/>
            <use href="#myRect" x="60" y="10"/>
        </svg>'''
        result = process_svg(svg)
        lines = [l for l in result.strip().split("\n") if not l.startswith("#") and not l.startswith("V")]
        # Should have 2 paths (one for each use)
        assert len(lines) == 2


class TestEvenOdd:
    def test_evenodd_fill_rule(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <path d="M 0,0 L 100,0 L 100,100 L 0,100 Z" fill="black" fill-rule="evenodd"/>
        </svg>'''
        result = process_svg(svg)
        lines = [l for l in result.strip().split("\n") if not l.startswith("#") and not l.startswith("V")]
        assert lines[0].startswith("E")

    def test_default_nonzero(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <path d="M 0,0 L 100,0 L 100,100 L 0,100 Z" fill="black"/>
        </svg>'''
        result = process_svg(svg)
        lines = [l for l in result.strip().split("\n") if not l.startswith("#") and not l.startswith("V")]
        assert lines[0].startswith("N")


class TestEdgeCases:
    def test_empty_svg(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        </svg>'''
        result = process_svg(svg)
        lines = [l for l in result.strip().split("\n") if not l.startswith("#")]
        assert len(lines) == 1  # Only viewbox

    def test_hidden_element(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <rect x="10" y="10" width="80" height="80" fill="black" display="none"/>
        </svg>'''
        result = process_svg(svg)
        lines = [l for l in result.strip().split("\n") if not l.startswith("#")]
        assert len(lines) == 1  # Only viewbox

    def test_style_fill(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <rect x="10" y="10" width="80" height="80" style="fill:red"/>
        </svg>'''
        result = process_svg(svg)
        lines = [l for l in result.strip().split("\n") if not l.startswith("#") and not l.startswith("V")]
        assert len(lines) == 1

    def test_polygon(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <polygon points="50,0 100,100 0,100" fill="black"/>
        </svg>'''
        result = process_svg(svg)
        assert "M" in result
        assert "Z" in result

    def test_viewbox_fallback(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="200" height="150">
            <rect x="0" y="0" width="200" height="150" fill="black"/>
        </svg>'''
        result = process_svg(svg)
        assert "V0,0,200,150" in result
