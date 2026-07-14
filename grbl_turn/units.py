"""Unit handling. All operation math happens in the units the user chose;
the generated program declares them with G20/G21."""

from enum import Enum

MM_PER_INCH = 25.4


class Units(Enum):
    INCH = "inch"
    MM = "mm"

    @property
    def gcode(self) -> str:
        return "G20" if self is Units.INCH else "G21"

    @property
    def decimals(self) -> int:
        return 4 if self is Units.INCH else 3


def fmt(value: float, units: Units) -> str:
    """Format a coordinate/length for G-code output."""
    return f"{value:.{units.decimals}f}"
