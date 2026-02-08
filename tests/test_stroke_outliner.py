"""Tests for stroke-to-outline conversion."""

import math
import pytest
from svg_to_tex.stroke_outliner import (
    flatten_cubic,
    flatten_arc,
    split_subpaths,
    offset_segment,
    line_intersection,
    offset_polyline,
    outline_open_subpath,
    outline_closed_subpath,
    stroke_to_outlines,
)


class TestFlattenCubic:
    def test_straight_line_cubic(self):
        pts = flatten_cubic(0, 0, 10, 0, 20, 0, 30, 0, num_segments=4)
        assert len(pts) == 4
        for x, y in pts:
            assert y == pytest.approx(0, abs=1e-6)
        assert pts[-1][0] == pytest.approx(30, abs=1e-6)

    def test_curved_cubic(self):
        pts = flatten_cubic(0, 0, 0, 10, 10, 10, 10, 0, num_segments=8)
        assert len(pts) == 8
        mid = pts[3]
        assert mid[1] > 0

    def test_single_segment(self):
        pts = flatten_cubic(0, 0, 5, 5, 10, 5, 15, 0, num_segments=1)
        assert len(pts) == 1
        assert pts[0] == pytest.approx((15, 0), abs=1e-6)

    def test_endpoint_accuracy(self):
        pts = flatten_cubic(1, 2, 3, 4, 5, 6, 7, 8, num_segments=16)
        assert pts[-1][0] == pytest.approx(7, abs=1e-6)
        assert pts[-1][1] == pytest.approx(8, abs=1e-6)


class TestFlattenArc:
    def test_quarter_circle(self):
        pts = flatten_arc(0, 0, 10, 0, 90, num_segments=8)
        assert len(pts) == 8
        assert pts[-1][0] == pytest.approx(0, abs=0.01)
        assert pts[-1][1] == pytest.approx(10, abs=0.01)

    def test_full_circle(self):
        pts = flatten_arc(0, 0, 5, 0, 360, num_segments=16)
        assert len(pts) == 16
        assert pts[-1][0] == pytest.approx(5, abs=0.01)
        assert pts[-1][1] == pytest.approx(0, abs=0.1)

    def test_negative_sweep(self):
        pts = flatten_arc(0, 0, 10, 90, -90, num_segments=4)
        assert len(pts) == 4
        assert pts[-1][0] == pytest.approx(10, abs=0.01)
        assert pts[-1][1] == pytest.approx(0, abs=0.01)

    def test_semicircle(self):
        pts = flatten_arc(0, 0, 5, 0, 180, num_segments=8)
        assert pts[-1][0] == pytest.approx(-5, abs=0.01)
        assert pts[-1][1] == pytest.approx(0, abs=0.1)


class TestSplitSubpaths:
    def test_single_open_subpath(self):
        cmds = [("M", [0, 0]), ("L", [10, 0]), ("L", [10, 10])]
        result = split_subpaths(cmds)
        assert len(result) == 1
        points, is_closed = result[0]
        assert len(points) == 3
        assert is_closed is False

    def test_single_closed_subpath(self):
        cmds = [("M", [0, 0]), ("L", [10, 0]), ("L", [10, 10]), ("Z", [])]
        result = split_subpaths(cmds)
        assert len(result) == 1
        points, is_closed = result[0]
        assert is_closed is True
        assert points[-1] == pytest.approx(points[0], abs=1e-6)

    def test_multiple_subpaths(self):
        cmds = [
            ("M", [0, 0]), ("L", [10, 0]),
            ("M", [20, 0]), ("L", [30, 0]),
        ]
        result = split_subpaths(cmds)
        assert len(result) == 2

    def test_cubic_flattened(self):
        cmds = [("M", [0, 0]), ("C", [0, 10, 10, 10, 10, 0])]
        result = split_subpaths(cmds)
        assert len(result) == 1
        points, _ = result[0]
        assert len(points) > 2

    def test_arc_flattened(self):
        cmds = [("M", [10, 0]), ("A", [0, 0, 10, 0, 90])]
        result = split_subpaths(cmds)
        assert len(result) == 1
        points, _ = result[0]
        assert len(points) > 2

    def test_empty_commands(self):
        result = split_subpaths([])
        assert len(result) == 0

    def test_single_point_discarded(self):
        cmds = [("M", [5, 5])]
        result = split_subpaths(cmds)
        assert len(result) == 0


