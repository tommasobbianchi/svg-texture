"""Tests for viewBox clipping (Sutherland-Hodgman polygon clipping)."""

import os
import math
import pytest

from svg_to_tex.viewbox_clipper import (
    clip_paths_to_viewbox,
    _clip_single_path,
    _split_into_subpaths,
    _subpath_bounds,
    _is_inside_rect,
    _is_outside_rect,
    _flatten_subpath_to_polygon,
    _sutherland_hodgman_clip,
    _polygon_to_commands,
)

TEXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "textures")


# ─── Bounding Box Tests ──────────────────────────────────────────────────


class TestSubpathBounds:
    def test_line_only_subpath(self):
        cmds = [("M", [10, 20]), ("L", [50, 80]), ("L", [30, 10]), ("Z", [])]
        bbox = _subpath_bounds(cmds)
        assert bbox == (10, 10, 50, 80)

    def test_single_point(self):
        cmds = [("M", [5, 5]), ("Z", [])]
        bbox = _subpath_bounds(cmds)
        assert bbox == (5, 5, 5, 5)

    def test_empty_commands(self):
        assert _subpath_bounds([]) is None

    def test_arc_bounds_conservative(self):
        """Arc bbox includes center ± radius."""
        cmds = [("M", [75, 50]), ("A", [50, 50, 25, 0, 180]), ("Z", [])]
        bbox = _subpath_bounds(cmds)
        min_x, min_y, max_x, max_y = bbox
        assert min_x <= 25
        assert max_x >= 75
        assert min_y <= 25
        assert max_y >= 75


# ─── Inside/Outside Tests ────────────────────────────────────────────────


class TestInsideOutside:
    def test_fully_inside(self):
        bbox = (10, 10, 90, 90)
        rect = (0, 0, 100, 100)
        assert _is_inside_rect(bbox, rect) is True
        assert _is_outside_rect(bbox, rect) is False

    def test_fully_outside_right(self):
        bbox = (110, 10, 150, 90)
        rect = (0, 0, 100, 100)
        assert _is_inside_rect(bbox, rect) is False
        assert _is_outside_rect(bbox, rect) is True

    def test_fully_outside_left(self):
        bbox = (-50, 10, -10, 90)
        rect = (0, 0, 100, 100)
        assert _is_outside_rect(bbox, rect) is True

    def test_partially_overlapping(self):
        bbox = (50, 50, 150, 150)
        rect = (0, 0, 100, 100)
        assert _is_inside_rect(bbox, rect) is False
        assert _is_outside_rect(bbox, rect) is False

    def test_touching_edge(self):
        """Points exactly on boundary are considered inside."""
        bbox = (0, 0, 100, 100)
        rect = (0, 0, 100, 100)
        assert _is_inside_rect(bbox, rect) is True


# ─── Sutherland-Hodgman Tests ────────────────────────────────────────────


class TestSutherlandHodgman:
    def test_square_fully_inside(self):
        polygon = [(10, 10), (90, 10), (90, 90), (10, 90)]
        rect = (0, 0, 100, 100)
        result = _sutherland_hodgman_clip(polygon, rect)
        assert len(result) == 1
        assert len(result[0]) == 4

    def test_square_fully_outside(self):
        polygon = [(110, 110), (150, 110), (150, 150), (110, 150)]
        rect = (0, 0, 100, 100)
        result = _sutherland_hodgman_clip(polygon, rect)
        assert len(result) == 0

    def test_square_half_overlapping(self):
        """Square from (50,-50) to (150,50) clipped to (0,0,100,100)."""
        polygon = [(50, -50), (150, -50), (150, 50), (50, 50)]
        rect = (0, 0, 100, 100)
        result = _sutherland_hodgman_clip(polygon, rect)
        assert len(result) == 1
        # Should be clipped to roughly (50,0)-(100,0)-(100,50)-(50,50)
        poly = result[0]
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        assert min(xs) >= -0.02
        assert max(xs) <= 100.02
        assert min(ys) >= -0.02
        assert max(ys) <= 100.02

    def test_triangle_one_vertex_outside(self):
        """Triangle with one vertex outside the clip rect."""
        polygon = [(50, 50), (150, 50), (50, 150)]
        rect = (0, 0, 100, 100)
        result = _sutherland_hodgman_clip(polygon, rect)
        assert len(result) == 1
        poly = result[0]
        # All clipped vertices should be within bounds
        for x, y in poly:
            assert x >= -0.02 and x <= 100.02
            assert y >= -0.02 and y <= 100.02

    def test_exact_boundary_square(self):
        """Square exactly matching the clip rect."""
        polygon = [(0, 0), (100, 0), (100, 100), (0, 100)]
        rect = (0, 0, 100, 100)
        result = _sutherland_hodgman_clip(polygon, rect)
        assert len(result) == 1
        assert len(result[0]) == 4

    def test_thin_rectangle_crossing(self):
        """Thin horizontal rectangle crossing left and right boundaries."""
        polygon = [(-20, 45), (120, 45), (120, 55), (-20, 55)]
        rect = (0, 0, 100, 100)
        result = _sutherland_hodgman_clip(polygon, rect)
        assert len(result) == 1
        poly = result[0]
        xs = [p[0] for p in poly]
        assert min(xs) == pytest.approx(0, abs=0.02)
        assert max(xs) == pytest.approx(100, abs=0.02)

    def test_degenerate_line(self):
        """Two-point polygon is degenerate — should return empty."""
        polygon = [(10, 10), (50, 50)]
        rect = (0, 0, 100, 100)
        result = _sutherland_hodgman_clip(polygon, rect)
        assert len(result) == 0


