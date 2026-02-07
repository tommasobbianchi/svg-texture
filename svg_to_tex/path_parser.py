"""
Tokenize SVG path `d` attribute.

Handles implicit commands, double-decimal (e.g. "1.2.3" = "1.2 0.3"),
sign-as-separator (e.g. "10-5" = "10 -5"), and all SVG path commands.
"""

import re
from typing import List, Tuple

# SVG path command letters
COMMANDS = set("MmZzLlHhVvCcSsQqTtAa")

# Number of coordinate values expected per command
PARAM_COUNTS = {
    "M": 2, "m": 2,
    "L": 2, "l": 2,
    "H": 1, "h": 1,
    "V": 1, "v": 1,
    "C": 6, "c": 6,
    "S": 4, "s": 4,
    "Q": 4, "q": 4,
    "T": 2, "t": 2,
    "A": 7, "a": 7,
    "Z": 0, "z": 0,
}

# Commands that repeat with an implicit command letter
IMPLICIT_NEXT = {
    "M": "L", "m": "l",
}


def tokenize_numbers(s: str) -> List[float]:
    """Extract all numbers from a string, handling SVG-specific edge cases.

    SVG allows:
    - Comma or whitespace as separator
    - Sign (-/+) as implicit separator: "10-5" -> [10, -5]
    - Double decimal as separator: "1.2.3" -> [1.2, 0.3]
    """
    # Match: optional sign, digits with optional decimal, or just decimal+digits
    # Also handles scientific notation (rare in SVG but valid)
    pattern = r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"
    return [float(m) for m in re.findall(pattern, s)]


def parse_path(d: str) -> List[Tuple[str, List[float]]]:
    """Parse an SVG path `d` attribute into a list of (command, params) tuples.

    Returns:
        List of (command_letter, [param_values]) tuples.
        Implicit repeated commands are expanded.
        e.g., "M 0,0 10,10 20,20" -> [('M', [0,0]), ('L', [10,10]), ('L', [20,20])]
    """
    if not d:
        return []

    # Split into segments: each starting with a command letter
    # First, insert a separator before each command letter
    tokens = []
    current_cmd = None
    current_nums_str = ""

    # Iterate character by character to split commands from number sequences
    i = 0
    segments = []
    while i < len(d):
        ch = d[i]
        if ch in COMMANDS:
            if current_cmd is not None or current_nums_str.strip():
                segments.append((current_cmd, current_nums_str))
            current_cmd = ch
            current_nums_str = ""
        else:
            current_nums_str += ch
        i += 1

    if current_cmd is not None or current_nums_str.strip():
        segments.append((current_cmd, current_nums_str))

    result = []
    for cmd, num_str in segments:
        if cmd is None:
            # Numbers before any command - shouldn't happen in valid SVG
            continue

        if cmd in ("Z", "z"):
            result.append((cmd, []))
            # Any trailing numbers after Z are ignored (or belong to implicit M)
            nums = tokenize_numbers(num_str)
            if nums:
                # Numbers after Z imply an implicit M
                param_count = PARAM_COUNTS["M"]
                implicit_cmd = "M" if cmd == "Z" else "m"
                for j in range(0, len(nums), param_count):
                    chunk = nums[j : j + param_count]
                    if len(chunk) == param_count:
                        result.append((implicit_cmd, chunk))
                        implicit_cmd = IMPLICIT_NEXT.get(implicit_cmd, implicit_cmd)
            continue

        nums = tokenize_numbers(num_str)
        param_count = PARAM_COUNTS[cmd]

        if param_count == 0:
            result.append((cmd, []))
            continue

        # Split numbers into groups of param_count
        idx = 0
        first = True
        while idx + param_count <= len(nums):
            chunk = nums[idx : idx + param_count]
            if first:
                result.append((cmd, chunk))
                first = False
            else:
                # Implicit repeat: M becomes L, m becomes l, others repeat same
                implicit = IMPLICIT_NEXT.get(cmd, cmd)
                result.append((implicit, chunk))
            idx += param_count

    return result
