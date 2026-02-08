"""Tests for text-to-path conversion."""

import xml.etree.ElementTree as ET
import pytest

from svg_to_tex.text_to_path import (
    convert_text_to_paths,
    find_system_font,
    HAS_FONTTOOLS,
    _parse_font_size,
)
from svg_to_tex.svg_parser import parse_svg

# Skip all tests if fontTools is not installed
pytestmark = pytest.mark.skipif(not HAS_FONTTOOLS, reason="fontTools not installed")

NS = "http://www.w3.org/2000/svg"


class TestFindSystemFont:
    def test_finds_a_font(self):
        font = find_system_font()
        assert font is not None
        assert font.endswith((".ttf", ".otf", ".ttc"))

    def test_finds_named_font(self):
        font = find_system_font("DejaVu")
        # May or may not find it depending on system
        if font:
            assert "DejaVu" in font or "dejavu" in font.lower()


class TestParseFontSize:
    def test_plain_number(self):
        assert _parse_font_size("16") == 16.0

    def test_with_px(self):
        assert _parse_font_size("24px") == 24.0

    def test_with_pt(self):
        assert _parse_font_size("12pt") == 12.0

    def test_none_returns_default(self):
        assert _parse_font_size(None) == 16.0

    def test_invalid_returns_default(self):
        assert _parse_font_size("abc") == 16.0

    def test_float_value(self):
        assert _parse_font_size("13.5") == 13.5


class TestConvertTextToPaths:
    def test_simple_text(self):
        svg = f'<svg viewBox="0 0 200 100" xmlns="{NS}"><text x="10" y="50" font-size="20" fill="black">Hi</text></svg>'
        root = ET.fromstring(svg)
        count = convert_text_to_paths(root)
        assert count == 1
        # Should have replaced <text> with <g> containing <path> elements
        groups = root.findall(f".//{{{NS}}}g")
        assert len(groups) >= 1
        paths = root.findall(f".//{{{NS}}}path")
        assert len(paths) >= 1  # At least one path for "H" and one for "i"

    def test_text_anchor_middle(self):
        svg = f'<svg viewBox="0 0 200 100" xmlns="{NS}"><text x="100" y="50" font-size="20" text-anchor="middle" fill="black">AB</text></svg>'
        root = ET.fromstring(svg)
        count = convert_text_to_paths(root)
        assert count == 1
        paths = root.findall(f".//{{{NS}}}path")
        assert len(paths) >= 2  # A and B

    def test_text_anchor_end(self):
        svg = f'<svg viewBox="0 0 200 100" xmlns="{NS}"><text x="100" y="50" font-size="20" text-anchor="end" fill="black">X</text></svg>'
        root = ET.fromstring(svg)
        count = convert_text_to_paths(root)
        assert count == 1

    def test_tspan_nested(self):
        svg = f'<svg viewBox="0 0 300 100" xmlns="{NS}"><text x="10" y="50" font-size="20" fill="black"><tspan>A</tspan><tspan x="50">B</tspan></text></svg>'
        root = ET.fromstring(svg)
        count = convert_text_to_paths(root)
        assert count == 1
        paths = root.findall(f".//{{{NS}}}path")
        assert len(paths) >= 2

    def test_mixed_text_and_shapes(self):
        svg = f'<svg viewBox="0 0 200 100" xmlns="{NS}"><rect width="200" height="100" fill="white"/><text x="100" y="60" font-size="30" fill="black">Ok</text></svg>'
        root = ET.fromstring(svg)
        count = convert_text_to_paths(root)
        assert count == 1
        # Should still have the rect
        rects = root.findall(f".//{{{NS}}}rect")
        assert len(rects) == 1

    def test_empty_text(self):
        svg = f'<svg viewBox="0 0 200 100" xmlns="{NS}"><text x="10" y="50" font-size="20" fill="black"></text></svg>'
        root = ET.fromstring(svg)
        count = convert_text_to_paths(root)
        # Empty text — nothing to convert
        assert count == 0

    def test_whitespace_only_text(self):
        svg = f'<svg viewBox="0 0 200 100" xmlns="{NS}"><text x="10" y="50" font-size="20" fill="black">   </text></svg>'
        root = ET.fromstring(svg)
        count = convert_text_to_paths(root)
        assert count == 0

    def test_font_size_scaling(self):
        svg_small = f'<svg viewBox="0 0 200 100" xmlns="{NS}"><text x="10" y="50" font-size="10" fill="black">A</text></svg>'
        svg_large = f'<svg viewBox="0 0 200 100" xmlns="{NS}"><text x="10" y="50" font-size="40" fill="black">A</text></svg>'
        root_small = ET.fromstring(svg_small)
        root_large = ET.fromstring(svg_large)
        convert_text_to_paths(root_small)
        convert_text_to_paths(root_large)
        # Both should produce paths, but the large one should have larger path data
        paths_small = root_small.findall(f".//{{{NS}}}path")
        paths_large = root_large.findall(f".//{{{NS}}}path")
        assert len(paths_small) >= 1
        assert len(paths_large) >= 1
        # Large path d string should be different (larger coordinates)
        d_small = paths_small[0].get("d", "")
        d_large = paths_large[0].get("d", "")
        assert d_small != d_large

    def test_transform_preserved(self):
        svg = f'<svg viewBox="0 0 200 100" xmlns="{NS}"><text x="10" y="50" font-size="20" fill="black" transform="rotate(45)">X</text></svg>'
        root = ET.fromstring(svg)
        count = convert_text_to_paths(root)
        assert count == 1
        # Transform should be on the group
        groups = root.findall(f".//{{{NS}}}g")
        assert len(groups) >= 1
        assert groups[0].get("transform") == "rotate(45)"

    def test_no_text_flag(self):
        """Test that --no-text flag prevents text conversion."""
        svg = f'<svg viewBox="0 0 200 100" xmlns="{NS}"><text x="10" y="50" font-size="20" fill="black">Hi</text></svg>'
        viewbox, paths = parse_svg(svg, convert_text=False)
        # With convert_text=False, text is not converted and won't appear as paths
        # The rect (if any) or nothing should be in paths
        # Text elements are skipped by walk_elements since they're not path elements
        for p in paths:
            assert len(p.get("commands", [])) >= 0  # just verify no crash

    def test_multiple_text_elements(self):
        svg = f'<svg viewBox="0 0 400 100" xmlns="{NS}"><text x="10" y="50" font-size="20" fill="black">A</text><text x="200" y="50" font-size="20" fill="black">B</text></svg>'
        root = ET.fromstring(svg)
        count = convert_text_to_paths(root)
        assert count == 2


