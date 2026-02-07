"""Tests for SVG path d-attribute tokenizer."""

import pytest
from svg_to_tex.path_parser import parse_path, tokenize_numbers


class TestTokenizeNumbers:
    def test_simple_integers(self):
        assert tokenize_numbers("10 20 30") == [10.0, 20.0, 30.0]

    def test_comma_separated(self):
        assert tokenize_numbers("10,20,30") == [10.0, 20.0, 30.0]

    def test_sign_as_separator(self):
        assert tokenize_numbers("10-5") == [10.0, -5.0]

    def test_double_decimal(self):
        assert tokenize_numbers("1.2.3") == [1.2, 0.3]

    def test_negative_numbers(self):
        assert tokenize_numbers("-10 -20") == [-10.0, -20.0]

    def test_positive_sign(self):
        assert tokenize_numbers("+10+20") == [10.0, 20.0]

    def test_mixed_separators(self):
        assert tokenize_numbers("10,20 30-40") == [10.0, 20.0, 30.0, -40.0]

    def test_decimals_only(self):
        assert tokenize_numbers(".5 .3") == [0.5, 0.3]

    def test_empty(self):
        assert tokenize_numbers("") == []


class TestParsePath:
    def test_simple_move_line(self):
        result = parse_path("M 0,0 L 10,10")
        assert result == [("M", [0, 0]), ("L", [10, 10])]

    def test_implicit_lineto(self):
        """M followed by coords becomes L"""
        result = parse_path("M 0,0 10,10 20,20")
        assert result == [("M", [0, 0]), ("L", [10, 10]), ("L", [20, 20])]

    def test_close_path(self):
        result = parse_path("M 0,0 L 10,0 L 10,10 Z")
        assert len(result) == 4
        assert result[-1] == ("Z", [])

    def test_relative_commands(self):
        result = parse_path("m 0,0 l 10,10")
        assert result == [("m", [0, 0]), ("l", [10, 10])]

    def test_cubic_bezier(self):
        result = parse_path("M 0,0 C 10,0 20,10 30,10")
        assert result == [
            ("M", [0, 0]),
            ("C", [10, 0, 20, 10, 30, 10]),
        ]

    def test_arc_command(self):
        result = parse_path("M 0,0 A 10,10 0 0 1 20,20")
        assert len(result) == 2
        assert result[1][0] == "A"
        assert result[1][1] == [10, 10, 0, 0, 1, 20, 20]

    def test_multiple_subpaths(self):
        result = parse_path("M 0,0 L 10,0 Z M 20,20 L 30,20 Z")
        assert len(result) == 6

    def test_no_spaces(self):
        result = parse_path("M0,0L10,10")
        assert result == [("M", [0, 0]), ("L", [10, 10])]

    def test_horizontal_vertical(self):
        result = parse_path("M 0,0 H 10 V 20")
        assert result == [("M", [0, 0]), ("H", [10]), ("V", [20])]

    def test_smooth_cubic(self):
        result = parse_path("M 0,0 C 10,0 20,10 30,10 S 50,10 60,0")
        assert len(result) == 3
        assert result[2][0] == "S"

    def test_quadratic(self):
        result = parse_path("M 0,0 Q 10,20 20,0")
        assert result == [("M", [0, 0]), ("Q", [10, 20, 20, 0])]

    def test_smooth_quadratic(self):
        result = parse_path("M 0,0 Q 10,20 20,0 T 40,0")
        assert len(result) == 3
        assert result[2][0] == "T"

    def test_empty_path(self):
        assert parse_path("") == []

    def test_complex_path(self):
        """Test a more realistic SVG path."""
        d = "M 10,80 C 40,10 65,10 95,80 S 150,150 180,80"
        result = parse_path(d)
        assert len(result) == 3
        assert result[0] == ("M", [10, 80])
        assert result[1][0] == "C"
        assert result[2][0] == "S"
