"""Tests for SVGTEX format contract between Python encoder and FeatureScript parser.

Uses the decoder (which mirrors FeatureScript's parseSvgTex) to validate that
encoded SVGTEX strings can be correctly parsed back into equivalent structures.
"""

import os
import math
import pytest
from svg_to_tex.encoder import (
    encode_viewbox, encode_commands, encode_path, encode_svgtex, _fmt,
)
from svg_to_tex.decoder import (
    decode_viewbox, decode_commands, decode_path, decode_svgtex,
    estimate_entity_count, SvgtexDecodeError,
)
from svg_to_tex.region_analyzer import estimate_entity_count as encoder_entity_count


TEXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "textures")


# ─── ViewBox ────────────────────────────────────────────────────────────────


class TestViewboxRoundtrip:
    def test_simple_integer(self):
        encoded = encode_viewbox(0, 0, 100, 100)
        vb = decode_viewbox(encoded)
        assert vb == (0, 0, 100, 100)

    def test_negative_coords(self):
        encoded = encode_viewbox(-10, -20, 200, 300)
        vb = decode_viewbox(encoded)
        assert vb == (-10, -20, 200, 300)

    def test_decimal_values(self):
        encoded = encode_viewbox(0.5, 1.25, 99.75, 50.5)
        vb = decode_viewbox(encoded)
        assert vb == (0.5, 1.25, 99.75, 50.5)

    def test_negative_zero_normalized(self):
        encoded = encode_viewbox(-0.0, 0.0, 100, 100)
        vb = decode_viewbox(encoded)
        assert vb == (0, 0, 100, 100)

    def test_large_values(self):
        encoded = encode_viewbox(0, 0, 10000, 10000)
        vb = decode_viewbox(encoded)
        assert vb == (0, 0, 10000, 10000)

    def test_small_fractional(self):
        encoded = encode_viewbox(0.01, 0.02, 0.99, 0.98, precision=4)
        vb = decode_viewbox(encoded)
        assert vb == (0.01, 0.02, 0.99, 0.98)


class TestViewboxDecodeErrors:
    def test_missing_prefix(self):
        with pytest.raises(SvgtexDecodeError, match="must start with 'V'"):
            decode_viewbox("0,0,100,100")

    def test_wrong_prefix(self):
        with pytest.raises(SvgtexDecodeError, match="must start with 'V'"):
            decode_viewbox("X0,0,100,100")

    def test_too_few_values(self):
        with pytest.raises(SvgtexDecodeError, match="4 comma-separated"):
            decode_viewbox("V0,0,100")

    def test_too_many_values(self):
        with pytest.raises(SvgtexDecodeError, match="4 comma-separated"):
            decode_viewbox("V0,0,100,100,50")

    def test_non_numeric(self):
        with pytest.raises(SvgtexDecodeError, match="Invalid viewbox number"):
            decode_viewbox("V0,abc,100,100")


# ─── Commands ───────────────────────────────────────────────────────────────


class TestCommandRoundtrip:
    def test_move(self):
        original = [("M", [10.5, 20.3])]
        encoded = encode_commands(original)
        decoded = decode_commands(encoded)
        assert len(decoded) == 1
        assert decoded[0][0] == "M"
        assert decoded[0][1] == pytest.approx([10.5, 20.3], abs=0.01)

    def test_line(self):
        original = [("L", [50, 75])]
        encoded = encode_commands(original)
        decoded = decode_commands(encoded)
        assert decoded[0] == ("L", [50.0, 75.0])

    def test_cubic_bezier(self):
        original = [("C", [1.5, 2.5, 3.5, 4.5, 5.5, 6.5])]
        encoded = encode_commands(original)
        decoded = decode_commands(encoded)
        assert decoded[0][0] == "C"
        assert decoded[0][1] == pytest.approx([1.5, 2.5, 3.5, 4.5, 5.5, 6.5], abs=0.01)

    def test_arc(self):
        original = [("A", [50, 50, 25, 0, 360])]
        encoded = encode_commands(original)
        decoded = decode_commands(encoded)
        assert decoded[0][0] == "A"
        assert decoded[0][1] == pytest.approx([50, 50, 25, 0, 360], abs=0.01)

    def test_close(self):
        original = [("Z", [])]
        encoded = encode_commands(original)
        decoded = decode_commands(encoded)
        assert decoded == [("Z", [])]

    def test_mixed_sequence(self):
        original = [
            ("M", [0, 0]),
            ("L", [100, 0]),
            ("C", [100, 50, 50, 100, 0, 100]),
            ("A", [50, 50, 30, 90, 270]),
            ("Z", []),
        ]
        encoded = encode_commands(original)
        decoded = decode_commands(encoded)
        assert len(decoded) == 5
        assert [c[0] for c in decoded] == ["M", "L", "C", "A", "Z"]

    def test_negative_coords(self):
        original = [("M", [-10, -20]), ("L", [-30.5, -40.75])]
        encoded = encode_commands(original)
        decoded = decode_commands(encoded)
        assert decoded[0][1] == pytest.approx([-10, -20])
        assert decoded[1][1] == pytest.approx([-30.5, -40.75], abs=0.01)