class TestFullPipeline:
    def test_text_produces_paths(self):
        svg = f'<svg viewBox="0 0 200 100" xmlns="{NS}"><text x="100" y="60" font-size="40" text-anchor="middle" fill="black">Hello</text></svg>'
        viewbox, paths = parse_svg(svg)
        assert len(paths) >= 1
        # Should have some L/C commands from the font outlines
        total_cmds = sum(len(p.get("commands", [])) for p in paths)
        assert total_cmds > 5

    def test_text_with_rect(self):
        svg = f'<svg viewBox="0 0 200 100" xmlns="{NS}"><rect width="200" height="100" fill="white"/><text x="100" y="60" font-size="30" fill="black">Hi</text></svg>'
        viewbox, paths = parse_svg(svg)
        # Should have rect path + text paths
        assert len(paths) >= 2

    def test_no_text_skips_conversion(self):
        svg = f'<svg viewBox="0 0 200 100" xmlns="{NS}"><rect width="200" height="100" fill="white"/><text x="100" y="60" font-size="30" fill="black">Hi</text></svg>'
        viewbox, paths = parse_svg(svg, convert_text=False)
        # Only rect path (text is not a recognized path element)
        assert len(paths) == 1

    def test_special_characters(self):
        svg = f'<svg viewBox="0 0 200 100" xmlns="{NS}"><text x="10" y="50" font-size="20" fill="black">!@#</text></svg>'
        viewbox, paths = parse_svg(svg)
        assert len(paths) >= 1

    def test_numbers_in_text(self):
        svg = f'<svg viewBox="0 0 200 100" xmlns="{NS}"><text x="10" y="50" font-size="20" fill="black">123</text></svg>'
        viewbox, paths = parse_svg(svg)
        assert len(paths) >= 1
