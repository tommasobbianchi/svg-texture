"""Tests for 2D affine transform operations."""

import pytest
import math
from svg_to_tex.transform import (
    identity, multiply, apply_to_point, parse_transform,
    make_translate, make_scale, make_rotate,
)


class TestIdentity:
    def test_identity_point(self):
        m = identity()
        x, y = apply_to_point(m, 10, 20)
        assert x == pytest.approx(10)
        assert y == pytest.approx(20)


class TestTranslate:
    def test_translate(self):
        m = make_translate(5, 10)
        x, y = apply_to_point(m, 0, 0)
        assert x == pytest.approx(5)
        assert y == pytest.approx(10)

    def test_translate_point(self):
        m = make_translate(5, 10)
        x, y = apply_to_point(m, 3, 4)
        assert x == pytest.approx(8)
        assert y == pytest.approx(14)


class TestScale:
    def test_uniform_scale(self):
        m = make_scale(2)
        x, y = apply_to_point(m, 5, 10)
        assert x == pytest.approx(10)
        assert y == pytest.approx(20)

    def test_non_uniform_scale(self):
        m = make_scale(2, 3)
        x, y = apply_to_point(m, 5, 10)
        assert x == pytest.approx(10)
        assert y == pytest.approx(30)


class TestRotate:
    def test_rotate_90(self):
        m = make_rotate(90)
        x, y = apply_to_point(m, 10, 0)
        assert x == pytest.approx(0, abs=1e-10)
        assert y == pytest.approx(10, abs=1e-10)

    def test_rotate_around_point(self):
        m = make_rotate(180, 5, 0)
        x, y = apply_to_point(m, 10, 0)
        assert x == pytest.approx(0, abs=1e-10)
        assert y == pytest.approx(0, abs=1e-10)


class TestComposition:
    def test_translate_then_scale(self):
        t = make_translate(10, 0)
        s = make_scale(2)
        m = multiply(s, t)  # Scale applied to translated point
        x, y = apply_to_point(m, 0, 0)
        assert x == pytest.approx(20)

    def test_scale_then_translate(self):
        s = make_scale(2)
        t = make_translate(10, 0)
        m = multiply(t, s)  # Translate applied after scale
        x, y = apply_to_point(m, 5, 0)
        assert x == pytest.approx(20)  # 5*2 + 10


class TestParseTransform:
    def test_translate(self):
        m = parse_transform("translate(10, 20)")
        x, y = apply_to_point(m, 0, 0)
        assert x == pytest.approx(10)
        assert y == pytest.approx(20)

    def test_scale(self):
        m = parse_transform("scale(2)")
        x, y = apply_to_point(m, 5, 10)
        assert x == pytest.approx(10)
        assert y == pytest.approx(20)

    def test_rotate(self):
        m = parse_transform("rotate(90)")
        x, y = apply_to_point(m, 10, 0)
        assert x == pytest.approx(0, abs=1e-10)
        assert y == pytest.approx(10, abs=1e-10)

    def test_matrix(self):
        m = parse_transform("matrix(2, 0, 0, 2, 10, 20)")
        x, y = apply_to_point(m, 5, 5)
        assert x == pytest.approx(20)  # 2*5 + 0*5 + 10
        assert y == pytest.approx(30)  # 0*5 + 2*5 + 20

    def test_multiple_transforms(self):
        m = parse_transform("translate(10,0) scale(2)")
        # SVG composition: translate(10,0) * scale(2), so point is scaled first then translated
        x, y = apply_to_point(m, 5, 0)
        # scale(2) * 5 = 10, then translate +10 = 20
        assert x == pytest.approx(20)

    def test_empty(self):
        m = parse_transform("")
        assert m == identity()

    def test_skewx(self):
        m = parse_transform("skewX(45)")
        x, y = apply_to_point(m, 0, 10)
        assert x == pytest.approx(10, abs=0.01)
        assert y == pytest.approx(10)

    def test_translate_single_arg(self):
        m = parse_transform("translate(10)")
        x, y = apply_to_point(m, 0, 0)
        assert x == pytest.approx(10)
        assert y == pytest.approx(0)