class TestCommandDecodeErrors:
    def test_unknown_command(self):
        with pytest.raises(SvgtexDecodeError, match="Unknown command"):
            decode_commands("X10,20")

    def test_wrong_param_count_move(self):
        with pytest.raises(SvgtexDecodeError, match="expects 2 params"):
            decode_commands("M10,20,30")

    def test_wrong_param_count_line(self):
        with pytest.raises(SvgtexDecodeError, match="expects 2 params"):
            decode_commands("L10")

    def test_wrong_param_count_cubic(self):
        with pytest.raises(SvgtexDecodeError, match="expects 6 params"):
            decode_commands("C1,2,3,4")

    def test_wrong_param_count_arc(self):
        with pytest.raises(SvgtexDecodeError, match="expects 5 params"):
            decode_commands("A1,2,3")

    def test_non_numeric_params(self):
        with pytest.raises(SvgtexDecodeError, match="Invalid parameter"):
            decode_commands("Mabc,def")


# ─── Fill Rules ─────────────────────────────────────────────────────────────


class TestFillRuleRoundtrip:
    def test_nonzero(self):
        cmds = [("M", [0, 0]), ("L", [10, 0]), ("Z", [])]
        encoded = encode_path(cmds, "nonzero")
        decoded = decode_path(encoded)
        assert decoded["fill_rule"] == "nonzero"
        assert len(decoded["commands"]) == 3

    def test_evenodd(self):
        cmds = [("M", [0, 0]), ("L", [10, 0]), ("Z", [])]
        encoded = encode_path(cmds, "evenodd")
        decoded = decode_path(encoded)
        assert decoded["fill_rule"] == "evenodd"

    def test_default_is_nonzero(self):
        cmds = [("M", [0, 0]), ("Z", [])]
        encoded = encode_path(cmds)
        decoded = decode_path(encoded)
        assert decoded["fill_rule"] == "nonzero"


class TestFillRuleDecodeErrors:
    def test_empty_segment(self):
        with pytest.raises(SvgtexDecodeError, match="Empty path"):
            decode_path("")

    def test_invalid_prefix(self):
        with pytest.raises(SvgtexDecodeError, match="fill rule"):
            decode_path("XM0,0 Z")


# ─── Full Roundtrip ────────────────────────────────────────────────────────


class TestFullRoundtrip:
    def test_single_triangle(self):
        viewbox = (0, 0, 100, 100)
        paths = [
            {
                "commands": [("M", [0, 0]), ("L", [100, 0]), ("L", [50, 100]), ("Z", [])],
                "fill_rule": "nonzero",
            }
        ]
        encoded = encode_svgtex(viewbox, paths)
        dec_vb, dec_paths = decode_svgtex(encoded)
        assert dec_vb == viewbox
        assert len(dec_paths) == 1
        assert dec_paths[0]["fill_rule"] == "nonzero"
        assert len(dec_paths[0]["commands"]) == 4

    def test_multiple_paths(self):
        viewbox = (0, 0, 200, 200)
        paths = [
            {
                "commands": [("M", [0, 0]), ("L", [50, 0]), ("L", [50, 50]), ("Z", [])],
                "fill_rule": "nonzero",
            },
            {
                "commands": [("M", [100, 100]), ("L", [150, 100]), ("Z", [])],
                "fill_rule": "evenodd",
            },
        ]
        encoded = encode_svgtex(viewbox, paths)
        dec_vb, dec_paths = decode_svgtex(encoded)
        assert dec_vb == viewbox
        assert len(dec_paths) == 2
        assert dec_paths[0]["fill_rule"] == "nonzero"
        assert dec_paths[1]["fill_rule"] == "evenodd"

    def test_mixed_commands_roundtrip(self):
        viewbox = (-10, -10, 120, 120)
        paths = [
            {
                "commands": [
                    ("M", [0, 50]),
                    ("C", [0, 22.39, 22.39, 0, 50, 0]),
                    ("C", [77.61, 0, 100, 22.39, 100, 50]),
                    ("A", [50, 50, 50, 0, 180]),
                    ("Z", []),
                ],
                "fill_rule": "evenodd",
            }
        ]
        encoded = encode_svgtex(viewbox, paths)
        dec_vb, dec_paths = decode_svgtex(encoded)
        assert dec_vb == (-10, -10, 120, 120)
        assert dec_paths[0]["fill_rule"] == "evenodd"
        cmds = dec_paths[0]["commands"]
        assert cmds[0][0] == "M"
        assert cmds[1][0] == "C"
        assert cmds[2][0] == "C"
        assert cmds[3][0] == "A"
        assert cmds[4][0] == "Z"

    def test_precision_preserved(self):
        viewbox = (0, 0, 100, 100)
        paths = [
            {
                "commands": [
                    ("M", [12.345, 67.891]),
                    ("L", [98.765, 43.21]),
                    ("Z", []),
                ],
                "fill_rule": "nonzero",
            }
        ]
        encoded = encode_svgtex(viewbox, paths, precision=3)
        dec_vb, dec_paths = decode_svgtex(encoded)
        assert dec_paths[0]["commands"][0][1] == pytest.approx([12.345, 67.891], abs=0.001)
        assert dec_paths[0]["commands"][1][1] == pytest.approx([98.765, 43.21], abs=0.001)

    def test_viewbox_only_no_paths(self):
        viewbox = (0, 0, 100, 100)
        paths = []
        encoded = encode_svgtex(viewbox, paths)
        dec_vb, dec_paths = decode_svgtex(encoded)
        assert dec_vb == (0, 0, 100, 100)
        assert dec_paths == []


