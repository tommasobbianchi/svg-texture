"""Integration tests: SVG -> SVGTEX end-to-end."""

import pytest
from svg_to_tex.svg_parser import parse_svg
from svg_to_tex.region_analyzer import filter_filled_paths
from svg_to_tex.encoder import encode_svgtex
from svg_to_tex.stroke_outliner import stroke_to_outlines


def process_svg(svg_content: str, precision: int = 2, include_strokes: bool = False,
                stroke_width: float = None) -> str:
    """Full pipeline: SVG string -> SVGTEX string."""
    viewbox, paths = parse_svg(svg_content, include_strokes=include_strokes)
    if include_strokes:
        paths = stroke_to_outlines(paths, stroke_width_override=stroke_width)
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
        lines = [l for l in result.strip().split("|") if not l.startswith("#")]
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
        lines = [l for l in result.strip().split("|") if not l.startswith("#") and not l.startswith("V")]
        # Should have 2 paths (one for each use)
        assert len(lines) == 2


class TestEvenOdd:
    def test_evenodd_fill_rule(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <path d="M 0,0 L 100,0 L 100,100 L 0,100 Z" fill="black" fill-rule="evenodd"/>
        </svg>'''
        result = process_svg(svg)
        lines = [l for l in result.strip().split("|") if not l.startswith("#") and not l.startswith("V")]
        assert lines[0].startswith("E")

    def test_default_nonzero(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <path d="M 0,0 L 100,0 L 100,100 L 0,100 Z" fill="black"/>
        </svg>'''
        result = process_svg(svg)
        lines = [l for l in result.strip().split("|") if not l.startswith("#") and not l.startswith("V")]
        assert lines[0].startswith("N")


class TestEdgeCases:
    def test_empty_svg(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        </svg>'''
        result = process_svg(svg)
        lines = [l for l in result.strip().split("|") if not l.startswith("#")]
        assert len(lines) == 1  # Only viewbox

    def test_hidden_element(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <rect x="10" y="10" width="80" height="80" fill="black" display="none"/>
        </svg>'''
        result = process_svg(svg)
        lines = [l for l in result.strip().split("|") if not l.startswith("#")]
        assert len(lines) == 1  # Only viewbox

    def test_style_fill(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <rect x="10" y="10" width="80" height="80" style="fill:red"/>
        </svg>'''
        result = process_svg(svg)
        lines = [l for l in result.strip().split("|") if not l.startswith("#") and not l.startswith("V")]
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


class TestCSSStyleBlocks:
    def test_class_selector_fill(self):
        """CSS class selector sets fill on element."""
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <style>.filled { fill: red; }</style>
            <rect class="filled" x="10" y="10" width="80" height="80"/>
        </svg>'''
        result = process_svg(svg)
        parts = [l for l in result.strip().split("|") if not l.startswith("#") and not l.startswith("V")]
        assert len(parts) == 1

    def test_class_selector_fill_none(self):
        """CSS class setting fill:none removes element from output."""
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <style>.hidden { fill: none; }</style>
            <rect class="hidden" x="10" y="10" width="80" height="80"/>
        </svg>'''
        result = process_svg(svg)
        parts = [l for l in result.strip().split("|") if not l.startswith("#") and not l.startswith("V")]
        assert len(parts) == 0

    def test_id_selector(self):
        """CSS #id selector applies styles."""
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <style>#mybox { fill: blue; }</style>
            <rect id="mybox" x="10" y="10" width="80" height="80" fill="none"/>
        </svg>'''
        result = process_svg(svg)
        parts = [l for l in result.strip().split("|") if not l.startswith("#") and not l.startswith("V")]
        # id selector should override the presentation attribute fill="none"
        assert len(parts) == 1

    def test_css_overrides_presentation_attr(self):
        """CSS should override presentation attributes."""
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <style>.nofill { fill: none; }</style>
            <rect class="nofill" x="10" y="10" width="80" height="80" fill="red"/>
        </svg>'''
        result = process_svg(svg)
        parts = [l for l in result.strip().split("|") if not l.startswith("#") and not l.startswith("V")]
        # CSS fill:none should override fill="red"
        assert len(parts) == 0

    def test_inline_style_overrides_css(self):
        """Inline style should override CSS rules."""
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <style>.nofill { fill: none; }</style>
            <rect class="nofill" x="10" y="10" width="80" height="80" style="fill:blue"/>
        </svg>'''
        result = process_svg(svg)
        parts = [l for l in result.strip().split("|") if not l.startswith("#") and not l.startswith("V")]
        # inline style fill:blue should override CSS fill:none
        assert len(parts) == 1

    def test_css_fill_rule_evenodd(self):
        """CSS can set fill-rule."""
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <style>.eo { fill-rule: evenodd; fill: black; }</style>
            <path class="eo" d="M 0,0 L 100,0 L 100,100 L 0,100 Z"/>
        </svg>'''
        result = process_svg(svg)
        parts = [l for l in result.strip().split("|") if not l.startswith("#") and not l.startswith("V")]
        assert len(parts) == 1
        assert parts[0].startswith("E")

    def test_multiple_classes(self):
        """Element with multiple CSS classes gets combined rules."""
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <style>.colored { fill: red; } .rule { fill-rule: evenodd; }</style>
            <path class="colored rule" d="M 0,0 L 100,0 L 100,100 L 0,100 Z"/>
        </svg>'''
        result = process_svg(svg)
        parts = [l for l in result.strip().split("|") if not l.startswith("#") and not l.startswith("V")]
        assert len(parts) == 1
        assert parts[0].startswith("E")

    def test_no_style_block(self):
        """SVG without <style> block works normally."""
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <rect x="10" y="10" width="80" height="80" fill="black"/>
        </svg>'''
        result = process_svg(svg)
        parts = [l for l in result.strip().split("|") if not l.startswith("#") and not l.startswith("V")]
        assert len(parts) == 1

    def test_css_comment_ignored(self):
        """CSS comments are properly stripped."""
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <style>/* this is a comment */ .box { fill: red; }</style>
            <rect class="box" x="10" y="10" width="80" height="80"/>
        </svg>'''
        result = process_svg(svg)
        parts = [l for l in result.strip().split("|") if not l.startswith("#") and not l.startswith("V")]
        assert len(parts) == 1


class TestStrokeIntegration:
    def test_stroke_only_rect(self):
        """Stroke-only rect produces outline with include_strokes=True."""
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <rect x="10" y="10" width="80" height="80" fill="none" stroke="black" stroke-width="2"/>
        </svg>'''
        result = process_svg(svg, include_strokes=True)
        parts = [l for l in result.strip().split("|") if not l.startswith("#") and not l.startswith("V")]
        assert len(parts) >= 1

    def test_stroke_only_line(self):
        """A <line> element with stroke produces outline."""
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <line x1="10" y1="50" x2="90" y2="50" stroke="black" stroke-width="3"/>
        </svg>'''
        result = process_svg(svg, include_strokes=True)
        parts = [l for l in result.strip().split("|") if not l.startswith("#") and not l.startswith("V")]
        assert len(parts) >= 1

    def test_stroke_style_attribute(self):
        """Stroke defined in style attribute is detected."""
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <path d="M 10,10 L 90,10 L 90,90" style="fill:none;stroke:#000;stroke-width:2"/>
        </svg>'''
        result = process_svg(svg, include_strokes=True)
        parts = [l for l in result.strip().split("|") if not l.startswith("#") and not l.startswith("V")]
        assert len(parts) >= 1

    def test_default_ignores_strokes(self):
        """Without include_strokes, stroke-only paths are still ignored."""
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <rect x="10" y="10" width="80" height="80" fill="none" stroke="black" stroke-width="2"/>
        </svg>'''
        result = process_svg(svg)
        parts = [l for l in result.strip().split("|") if not l.startswith("#") and not l.startswith("V")]
        assert len(parts) == 0

    def test_mixed_fill_and_stroke(self):
        """SVG with both filled and stroke-only elements."""
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <rect x="10" y="10" width="30" height="30" fill="blue"/>
            <line x1="50" y1="50" x2="90" y2="90" stroke="red" stroke-width="2"/>
        </svg>'''
        result = process_svg(svg, include_strokes=True)
        parts = [l for l in result.strip().split("|") if not l.startswith("#") and not l.startswith("V")]
        assert len(parts) == 2

    def test_stroke_width_override(self):
        """CLI stroke-width override affects output."""
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <path d="M 0,50 L 100,50" fill="none" stroke="black" stroke-width="1"/>
        </svg>'''
        narrow = process_svg(svg, include_strokes=True, stroke_width=1.0)
        wide = process_svg(svg, include_strokes=True, stroke_width=5.0)
        # Both should produce output, but with different coordinates
        assert narrow != wide
        # Wide outline should have larger Y offset from center (50)
        assert "52.5" in wide  # 50 + 5/2 = 52.5
        assert "50.5" in narrow  # 50 + 1/2 = 50.5