# ─── Flatten Subpath Tests ───────────────────────────────────────────────


class TestFlattenSubpath:
    def test_all_lines(self):
        cmds = [("M", [0, 0]), ("L", [10, 0]), ("L", [10, 10]), ("L", [0, 10]), ("Z", [])]
        poly = _flatten_subpath_to_polygon(cmds)
        assert len(poly) == 4
        assert poly[0] == (0, 0)
        assert poly[1] == (10, 0)

    def test_with_cubic(self):
        cmds = [("M", [0, 0]), ("C", [10, 0, 10, 10, 0, 10]), ("Z", [])]
        poly = _flatten_subpath_to_polygon(cmds, segments_per_curve=8)
        # Start point + 8 curve segments
        assert len(poly) == 9

    def test_with_arc(self):
        cmds = [("M", [75, 50]), ("A", [50, 50, 25, 0, 180]), ("Z", [])]
        poly = _flatten_subpath_to_polygon(cmds, segments_per_curve=8)
        # Start point + 8 arc segments
        assert len(poly) == 9


# ─── Split Subpaths Tests ───────────────────────────────────────────────


class TestSplitSubpaths:
    def test_single_subpath(self):
        cmds = [("M", [0, 0]), ("L", [10, 0]), ("L", [10, 10]), ("Z", [])]
        sps = _split_into_subpaths(cmds)
        assert len(sps) == 1
        assert sps[0][0] == ("M", [0, 0])
        assert sps[0][-1] == ("Z", [])

    def test_two_subpaths(self):
        cmds = [
            ("M", [0, 0]), ("L", [10, 0]), ("Z", []),
            ("M", [20, 20]), ("L", [30, 20]), ("Z", []),
        ]
        sps = _split_into_subpaths(cmds)
        assert len(sps) == 2

    def test_missing_z_added(self):
        cmds = [("M", [0, 0]), ("L", [10, 0]), ("L", [10, 10])]
        sps = _split_into_subpaths(cmds)
        assert len(sps) == 1
        assert sps[0][-1] == ("Z", [])


# ─── Polygon to Commands Tests ───────────────────────────────────────────


class TestPolygonToCommands:
    def test_triangle(self):
        poly = [(0, 0), (10, 0), (5, 10)]
        cmds = _polygon_to_commands(poly)
        assert cmds[0] == ("M", [0, 0])
        assert cmds[1] == ("L", [10, 0])
        assert cmds[2] == ("L", [5, 10])
        assert cmds[3] == ("Z", [])

    def test_degenerate(self):
        """Fewer than 3 points produces no commands."""
        assert _polygon_to_commands([(0, 0), (1, 1)]) == []
        assert _polygon_to_commands([]) == []


# ─── Clip Single Path Tests ──────────────────────────────────────────────