class TestOffsetSegment:
    def test_horizontal_right_positive_offset(self):
        # For rightward segment, positive offset goes down in SVG coords (y-down)
        # Normal of (1,0) is (0,1) in our convention: (-dy, dx)/len
        q0, q1 = offset_segment((0, 0), (10, 0), 5)
        assert abs(q0[1]) == pytest.approx(5, abs=1e-6)
        assert abs(q1[1]) == pytest.approx(5, abs=1e-6)
        assert q0[0] == pytest.approx(0, abs=1e-6)
        assert q1[0] == pytest.approx(10, abs=1e-6)

    def test_opposite_offsets(self):
        # Positive and negative offsets should go to opposite sides
        q0_pos, q1_pos = offset_segment((0, 0), (10, 0), 5)
        q0_neg, q1_neg = offset_segment((0, 0), (10, 0), -5)
        assert q0_pos[1] == pytest.approx(-q0_neg[1], abs=1e-6)
        assert q1_pos[1] == pytest.approx(-q1_neg[1], abs=1e-6)

    def test_zero_length_segment(self):
        q0, q1 = offset_segment((5, 5), (5, 5), 3)
        assert q0 == (5, 5)
        assert q1 == (5, 5)

    def test_offset_distance(self):
        # Offset should be exactly the specified distance from the original
        q0, q1 = offset_segment((0, 0), (10, 0), 5)
        assert abs(q0[1]) == pytest.approx(5, abs=1e-6)
        assert abs(q1[1]) == pytest.approx(5, abs=1e-6)


class TestLineIntersection:
    def test_perpendicular_lines(self):
        pt = line_intersection((0, 5), (10, 5), (3, 0), (3, 10))
        assert pt[0] == pytest.approx(3, abs=1e-6)
        assert pt[1] == pytest.approx(5, abs=1e-6)

    def test_parallel_lines(self):
        pt = line_intersection((0, 0), (10, 0), (0, 5), (10, 5))
        assert pt[1] == pytest.approx(2.5, abs=1e-6)

    def test_angled_lines(self):
        pt = line_intersection((0, 0), (10, 10), (0, 10), (10, 0))
        assert pt[0] == pytest.approx(5, abs=1e-6)
        assert pt[1] == pytest.approx(5, abs=1e-6)


class TestOffsetPolyline:
    def test_two_point_line(self):
        result = offset_polyline([(0, 0), (10, 0)], 2.0)
        assert len(result) == 2
        # Both points offset by same amount
        assert result[0][1] == result[1][1]
        assert abs(result[0][1]) == pytest.approx(2.0, abs=1e-6)

    def test_right_angle(self):
        pts = [(0, 0), (10, 0), (10, -10)]
        result = offset_polyline(pts, 1.0)
        assert len(result) == 3
        assert abs(result[0][1]) == pytest.approx(1.0, abs=1e-6)

    def test_miter_limit_bevel(self):
        # Very sharp angle should trigger bevel
        pts = [(0, 0), (10, 0), (10.01, 10)]
        result = offset_polyline(pts, 2.0, miter_limit=2.0)
        assert len(result) >= 3

    def test_single_point(self):
        result = offset_polyline([(5, 5)], 1.0)
        assert len(result) == 1


