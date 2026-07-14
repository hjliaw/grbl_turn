"""G-code program assembly and analysis.

Conventions used throughout:
  X0 = spindle centerline, Z0 = part face, Z negative into the work.
  G18 (XZ plane), G90 (absolute), G94 (units/min feed).
"""

import re
from datetime import date

from grbl_turn.units import Units, fmt


def header(op_title: str, param_desc: list[str], units: Units) -> list[str]:
    lines = [f"({op_title} - grbl_turn {date.today().isoformat()})"]
    lines += [f"({d})" for d in param_desc]
    lines.append(f"{units.gcode} G18 G90 G94")
    return lines


def footer(spindle_started: bool, safe_x_word: float, safe_z: float,
           units: Units) -> list[str]:
    lines = []
    if spindle_started:
        lines.append("M5")
    lines.append(f"G0 X{fmt(safe_x_word, units)}")
    lines.append(f"G0 Z{fmt(safe_z, units)}")
    lines.append("M2")
    return lines


_WORD = re.compile(r"([XZ])(-?\d+\.?\d*)")


def extents(lines: list[str]) -> dict[str, tuple[float, float]]:
    """Min/max of every X and Z word in the program (comments excluded)."""
    found: dict[str, list[float]] = {"X": [], "Z": []}
    for line in lines:
        line = re.sub(r"\(.*?\)", "", line)
        for axis, num in _WORD.findall(line):
            found[axis].append(float(num))
    return {axis: (min(vals), max(vals)) for axis, vals in found.items() if vals}