class TestClipSinglePath:
    def test_path_fully_inside(self):
        """Path inside viewBox is returned unchanged."""
        cmds = [("M", [10, 10]), ("L", [90, 10]), ("L", [90, 90]), ("L", [10, 90]), ("Z", [])]
        rect = (0, 0, 100, 100)
        result = _clip_single_path(cmds, rect)
        assert result == cmds

    def test_path_fully_outside(self):
        cmds = [("M", [110, 10]), ("L", [150, 10]), ("L", [150, 50]), ("Z", [])]
        rect = (0, 0, 100, 100)
        result = _clip_single_path(cmds, rect)
        assert result is None

    def test_path_crossing(self):
        """Path crossing the boundary is clipped."""
        cmds = [("M", [-20, 40]), ("L", [120, 40]), ("L", [120, 60]), ("L", [-20, 60]), ("Z", [])]
        rect = (0, 0, 100, 100)
        result = _clip_single_path(cmds, rect)
        assert result is not None
        # Verify all coordinates are within bounds
        for cmd, params in result:
            if cmd in ("M", "L"):
                assert params[0] >= -0.02 and params[0] <= 100.02
                assert params[1] >= -0.02 and params[1] <= 100.02

    def test_empty_commands(self):
        assert _clip_single_path([], (0, 0, 100, 100)) is None

    def test_multi_subpath_mixed(self):
        """Two subpaths: one inside, one outside."""
        cmds = [
            ("M", [10, 10]), ("L", [20, 10]), ("L", [20, 20]), ("Z", []),
            ("M", [110, 10]), ("L", [120, 10]), ("L", [120, 20]), ("Z", []),
        ]
        rect = (0, 0, 100, 100)
        result = _clip_single_path(cmds, rect)
        assert result is not None
        # Only the inside subpath should remain
        m_count = sum(1 for cmd, _ in result if cmd == "M")
        assert m_count == 1


# ─── Top-Level clip_paths_to_viewbox Tests ───────────────────────────────


class TestClipPathsToViewbox:
    def test_empty_input(self):
        assert clip_paths_to_viewbox([], (0, 0, 100, 100)) == []

    def test_all_inside(self):
        paths = [{
            "commands": [("M", [10, 10]), ("L", [90, 10]), ("L", [90, 90]), ("Z", [])],
            "fill_rule": "nonzero",
        }]
        result = clip_paths_to_viewbox(paths, (0, 0, 100, 100))
        assert len(result) == 1
        assert result[0]["fill_rule"] == "nonzero"

    def test_all_outside(self):
        paths = [{
            "commands": [("M", [110, 10]), ("L", [150, 10]), ("L", [150, 50]), ("Z", [])],
            "fill_rule": "evenodd",
        }]
        result = clip_paths_to_viewbox(paths, (0, 0, 100, 100))
        assert len(result) == 0

    def test_mixed(self):
        paths = [
            {
                "commands": [("M", [10, 10]), ("L", [20, 10]), ("L", [20, 20]), ("Z", [])],
                "fill_rule": "nonzero",
            },
            {
                "commands": [("M", [200, 200]), ("L", [300, 200]), ("L", [300, 300]), ("Z", [])],
                "fill_rule": "nonzero",
            },
        ]
        result = clip_paths_to_viewbox(paths, (0, 0, 100, 100))
        assert len(result) == 1

    def test_fill_rule_preserved(self):
        paths = [{
            "commands": [("M", [-20, 40]), ("L", [120, 40]), ("L", [120, 60]), ("L", [-20, 60]), ("Z", [])],
            "fill_rule": "evenodd",
        }]
        result = clip_paths_to_viewbox(paths, (0, 0, 100, 100))
        assert len(result) == 1
        assert result[0]["fill_rule"] == "evenodd"

    def test_nonzero_origin_viewbox_outside(self):
        """Path fully outside non-zero-origin viewBox."""
        paths = [{
            "commands": [("M", [1, 1]), ("L", [5, 1]), ("L", [5, 5]), ("Z", [])],
            "fill_rule": "nonzero",
        }]
        result = clip_paths_to_viewbox(paths, (10, 10, 80, 80))
        # Path is fully outside viewBox (10,10)-(90,90)
        assert len(result) == 0

    def test_nonzero_origin_viewbox_inside(self):
        """Path inside non-zero-origin viewBox."""
        paths = [{
            "commands": [("M", [20, 20]), ("L", [30, 20]), ("L", [30, 30]), ("Z", [])],
            "fill_rule": "nonzero",
        }]
        result = clip_paths_to_viewbox(paths, (10, 10, 80, 80))
        assert len(result) == 1

    def test_stroke_metadata_preserved(self):
        """Extra keys like 'source' are preserved."""
        paths = [{
            "commands": [("M", [10, 10]), ("L", [20, 10]), ("L", [20, 20]), ("Z", [])],
            "fill_rule": "nonzero",
            "source": "stroke",
            "stroke_width": 2.0,
        }]
        result = clip_paths_to_viewbox(paths, (0, 0, 100, 100))
        assert len(result) == 1
        assert result[0]["source"] == "stroke"
        assert result[0]["stroke_width"] == 2.0


# ─── Honeycomb Integration ───────────────────────────────────────────────