# ─── Arc Preservation ───────────────────────────────────────────────────────


class TestArcPreservation:
    """Verify arc commands survive roundtrip without conversion to cubics."""

    def test_full_circle_arc(self):
        cmds = [
            ("M", [75, 50]),
            ("A", [50, 50, 25, 0, 180]),
            ("A", [50, 50, 25, 180, 180]),
            ("Z", []),
        ]
        encoded = encode_commands(cmds)
        decoded = decode_commands(encoded)
        # Must have 2 arc commands, not converted to cubics
        arc_cmds = [c for c in decoded if c[0] == "A"]
        assert len(arc_cmds) == 2

    def test_arc_params_preserved(self):
        cmds = [("A", [30, 40, 15, 45, -90])]
        encoded = encode_commands(cmds)
        decoded = decode_commands(encoded)
        assert decoded[0][0] == "A"
        assert decoded[0][1] == pytest.approx([30, 40, 15, 45, -90])

    def test_arc_negative_sweep(self):
        cmds = [("A", [50, 50, 10, 0, -270])]
        encoded = encode_commands(cmds)
        decoded = decode_commands(encoded)
        assert decoded[0][1][4] == pytest.approx(-270)


# ─── Precision / Formatting ────────────────────────────────────────────────


class TestPrecisionFormatting:
    def test_trailing_zeros_stripped(self):
        encoded = encode_commands([("L", [10.0, 20.0])])
        assert encoded == "L10,20"

    def test_negative_zero_becomes_zero(self):
        encoded = encode_commands([("L", [-0.0, -0.0])])
        assert encoded == "L0,0"

    def test_high_precision(self):
        encoded = encode_commands([("L", [1.23456789, 9.87654321])], precision=6)
        decoded = decode_commands(encoded)
        assert decoded[0][1][0] == pytest.approx(1.234568, abs=1e-6)
        assert decoded[0][1][1] == pytest.approx(9.876543, abs=1e-6)

    def test_precision_truncation(self):
        """Values are truncated to precision, not rounded up to extra digits."""
        encoded = encode_commands([("L", [1.999, 2.001])], precision=2)
        decoded = decode_commands(encoded)
        assert decoded[0][1][0] == pytest.approx(2.0, abs=0.01)
        assert decoded[0][1][1] == pytest.approx(2.0, abs=0.01)


# ─── Full Decode Errors ────────────────────────────────────────────────────


class TestFullDecodeErrors:
    def test_empty_string(self):
        with pytest.raises(SvgtexDecodeError, match="Empty"):
            decode_svgtex("")

    def test_whitespace_only(self):
        with pytest.raises(SvgtexDecodeError, match="Empty"):
            decode_svgtex("   \n  ")

    def test_no_viewbox_prefix(self):
        with pytest.raises(SvgtexDecodeError, match="must start with 'V'"):
            decode_svgtex("0,0,100,100|NM0,0 Z")


# ─── Format Invariants ─────────────────────────────────────────────────────


class TestFormatInvariants:
    """Verify format properties that FeatureScript depends on."""

    def test_no_angle_brackets(self):
        viewbox = (0, 0, 100, 100)
        paths = [{"commands": [("M", [0, 0]), ("L", [10, 20]), ("Z", [])], "fill_rule": "nonzero"}]
        result = encode_svgtex(viewbox, paths)
        assert "<" not in result
        assert ">" not in result

    def test_no_quotes(self):
        viewbox = (0, 0, 100, 100)
        paths = [{"commands": [("M", [0, 0]), ("Z", [])], "fill_rule": "nonzero"}]
        result = encode_svgtex(viewbox, paths)
        assert '"' not in result
        assert "'" not in result

    def test_no_newlines(self):
        viewbox = (0, 0, 100, 100)
        paths = [{"commands": [("M", [0, 0]), ("L", [10, 20]), ("Z", [])], "fill_rule": "nonzero"}]
        result = encode_svgtex(viewbox, paths)
        assert "\n" not in result
        assert "\r" not in result

    def test_pipe_delimited(self):
        viewbox = (0, 0, 100, 100)
        paths = [
            {"commands": [("M", [0, 0]), ("Z", [])], "fill_rule": "nonzero"},
            {"commands": [("M", [10, 10]), ("Z", [])], "fill_rule": "evenodd"},
        ]
        result = encode_svgtex(viewbox, paths)
        segments = result.split("|")
        assert len(segments) == 3  # viewbox + 2 paths
        assert segments[0].startswith("V")
        assert segments[1].startswith("N")
        assert segments[2].startswith("E")

    def test_single_line(self):
        """SVGTEX must be a single line (Onshape TextData is single-line)."""
        viewbox = (0, 0, 100, 100)
        paths = [
            {"commands": [("M", [0, 0]), ("L", [10, 0]), ("L", [10, 10]), ("Z", [])], "fill_rule": "nonzero"},
        ]
        result = encode_svgtex(viewbox, paths)
        lines = result.split("\n")
        assert len(lines) == 1


# ─── Entity Count Consistency ──────────────────────────────────────────────