class TestOutlineOpenSubpath:
    def test_horizontal_line_outline(self):
        points = [(0, 0), (10, 0)]
        cmds = outline_open_subpath(points, 1.0)
        assert len(cmds) > 0
        assert cmds[0][0] == "M"
        assert cmds[-1][0] == "Z"
        for cmd, _ in cmds:
            assert cmd in ("M", "L", "Z")

    def test_outline_width(self):
        points = [(0, 0), (20, 0)]
        cmds = outline_open_subpath(points, 2.0)
        ys = [p[1] for _, p in cmds if len(p) >= 2]
        min_y = min(ys)
        max_y = max(ys)
        assert max_y - min_y == pytest.approx(4.0, abs=0.1)

    def test_single_segment_closed(self):
        points = [(5, 5), (15, 5)]
        cmds = outline_open_subpath(points, 1.5)
        z_count = sum(1 for cmd, _ in cmds if cmd == "Z")
        assert z_count == 1

    def test_too_few_points(self):
        cmds = outline_open_subpath([(0, 0)], 1.0)
        assert cmds == []


class TestOutlineClosedSubpath:
    def test_triangle_outline(self):
        points = [(0, 0), (10, 0), (5, 10), (0, 0)]
        cmds = outline_closed_subpath(points, 1.0)
        assert len(cmds) > 0
        z_count = sum(1 for cmd, _ in cmds if cmd == "Z")
        assert z_count == 2

    def test_square_outline(self):
        points = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        cmds = outline_closed_subpath(points, 0.5)
        z_count = sum(1 for cmd, _ in cmds if cmd == "Z")
        assert z_count == 2
        for cmd, _ in cmds:
            assert cmd in ("M", "L", "Z")

    def test_degenerate_two_points(self):
        points = [(0, 0), (10, 0)]
        cmds = outline_closed_subpath(points, 1.0)
        # Should fall back to open subpath outline
        assert len(cmds) > 0


class TestStrokeToOutlines:
    def test_passthrough_filled_paths(self):
        paths = [{"commands": [("M", [0, 0]), ("L", [10, 0]), ("Z", [])], "fill_rule": "nonzero"}]
        result = stroke_to_outlines(paths)
        assert result == paths

    def test_basic_stroke_conversion(self):
        paths = [{
            "commands": [("M", [0, 0]), ("L", [10, 0])],
            "fill_rule": "nonzero",
            "source": "stroke",
            "stroke_width": 2.0,
        }]
        result = stroke_to_outlines(paths)
        assert len(result) == 1
        assert "source" not in result[0]
        assert result[0]["commands"][0][0] == "M"
        assert result[0]["commands"][-1][0] == "Z"

    def test_stroke_width_override(self):
        paths = [{
            "commands": [("M", [0, 0]), ("L", [20, 0])],
            "fill_rule": "nonzero",
            "source": "stroke",
            "stroke_width": 1.0,
        }]
        result_default = stroke_to_outlines(paths)
        result_override = stroke_to_outlines(paths, stroke_width_override=4.0)
        ys_default = [p[1] for _, p in result_default[0]["commands"] if len(p) >= 2]
        ys_override = [p[1] for _, p in result_override[0]["commands"] if len(p) >= 2]
        height_default = max(ys_default) - min(ys_default)
        height_override = max(ys_override) - min(ys_override)
        assert height_override > height_default

    def test_closed_stroke_uses_evenodd(self):
        paths = [{
            "commands": [("M", [0, 0]), ("L", [10, 0]), ("L", [10, 10]), ("Z", [])],
            "fill_rule": "nonzero",
            "source": "stroke",
            "stroke_width": 2.0,
        }]
        result = stroke_to_outlines(paths)
        assert len(result) >= 1
        assert result[0]["fill_rule"] == "evenodd"

    def test_zero_width_stroke_skipped(self):
        paths = [{
            "commands": [("M", [0, 0]), ("L", [10, 0])],
            "fill_rule": "nonzero",
            "source": "stroke",
            "stroke_width": 0.0,
        }]
        result = stroke_to_outlines(paths)
        assert len(result) == 0

    def test_mixed_fill_and_stroke(self):
        paths = [
            {"commands": [("M", [0, 0]), ("L", [10, 0]), ("Z", [])], "fill_rule": "nonzero"},
            {
                "commands": [("M", [20, 0]), ("L", [30, 0])],
                "fill_rule": "nonzero",
                "source": "stroke",
                "stroke_width": 1.0,
            },
        ]
        result = stroke_to_outlines(paths)
        assert len(result) == 2
        assert result[0]["commands"] == paths[0]["commands"]
