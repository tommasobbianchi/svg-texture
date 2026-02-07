"""Tests for SVGTEX encoder."""

import pytest
from svg_to_tex.encoder import encode_viewbox, encode_commands, encode_path, encode_svgtex


class TestEncodeViewbox:
    def test_simple(self):
        assert encode_viewbox(0, 0, 100, 100) == "V0,0,100,100"

    def test_with_decimals(self):
        assert encode_viewbox(0.5, 1.5, 200, 300) == "V0.5,1.5,200,300"

    def test_negative_zero(self):
        result = encode_viewbox(-0.0, 0.0, 100, 100)
        assert result == "V0,0,100,100"


class TestEncodeCommands:
    def test_move_line(self):
        cmds = [("M", [0, 0]), ("L", [10, 20])]
        assert encode_commands(cmds) == "M0,0 L10,20"

    def test_cubic(self):
        cmds = [("C", [1, 2, 3, 4, 5, 6])]
        assert encode_commands(cmds) == "C1,2,3,4,5,6"

    def test_arc(self):
        cmds = [("A", [5, 5, 10, 0, 90])]
        assert encode_commands(cmds) == "A5,5,10,0,90"

    def test_close(self):
        cmds = [("Z", [])]
        assert encode_commands(cmds) == "Z"

    def test_precision(self):
        cmds = [("L", [1.23456, 7.89012])]
        assert encode_commands(cmds, precision=2) == "L1.23,7.89"
        assert encode_commands(cmds, precision=1) == "L1.2,7.9"

    def test_trailing_zeros_stripped(self):
        cmds = [("L", [10.0, 20.0])]
        assert encode_commands(cmds) == "L10,20"


class TestEncodePath:
    def test_nonzero_fill(self):
        cmds = [("M", [0, 0]), ("L", [10, 0]), ("Z", [])]
        result = encode_path(cmds, "nonzero")
        assert result.startswith("N")

    def test_evenodd_fill(self):
        cmds = [("M", [0, 0]), ("L", [10, 0]), ("Z", [])]
        result = encode_path(cmds, "evenodd")
        assert result.startswith("E")


class TestEncodeSvgtex:
    def test_complete_output(self):
        viewbox = (0, 0, 100, 100)
        paths = [
            {
                "commands": [("M", [0, 0]), ("L", [100, 0]), ("L", [100, 100]), ("Z", [])],
                "fill_rule": "nonzero",
            }
        ]
        result = encode_svgtex(viewbox, paths)
        lines = result.strip().split("|")
        assert lines[0] == "V0,0,100,100"
        assert lines[1].startswith("N")

    def test_no_angle_brackets(self):
        """SVGTEX should never contain angle brackets (Onshape strips them)."""
        viewbox = (0, 0, 100, 100)
        paths = [
            {
                "commands": [("M", [0, 0]), ("L", [100, 0]), ("Z", [])],
                "fill_rule": "nonzero",
            }
        ]
        result = encode_svgtex(viewbox, paths)
        assert "<" not in result
        assert ">" not in result

    def test_no_quotes(self):
        """SVGTEX should not contain quotes."""
        viewbox = (0, 0, 100, 100)
        paths = [{"commands": [("M", [0, 0]), ("Z", [])], "fill_rule": "nonzero"}]
        result = encode_svgtex(viewbox, paths)
        assert '"' not in result
        assert "'" not in result
