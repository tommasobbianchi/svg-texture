"""Tests for SVG shape to path conversion."""

import pytest
from svg_to_tex.shapes import (
    rect_to_path, circle_to_path, ellipse_to_path,
    polygon_to_path, polyline_to_path, shape_to_path_d,
)
from svg_to_tex.path_parser import parse_path


class TestRect:
    def test_simple_rect(self):
        d = rect_to_path(0, 0, 100, 50)
        cmds = parse_path(d)
        assert cmds[0][0] == "M"
        # Should have 4 lines and a Z
        assert any(c == "Z" for c, _ in cmds)

    def test_rounded_rect(self):
        d = rect_to_path(0, 0, 100, 50, rx=10, ry=10)
        cmds = parse_path(d)
        # Should contain arcs for corners
        assert any(c == "A" for c, _ in cmds)

    def test_zero_size(self):
        d = rect_to_path(0, 0, 0, 50)
        assert d == ""

    def test_rx_only(self):
        """rx without ry should set ry = rx"""
        d = rect_to_path(0, 0, 100, 50, rx=10)
        cmds = parse_path(d)
        assert any(c == "A" for c, _ in cmds)


class TestCircle:
    def test_simple_circle(self):
        d = circle_to_path(50, 50, 25)
        cmds = parse_path(d)
        assert cmds[0][0] == "M"
        assert any(c == "A" for c, _ in cmds)

    def test_zero_radius(self):
        d = circle_to_path(50, 50, 0)
        assert d == ""


class TestEllipse:
    def test_simple_ellipse(self):
        d = ellipse_to_path(50, 50, 30, 20)
        cmds = parse_path(d)
        assert cmds[0][0] == "M"
        assert any(c == "A" for c, _ in cmds)


class TestPolygon:
    def test_triangle(self):
        d = polygon_to_path("0,0 10,0 5,10")
        cmds = parse_path(d)
        assert cmds[0] == ("M", [0, 0])
        assert cmds[-1] == ("Z", [])

    def test_empty(self):
        d = polygon_to_path("")
        assert d == ""


class TestPolyline:
    def test_simple(self):
        d = polyline_to_path("0,0 10,10 20,0")
        cmds = parse_path(d)
        assert len(cmds) == 3
        assert cmds[0][0] == "M"
        # Polyline should NOT close
        assert all(c != "Z" for c, _ in cmds)


class TestShapeToPathD:
    def test_rect(self):
        d = shape_to_path_d("rect", {"x": "10", "y": "20", "width": "100", "height": "50"})
        assert "M" in d

    def test_circle(self):
        d = shape_to_path_d("circle", {"cx": "50", "cy": "50", "r": "25"})
        assert "M" in d

    def test_unknown_shape(self):
        d = shape_to_path_d("text", {"x": "0", "y": "0"})
        assert d == ""