class TestEntityCountConsistency:
    """Verify decoder entity count matches encoder's estimate."""

    def test_simple_path(self):
        paths = [
            {
                "commands": [("M", [0, 0]), ("L", [10, 0]), ("L", [10, 10]), ("L", [0, 10]), ("Z", [])],
                "fill_rule": "nonzero",
            }
        ]
        encoder_count = encoder_entity_count(paths)
        encoded = encode_svgtex((0, 0, 100, 100), paths)
        _, dec_paths = decode_svgtex(encoded)
        decoder_count = estimate_entity_count(dec_paths)
        assert encoder_count == decoder_count

    def test_mixed_commands(self):
        paths = [
            {
                "commands": [
                    ("M", [0, 0]),
                    ("L", [50, 0]),
                    ("C", [75, 0, 100, 25, 100, 50]),
                    ("A", [50, 50, 50, 0, 180]),
                    ("L", [0, 50]),
                    ("Z", []),
                ],
                "fill_rule": "nonzero",
            }
        ]
        encoder_count = encoder_entity_count(paths)
        encoded = encode_svgtex((0, 0, 100, 100), paths)
        _, dec_paths = decode_svgtex(encoded)
        decoder_count = estimate_entity_count(dec_paths)
        assert encoder_count == decoder_count
        assert encoder_count == 4  # 2 L + 1 C + 1 A

    def test_multiple_paths(self):
        paths = [
            {"commands": [("M", [0, 0]), ("L", [10, 0]), ("Z", [])], "fill_rule": "nonzero"},
            {"commands": [("M", [20, 20]), ("L", [30, 20]), ("L", [30, 30]), ("Z", [])], "fill_rule": "evenodd"},
        ]
        encoder_count = encoder_entity_count(paths)
        encoded = encode_svgtex((0, 0, 100, 100), paths)
        _, dec_paths = decode_svgtex(encoded)
        decoder_count = estimate_entity_count(dec_paths)
        assert encoder_count == decoder_count
        assert encoder_count == 3  # 1 + 2


# ─── Real Texture Files ────────────────────────────────────────────────────


def _get_texture_files():
    """Collect all .txt files from textures/ directory."""
    if not os.path.isdir(TEXTURES_DIR):
        return []
    files = sorted(f for f in os.listdir(TEXTURES_DIR) if f.endswith(".txt"))
    return files


@pytest.mark.parametrize("filename", _get_texture_files())
class TestRealTextures:
    """Parse all shipped texture files and validate structure."""

    def test_decodes_without_error(self, filename):
        path = os.path.join(TEXTURES_DIR, filename)
        with open(path) as f:
            text = f.read()
        viewbox, paths = decode_svgtex(text)
        assert len(viewbox) == 4
        assert viewbox[2] > 0  # width > 0
        assert viewbox[3] > 0  # height > 0

    def test_has_at_least_one_path(self, filename):
        path = os.path.join(TEXTURES_DIR, filename)
        with open(path) as f:
            text = f.read()
        _, paths = decode_svgtex(text)
        assert len(paths) >= 1, f"{filename} has no paths"

    def test_all_paths_have_valid_fill_rule(self, filename):
        path = os.path.join(TEXTURES_DIR, filename)
        with open(path) as f:
            text = f.read()
        _, paths = decode_svgtex(text)
        for p in paths:
            assert p["fill_rule"] in ("evenodd", "nonzero")

    def test_all_paths_have_move_command(self, filename):
        path = os.path.join(TEXTURES_DIR, filename)
        with open(path) as f:
            text = f.read()
        _, paths = decode_svgtex(text)
        for p in paths:
            cmd_types = [c[0] for c in p["commands"]]
            assert "M" in cmd_types, f"Path missing M command in {filename}"

    def test_all_paths_have_drawing_commands(self, filename):
        """Every path should contain at least one drawing command (L, C, or A)."""
        path = os.path.join(TEXTURES_DIR, filename)
        with open(path) as f:
            text = f.read()
        _, paths = decode_svgtex(text)
        for p in paths:
            cmd_types = set(c[0] for c in p["commands"])
            has_drawing = cmd_types & {"L", "C", "A"}
            assert has_drawing, f"Path has no drawing commands in {filename}"

    def test_entity_count_positive(self, filename):
        path = os.path.join(TEXTURES_DIR, filename)
        with open(path) as f:
            text = f.read()
        _, paths = decode_svgtex(text)
        count = estimate_entity_count(paths)
        assert count > 0, f"{filename} has 0 entities"