class TestHoneycombClipping:
    def _load_honeycomb(self):
        from svg_to_tex.svg_parser import parse_svg
        from svg_to_tex.stroke_outliner import stroke_to_outlines
        svg_path = os.path.join(TEXTURES_DIR, "honeycomb.svg")
        if not os.path.exists(svg_path):
            pytest.skip("honeycomb.svg not found")
        with open(svg_path) as f:
            svg_content = f.read()
        viewbox, paths = parse_svg(svg_content, include_strokes=True)
        paths = stroke_to_outlines(paths)
        return viewbox, paths

    def test_unclipped_extends_beyond_viewbox(self):
        """Verify the problem: unclipped paths extend beyond viewBox."""
        viewbox, paths = self._load_honeycomb()
        min_x, min_y, w, h = viewbox
        max_x, max_y = min_x + w, min_y + h
        has_outside = False
        for path in paths:
            for cmd, params in path["commands"]:
                if cmd in ("M", "L"):
                    if params[0] < min_x - 0.1 or params[0] > max_x + 0.1:
                        has_outside = True
                    if params[1] < min_y - 0.1 or params[1] > max_y + 0.1:
                        has_outside = True
        assert has_outside, "Expected honeycomb to have coords outside viewBox"

    def test_clipped_within_viewbox(self):
        """After clipping, all coordinates are within viewBox bounds."""
        viewbox, paths = self._load_honeycomb()
        clipped = clip_paths_to_viewbox(paths, viewbox)
        min_x, min_y, w, h = viewbox
        max_x, max_y = min_x + w, min_y + h
        for path in clipped:
            for cmd, params in path["commands"]:
                if cmd in ("M", "L"):
                    assert params[0] >= min_x - 0.1, f"x={params[0]} < {min_x}"
                    assert params[0] <= max_x + 0.1, f"x={params[0]} > {max_x}"
                    assert params[1] >= min_y - 0.1, f"y={params[1]} < {min_y}"
                    assert params[1] <= max_y + 0.1, f"y={params[1]} > {max_y}"

    def test_clipped_has_paths(self):
        """Clipping should not remove all paths."""
        viewbox, paths = self._load_honeycomb()
        clipped = clip_paths_to_viewbox(paths, viewbox)
        assert len(clipped) > 0, "Clipping removed all paths"

    def test_clipped_path_count_reasonable(self):
        """Clipped path count should be <= original (some fully-outside paths removed)."""
        viewbox, paths = self._load_honeycomb()
        clipped = clip_paths_to_viewbox(paths, viewbox)
        assert len(clipped) <= len(paths)


# ─── Real Texture Clipping ───────────────────────────────────────────────


def _get_texture_svg_files():
    if not os.path.isdir(TEXTURES_DIR):
        return []
    return sorted(f for f in os.listdir(TEXTURES_DIR) if f.endswith(".svg"))


@pytest.mark.parametrize("filename", _get_texture_svg_files())
class TestRealTextureClipping:
    """Ensure clipping works on all real texture SVGs."""

    def test_clipped_coords_within_viewbox(self, filename):
        from svg_to_tex.svg_parser import parse_svg
        from svg_to_tex.stroke_outliner import stroke_to_outlines
        svg_path = os.path.join(TEXTURES_DIR, filename)
        with open(svg_path) as f:
            svg_content = f.read()
        viewbox, paths = parse_svg(svg_content, include_strokes=True)
        paths = stroke_to_outlines(paths)
        clipped = clip_paths_to_viewbox(paths, viewbox)

        min_x, min_y, w, h = viewbox
        max_x, max_y = min_x + w, min_y + h
        for path in clipped:
            for cmd, params in path["commands"]:
                if cmd in ("M", "L"):
                    assert params[0] >= min_x - 0.5, \
                        f"{filename}: x={params[0]:.2f} < {min_x}"
                    assert params[0] <= max_x + 0.5, \
                        f"{filename}: x={params[0]:.2f} > {max_x}"
                    assert params[1] >= min_y - 0.5, \
                        f"{filename}: y={params[1]:.2f} < {min_y}"
                    assert params[1] <= max_y + 0.5, \
                        f"{filename}: y={params[1]:.2f} > {max_y}"

    def test_clipped_produces_paths(self, filename):
        from svg_to_tex.svg_parser import parse_svg
        from svg_to_tex.stroke_outliner import stroke_to_outlines
        svg_path = os.path.join(TEXTURES_DIR, filename)
        with open(svg_path) as f:
            svg_content = f.read()
        viewbox, paths = parse_svg(svg_content, include_strokes=True)
        paths = stroke_to_outlines(paths)
        clipped = clip_paths_to_viewbox(paths, viewbox)
        assert len(clipped) >= 1, f"{filename}: clipping removed all paths"
