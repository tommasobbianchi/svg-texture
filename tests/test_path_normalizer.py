"""Tests for path command normalization."""

import pytest
import math
from svg_to_tex.path_parser import parse_path
from svg_to_tex.path_normalizer import normalize_commands


def _normalize(d: str):
    """Helper to parse and normalize a path d-string."""
    return normalize_commands(parse_path(d))


class TestRelativeToAbsolute:
    def test_relative_move_line(self):
        result = _normalize("m 10,20 l 5,5")
        assert result[0] == ("M", [10, 20])
        assert result[1] == ("L", [15, 25])

    def test_relative_horizontal(self):
        result = _normalize("M 0,0 h 10")
        assert result[1] == ("L", [10, 0])

    def test_relative_vertical(self):
        result = _normalize("M 0,0 v 20")
        assert result[1] == ("L", [0, 20])


class TestHVToL:
    def test_absolute_h(self):
        result = _normalize("M 5,10 H 20")
        assert result[1] == ("L", [20, 10])

    def test_absolute_v(self):
        result = _normalize("M 5,10 V 30")
        assert result[1] == ("L", [5, 30])


class TestSmoothCubic:
    def test_s_after_c(self):
        result = _normalize("M 0,0 C 10,0 20,10 30,10 S 50,10 60,0")
        assert len(result) == 3
        # S should become C with reflected control point
        assert result[2][0] == "C"
        # First control point of S is reflection of second CP of previous C
        # Previous CP2 was (20,10), current point is (30,10)
        # Reflected: (2*30-20, 2*10-10) = (40, 10)
        assert result[2][1][0] == pytest.approx(40, abs=0.01)
        assert result[2][1][1] == pytest.approx(10, abs=0.01)

    def test_s_without_preceding_c(self):
        result = _normalize("M 10,10 S 50,10 60,0")
        assert result[1][0] == "C"
        # Without preceding C, first CP equals current point
        assert result[1][1][0] == pytest.approx(10, abs=0.01)
        assert result[1][1][1] == pytest.approx(10, abs=0.01)


class TestQuadraticToCubic:
    def test_q_to_c(self):
        result = _normalize("M 0,0 Q 10,20 20,0")
        assert len(result) == 2
        assert result[1][0] == "C"
        # C1 = P0 + 2/3*(Q1-P0) = (0,0) + 2/3*(10,20) = (6.67, 13.33)
        assert result[1][1][0] == pytest.approx(6.667, abs=0.01)
        assert result[1][1][1] == pytest.approx(13.333, abs=0.01)
        # C2 = P2 + 2/3*(Q1-P2) = (20,0) + 2/3*(-10,20) = (13.33, 13.33)
        assert result[1][1][2] == pytest.approx(13.333, abs=0.01)
        assert result[1][1][3] == pytest.approx(13.333, abs=0.01)

    def test_t_after_q(self):
        result = _normalize("M 0,0 Q 10,20 20,0 T 40,0")
        assert len(result) == 3
        assert result[2][0] == "C"


class TestCloseAndMove:
    def test_z_resets_position(self):
        result = _normalize("M 0,0 L 10,10 L 10,0 Z L 5,5")
        # After Z, current point goes back to (0,0)
        assert result[-1] == ("L", [5, 5])

    def test_z_output(self):
        result = _normalize("M 0,0 L 10,0 Z")
        assert result[-1] == ("Z", [])


class TestArc:
    def test_circular_arc(self):
        result = _normalize("M 0,0 A 10,10 0 0 1 20,0")
        # Should produce an A (circular) command
        has_arc = any(cmd == "A" for cmd, _ in result)
        assert has_arc

    def test_elliptical_arc(self):
        result = _normalize("M 0,0 A 10,20 0 0 1 20,0")
        # Elliptical arcs become cubic beziers
        has_cubic = any(cmd == "C" for cmd, _ in result)
        assert has_cubic

    def test_degenerate_arc(self):
        # Same start and end point
        result = _normalize("M 10,10 A 0,0 0 0 0 10,10")
        # Should produce a line or be skipped
        assert len(result) >= 1