# ─── Edge Cases ─────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_single_point_path(self):
        """A path with only M and Z."""
        cmds = [("M", [50, 50]), ("Z", [])]
        encoded = encode_path(cmds, "nonzero")
        decoded = decode_path(encoded)
        assert len(decoded["commands"]) == 2

    def test_many_subpaths(self):
        """Multiple M commands in a single path segment."""
        cmds = []
        for i in range(10):
            cmds.extend([
                ("M", [i * 10.0, 0.0]),
                ("L", [i * 10.0 + 5, 0.0]),
                ("L", [i * 10.0 + 5, 5.0]),
                ("Z", []),
            ])
        encoded = encode_path(cmds, "evenodd")
        decoded = decode_path(encoded)
        move_count = sum(1 for c in decoded["commands"] if c[0] == "M")
        assert move_count == 10

    def test_zero_dimension_viewbox(self):
        """Viewbox with zero width/height encodes/decodes."""
        encoded = encode_viewbox(0, 0, 0, 0)
        vb = decode_viewbox(encoded)
        assert vb == (0, 0, 0, 0)

    def test_very_small_coordinates(self):
        cmds = [("M", [0.001, 0.002]), ("L", [0.003, 0.004]), ("Z", [])]
        encoded = encode_commands(cmds, precision=4)
        decoded = decode_commands(encoded)
        assert decoded[0][1] == pytest.approx([0.001, 0.002], abs=1e-4)
        assert decoded[1][1] == pytest.approx([0.003, 0.004], abs=1e-4)

    def test_very_large_coordinates(self):
        cmds = [("M", [99999, 88888]), ("L", [77777, 66666]), ("Z", [])]
        encoded = encode_commands(cmds)
        decoded = decode_commands(encoded)
        assert decoded[0][1] == pytest.approx([99999, 88888])
        assert decoded[1][1] == pytest.approx([77777, 66666])

    def test_arc_with_zero_sweep(self):
        cmds = [("A", [50, 50, 10, 45, 0])]
        encoded = encode_commands(cmds)
        decoded = decode_commands(encoded)
        assert decoded[0][1][4] == pytest.approx(0)

    def test_whitespace_in_svgtex_trimmed(self):
        """Leading/trailing whitespace should be handled."""
        vb, paths = decode_svgtex("  V0,0,100,100|NM0,0 L10,0 Z  \n")
        assert vb == (0, 0, 100, 100)
        assert len(paths) == 1


# ─── FeatureScript Parser Contract ─────────────────────────────────────────


class TestFeatureScriptParserContract:
    """Tests that validate behaviors matching FeatureScript's parseSvgTex().

    The FeatureScript parser:
    - Splits on '|' (not newlines)
    - Skips lines starting with '#' (comments)
    - Skips empty segments
    - Trims whitespace from each segment
    - Viewbox: 'V' prefix, 4 comma-separated numbers
    - Paths: 'E' or 'N' prefix, space-delimited tokens
    - Each token: first char is command letter, rest is comma-separated params
    """

    def test_comment_segments_ignored(self):
        """FeatureScript skips segments starting with '#'."""
        # Manually build a string with a comment segment
        svgtex = "V0,0,100,100|#this is a comment|NM0,0 L10,0 Z"
        vb, paths = decode_svgtex(svgtex)
        assert vb == (0, 0, 100, 100)
        # The comment segment should not create a path
        assert len(paths) == 1

    def test_empty_segments_skipped(self):
        """FeatureScript skips empty segments (consecutive pipes)."""
        svgtex = "V0,0,100,100||NM0,0 Z||EM10,10 L20,20 Z|"
        vb, paths = decode_svgtex(svgtex)
        assert len(paths) == 2

    def test_viewbox_must_be_first(self):
        """The V segment must come before path segments."""
        svgtex = "V0,0,50,50|NM0,0 L10,10 Z"
        vb, paths = decode_svgtex(svgtex)
        assert vb == (0, 0, 50, 50)

    def test_fill_rule_evenodd_prefix(self):
        """'E' prefix = evenodd fill rule (FeatureScript checks firstChar == 'E')."""
        svgtex = "V0,0,100,100|EM0,0 L10,0 L10,10 Z"
        _, paths = decode_svgtex(svgtex)
        assert paths[0]["fill_rule"] == "evenodd"

    def test_fill_rule_nonzero_prefix(self):
        """'N' prefix = nonzero fill rule (FeatureScript default)."""
        svgtex = "V0,0,100,100|NM0,0 L10,0 L10,10 Z"
        _, paths = decode_svgtex(svgtex)
        assert paths[0]["fill_rule"] == "nonzero"

    def test_z_command_no_params(self):
        """Z command has no parameters (FeatureScript checks cc == 'Z')."""
        svgtex = "V0,0,100,100|NM0,0 L50,0 L50,50 Z"
        _, paths = decode_svgtex(svgtex)
        z_cmds = [c for c in paths[0]["commands"] if c[0] == "Z"]
        assert len(z_cmds) == 1
        assert z_cmds[0][1] == []

    def test_command_params_comma_separated(self):
        """FeatureScript splits params on ',' within each token."""
        svgtex = "V0,0,100,100|NM10,20 L30,40 Z"
        _, paths = decode_svgtex(svgtex)
        assert paths[0]["commands"][0] == ("M", [10, 20])
        assert paths[0]["commands"][1] == ("L", [30, 40])

    def test_cubic_six_params(self):
        """C command must have exactly 6 comma-separated params."""
        svgtex = "V0,0,100,100|NM0,0 C10,20,30,40,50,60 Z"
        _, paths = decode_svgtex(svgtex)
        c_cmd = paths[0]["commands"][1]
        assert c_cmd[0] == "C"
        assert len(c_cmd[1]) == 6

    def test_arc_five_params(self):
        """A command has 5 params: cx,cy,r,startDeg,sweepDeg (center-parameterized)."""
        svgtex = "V0,0,100,100|NM75,50 A50,50,25,0,180 Z"
        _, paths = decode_svgtex(svgtex)
        a_cmd = paths[0]["commands"][1]
        assert a_cmd[0] == "A"
        assert len(a_cmd[1]) == 5
        assert a_cmd[1] == pytest.approx([50, 50, 25, 0, 180])

    def test_multiple_paths_different_fill_rules(self):
        """FeatureScript parses each segment independently with its own fill rule."""
        svgtex = "V0,0,100,100|NM0,0 L10,0 Z|EM20,20 L30,30 Z"
        _, paths = decode_svgtex(svgtex)
        assert len(paths) == 2
        assert paths[0]["fill_rule"] == "nonzero"
        assert paths[1]["fill_rule"] == "evenodd"

    def test_negative_params(self):
        """FeatureScript parseNum handles negative values."""
        svgtex = "V-10,-20,200,300|NM-5,-10 L-15,-25 Z"
        vb, paths = decode_svgtex(svgtex)
        assert vb == (-10, -20, 200, 300)
        assert paths[0]["commands"][0][1] == pytest.approx([-5, -10])

    def test_decimal_params(self):
        """FeatureScript parseNum handles decimal values."""
        svgtex = "V0,0,100,100|NM1.5,2.75 L99.99,0.01 Z"
        _, paths = decode_svgtex(svgtex)
        assert paths[0]["commands"][0][1] == pytest.approx([1.5, 2.75])
        assert paths[0]["commands"][1][1] == pytest.approx([99.99, 0.01])

    def test_detectAndParse_svgtex_detection(self):
        """FeatureScript detectAndParse checks: starts with 'V' + digit or '-'."""
        # Valid SVGTEX starts
        for start in ["V0,0,100,100", "V-10,0,100,100", "V1,2,3,4"]:
            vb, _ = decode_svgtex(start)
            assert vb[2] > 0 or vb[2] == 0  # just verify it parses

    def test_output_is_single_line(self):
        """SVGTEX must be a single line for Onshape TextData."""
        viewbox = (0, 0, 100, 100)
        paths = [
            {"commands": [("M", [0, 0]), ("L", [50, 0]), ("L", [50, 50]), ("Z", [])], "fill_rule": "nonzero"},
            {"commands": [("M", [60, 60]), ("L", [90, 60]), ("L", [90, 90]), ("Z", [])], "fill_rule": "evenodd"},
        ]
        result = encode_svgtex(viewbox, paths)
        assert "\n" not in result
        assert "\r" not in result

    def test_pipe_is_only_delimiter(self):
        """No other top-level delimiters besides '|'."""
        viewbox = (0, 0, 100, 100)
        paths = [{"commands": [("M", [0, 0]), ("L", [10, 10]), ("Z", [])], "fill_rule": "nonzero"}]
        result = encode_svgtex(viewbox, paths)
        # Split on pipe should give viewbox + paths
        segments = result.split("|")
        assert len(segments) == 2
        assert segments[0].startswith("V")
        assert segments[1].startswith("N") or segments[1].startswith("E")


