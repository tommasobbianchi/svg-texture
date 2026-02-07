"""Tests for arc endpoint-to-center conversion and bezier approximation."""

import pytest
import math
from svg_to_tex.arc_converter import (
    endpoint_to_center, arc_to_beziers, is_circular, arc_to_center_param,
)


class TestEndpointToCenter:
    def test_semicircle(self):
        """A semicircular arc from (-10,0) to (10,0)."""
        cx, cy, rx, ry, theta1, dtheta, phi = endpoint_to_center(
            -10, 0, 10, 10, 0, 0, 1, 10, 0
        )
        assert cx == pytest.approx(0, abs=0.1)
        assert cy == pytest.approx(0, abs=0.1)
        assert rx == pytest.approx(10, abs=0.1)

    def test_same_point(self):
        """Degenerate: start == end."""
        result = endpoint_to_center(10, 10, 5, 5, 0, 0, 1, 10, 10)
        assert result[2] == 0  # rx = 0 (degenerate)

    def test_zero_radius(self):
        """Degenerate: zero radius."""
        result = endpoint_to_center(0, 0, 0, 0, 0, 0, 1, 10, 10)
        assert result[2] == 0

    def test_large_arc_flag(self):
        """Large arc flag should select the larger arc."""
        # Use points that aren't diametrically opposite (non-ambiguous case)
        # Small arc: from (0,-10) to (10,0) with r=10
        _, _, _, _, _, dtheta_small, _ = endpoint_to_center(
            0, -10, 10, 10, 0, 0, 1, 10, 0
        )
        # Large arc: same endpoints, large-arc flag set
        _, _, _, _, _, dtheta_large, _ = endpoint_to_center(
            0, -10, 10, 10, 0, 1, 1, 10, 0
        )
        assert abs(dtheta_large) > abs(dtheta_small)


class TestIsCircular:
    def test_circular(self):
        assert is_circular(10, 10, 0) is True

    def test_nearly_circular(self):
        assert is_circular(10, 10.05, 0) is True

    def test_elliptical(self):
        assert is_circular(10, 20, 0) is False


class TestArcToBeziers:
    def test_quarter_circle(self):
        """Quarter circle should produce 1 bezier segment."""
        result = arc_to_beziers(0, 0, 10, 10, 0, 90, 0)
        assert len(result) == 1
        assert result[0][0] == "C"

    def test_full_circle(self):
        """Full circle should produce 4 bezier segments."""
        result = arc_to_beziers(0, 0, 10, 10, 0, 360, 0)
        assert len(result) == 4

    def test_semicircle(self):
        """Semicircle should produce 2 bezier segments."""
        result = arc_to_beziers(0, 0, 10, 10, 0, 180, 0)
        assert len(result) == 2

    def test_bezier_endpoint_accuracy(self):
        """End point of bezier approximation should be close to true arc endpoint."""
        r = 10
        result = arc_to_beziers(0, 0, r, r, 0, 90, 0)
        # End point should be at (0, 10) for 90deg arc starting at 0deg
        last_cmd = result[-1]
        end_x = last_cmd[1][4]
        end_y = last_cmd[1][5]
        expected_x = r * math.cos(math.radians(90))
        expected_y = r * math.sin(math.radians(90))
        assert end_x == pytest.approx(expected_x, abs=0.01)
        assert end_y == pytest.approx(expected_y, abs=0.01)


class TestArcToCenterParam:
    def test_circular_returns_arc(self):
        result = arc_to_center_param(0, 0, 10, 10, 0, 0, 1, 20, 0)
        # Should return A command for circular arc
        assert any(cmd == "A" for cmd, _ in result)

    def test_elliptical_returns_beziers(self):
        result = arc_to_center_param(0, 0, 10, 20, 0, 0, 1, 20, 0)
        # Should return C commands for elliptical arc
        assert all(cmd in ("C", "L") for cmd, _ in result)