# ─── End-to-End SVG → SVGTEX → Decode ─────────────────────────────────────


class TestEndToEndRoundtrip:
    """Full pipeline: SVG string → parse → encode → decode → validate."""

    def _pipeline(self, svg_content, include_strokes=False, stroke_width=None, precision=2):
        from svg_to_tex.svg_parser import parse_svg
        from svg_to_tex.region_analyzer import filter_filled_paths
        from svg_to_tex.stroke_outliner import stroke_to_outlines
        viewbox, paths = parse_svg(svg_content, include_strokes=include_strokes)
        if include_strokes:
            paths = stroke_to_outlines(paths, stroke_width_override=stroke_width)
        filled = filter_filled_paths(paths)
        svgtex = encode_svgtex(viewbox, filled, precision)
        return decode_svgtex(svgtex)

    def test_rect_roundtrip(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <rect x="10" y="10" width="80" height="80" fill="black"/>
        </svg>'''
        vb, paths = self._pipeline(svg)
        assert vb == (0, 0, 100, 100)
        assert len(paths) == 1
        cmds = paths[0]["commands"]
        assert cmds[0][0] == "M"
        assert cmds[-1][0] == "Z"
        # Rect: M L L L Z = 5 commands
        assert len(cmds) == 5

    def test_circle_roundtrip(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="25" fill="red"/>
        </svg>'''
        vb, paths = self._pipeline(svg)
        assert vb == (0, 0, 100, 100)
        assert len(paths) == 1
        # Circle produces arcs (A commands) in center-parameterized form
        cmd_types = [c[0] for c in paths[0]["commands"]]
        assert "M" in cmd_types
        has_curves = "C" in cmd_types or "A" in cmd_types
        assert has_curves

    def test_two_rects_roundtrip(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">
            <rect x="10" y="10" width="30" height="30" fill="red"/>
            <rect x="60" y="10" width="30" height="30" fill="blue"/>
        </svg>'''
        vb, paths = self._pipeline(svg)
        assert len(paths) == 2
        for p in paths:
            assert p["fill_rule"] in ("nonzero", "evenodd")
            assert len(p["commands"]) >= 4

    def test_evenodd_path_roundtrip(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <path d="M10,10 L90,10 L90,90 L10,90 Z M30,30 L70,30 L70,70 L30,70 Z"
                  fill="black" fill-rule="evenodd"/>
        </svg>'''
        vb, paths = self._pipeline(svg)
        assert len(paths) == 1
        assert paths[0]["fill_rule"] == "evenodd"

    def test_translated_group_roundtrip(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
            <g transform="translate(50,50)">
                <rect x="0" y="0" width="40" height="40" fill="black"/>
            </g>
        </svg>'''
        vb, paths = self._pipeline(svg)
        assert len(paths) == 1
        # First M should be at (50, 50) after translate
        m_cmd = paths[0]["commands"][0]
        assert m_cmd[0] == "M"
        assert m_cmd[1] == pytest.approx([50, 50])

    def test_stroke_outline_roundtrip(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <line x1="10" y1="50" x2="90" y2="50" stroke="black" stroke-width="4"/>
        </svg>'''
        vb, paths = self._pipeline(svg, include_strokes=True)
        assert len(paths) >= 1
        # Outline should have drawing commands
        total_entities = estimate_entity_count(paths)
        assert total_entities > 0

    def test_polygon_roundtrip(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <polygon points="50,0 100,100 0,100" fill="green"/>
        </svg>'''
        vb, paths = self._pipeline(svg)
        assert len(paths) == 1
        cmd_types = [c[0] for c in paths[0]["commands"]]
        assert cmd_types[0] == "M"
        assert "Z" in cmd_types

    def test_ellipse_roundtrip(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <ellipse cx="50" cy="50" rx="40" ry="20" fill="orange"/>
        </svg>'''
        vb, paths = self._pipeline(svg)
        assert len(paths) == 1
        cmd_types = [c[0] for c in paths[0]["commands"]]
        assert "M" in cmd_types
        has_curves = "C" in cmd_types or "A" in cmd_types
        assert has_curves

    def test_no_fill_produces_no_paths(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <rect x="10" y="10" width="80" height="80" fill="none" stroke="black"/>
        </svg>'''
        vb, paths = self._pipeline(svg)
        assert len(paths) == 0

    def test_hidden_element_excluded(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <rect x="0" y="0" width="100" height="100" fill="black" display="none"/>
            <rect x="10" y="10" width="30" height="30" fill="red"/>
        </svg>'''
        vb, paths = self._pipeline(svg)
        assert len(paths) == 1

    def test_use_element_roundtrip(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">
            <defs>
                <rect id="tile" x="0" y="0" width="20" height="20" fill="black"/>
            </defs>
            <use href="#tile" x="10" y="10"/>
            <use href="#tile" x="50" y="10"/>
        </svg>'''
        vb, paths = self._pipeline(svg)
        assert len(paths) == 2

    def test_complex_path_roundtrip(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <path d="M10,80 C10,10 90,10 90,80 Q50,120 10,80 Z" fill="purple"/>
        </svg>'''
        vb, paths = self._pipeline(svg)
        assert len(paths) == 1
        cmd_types = [c[0] for c in paths[0]["commands"]]
        assert "M" in cmd_types
        assert "C" in cmd_types

    def test_entity_count_matches(self):
        """Encoder entity count matches decoder entity count after roundtrip."""
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <rect x="10" y="10" width="80" height="80" fill="black"/>
            <circle cx="50" cy="50" r="20" fill="white"/>
        </svg>'''
        from svg_to_tex.svg_parser import parse_svg
        from svg_to_tex.region_analyzer import filter_filled_paths, estimate_entity_count as enc_count
        viewbox, raw_paths = parse_svg(svg)
        filled = filter_filled_paths(raw_paths)
        encoder_entities = enc_count(filled)
        svgtex = encode_svgtex(viewbox, filled)
        _, dec_paths = decode_svgtex(svgtex)
        decoder_entities = estimate_entity_count(dec_paths)
        assert encoder_entities == decoder_entities


# ─── Real Texture SVG → SVGTEX → Decode ───────────────────────────────────


def _get_texture_svg_files():
    """Collect all .svg files from textures/ directory."""
    if not os.path.isdir(TEXTURES_DIR):
        return []
    return sorted(f for f in os.listdir(TEXTURES_DIR) if f.endswith(".svg"))


@pytest.mark.parametrize("filename", _get_texture_svg_files())
class TestRealTextureSvgRoundtrip:
    """Parse real .svg texture files through the full pipeline and validate."""

    def _process(self, filename):
        from svg_to_tex.svg_parser import parse_svg
        from svg_to_tex.region_analyzer import filter_filled_paths
        from svg_to_tex.stroke_outliner import stroke_to_outlines
        from svg_to_tex.viewbox_clipper import clip_paths_to_viewbox
        svg_path = os.path.join(TEXTURES_DIR, filename)
        with open(svg_path) as f:
            svg_content = f.read()
        viewbox, paths = parse_svg(svg_content, include_strokes=True)
        paths = stroke_to_outlines(paths)
        paths = clip_paths_to_viewbox(paths, viewbox)
        filled = filter_filled_paths(paths)
        svgtex = encode_svgtex(viewbox, filled)
        return decode_svgtex(svgtex), svgtex

    def test_svg_produces_decodable_svgtex(self, filename):
        (vb, paths), svgtex = self._process(filename)
        assert vb[2] > 0  # width > 0
        assert vb[3] > 0  # height > 0

    def test_svg_produces_paths(self, filename):
        (vb, paths), _ = self._process(filename)
        assert len(paths) >= 1, f"{filename} produced no paths"

    def test_svg_svgtex_matches_prebuilt(self, filename):
        """Verify the SVG pipeline produces output consistent with the .txt file."""
        txt_name = filename.replace(".svg", ".txt")
        txt_path = os.path.join(TEXTURES_DIR, txt_name)
        if not os.path.exists(txt_path):
            pytest.skip(f"No prebuilt .txt for {filename}")
        with open(txt_path) as f:
            prebuilt = f.read().strip()
        (_, paths_from_svg), svgtex = self._process(filename)
        _, paths_from_txt = decode_svgtex(prebuilt)
        # Path count should match between fresh encode and prebuilt
        assert len(paths_from_svg) == len(paths_from_txt), \
            f"{filename}: SVG pipeline gives {len(paths_from_svg)} paths, prebuilt has {len(paths_from_txt)}"


# ─── Stress / Boundary Tests ──────────────────────────────────────────────


class TestStressAndBoundary:
    """Tests near Onshape limits and with extreme inputs."""

    def test_many_paths(self):
        """100 paths encode and decode correctly."""
        viewbox = (0, 0, 1000, 1000)
        paths = []
        for i in range(100):
            x = float(i * 10)
            paths.append({
                "commands": [("M", [x, 0]), ("L", [x+5, 0]), ("L", [x+5, 5]), ("Z", [])],
                "fill_rule": "nonzero",
            })
        svgtex = encode_svgtex(viewbox, paths)
        vb, dec_paths = decode_svgtex(svgtex)
        assert len(dec_paths) == 100

    def test_long_path(self):
        """A single path with 500 line segments."""
        cmds = [("M", [0.0, 0.0])]
        for i in range(1, 501):
            cmds.append(("L", [float(i), float(i % 50)]))
        cmds.append(("Z", []))
        viewbox = (0, 0, 500, 50)
        paths = [{"commands": cmds, "fill_rule": "nonzero"}]
        svgtex = encode_svgtex(viewbox, paths)
        vb, dec_paths = decode_svgtex(svgtex)
        assert len(dec_paths) == 1
        assert len(dec_paths[0]["commands"]) == 502  # M + 500 L + Z
        assert estimate_entity_count(dec_paths) == 500

    def test_output_within_onshape_limit(self):
        """Typical texture should be under 10000 chars."""
        # Use a moderate synthetic texture
        viewbox = (0, 0, 100, 100)
        paths = []
        for i in range(20):
            x = float(i * 5)
            paths.append({
                "commands": [
                    ("M", [x, 0]), ("L", [x+4, 0]), ("L", [x+4, 4]),
                    ("L", [x, 4]), ("Z", []),
                ],
                "fill_rule": "nonzero",
            })
        svgtex = encode_svgtex(viewbox, paths)
        assert len(svgtex) < 10000, f"Output is {len(svgtex)} chars, exceeds Onshape limit"

    def test_max_entity_count(self):
        """Entity count is correctly tracked for large outputs."""
        viewbox = (0, 0, 100, 100)
        cmds = [("M", [0.0, 0.0])]
        for i in range(2500):
            cmds.append(("L", [float(i % 100), float(i // 100)]))
        cmds.append(("Z", []))
        paths = [{"commands": cmds, "fill_rule": "nonzero"}]
        svgtex = encode_svgtex(viewbox, paths)
        _, dec_paths = decode_svgtex(svgtex)
        count = estimate_entity_count(dec_paths)
        assert count == 2500

    def test_all_command_types_in_one_path(self):
        """A path using M, L, C, A, and Z together."""
        cmds = [
            ("M", [0, 50]),
            ("L", [20, 0]),
            ("C", [30, 0, 40, 10, 50, 10]),
            ("A", [70, 10, 20, 0, 180]),
            ("L", [100, 50]),
            ("C", [100, 80, 80, 100, 50, 100]),
            ("A", [50, 50, 50, 90, 180]),
            ("L", [0, 50]),
            ("Z", []),
        ]
        viewbox = (0, 0, 100, 100)
        paths = [{"commands": cmds, "fill_rule": "evenodd"}]
        svgtex = encode_svgtex(viewbox, paths)
        vb, dec_paths = decode_svgtex(svgtex)
        assert len(dec_paths) == 1
        dec_cmd_types = [c[0] for c in dec_paths[0]["commands"]]
        assert set(dec_cmd_types) == {"M", "L", "C", "A", "Z"}
        assert dec_paths[0]["fill_rule"] == "evenodd"

    def test_many_subpaths_in_one_segment(self):
        """Multiple M-...-Z sequences within a single path segment."""
        cmds = []
        for i in range(50):
            x = float(i * 2)
            cmds.extend([
                ("M", [x, 0]),
                ("L", [x+1, 0]),
                ("L", [x+1, 1]),
                ("L", [x, 1]),
                ("Z", []),
            ])
        viewbox = (0, 0, 100, 2)
        paths = [{"commands": cmds, "fill_rule": "nonzero"}]
        svgtex = encode_svgtex(viewbox, paths)
        _, dec_paths = decode_svgtex(svgtex)
        assert len(dec_paths) == 1
        m_count = sum(1 for c in dec_paths[0]["commands"] if c[0] == "M")
        assert m_count == 50
