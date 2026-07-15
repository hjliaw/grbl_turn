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
        """G-code output precision."""
        return 4 if self is Units.INCH else 3

    @property
    def display_decimals(self) -> int:
        """DRO readouts: one digit coarser than the G-code."""
        return 3 if self is Units.INCH else 2


def fmt(value: float, units: Units) -> str:
    """Format a coordinate/length for G-code output."""
    return f"{value:.{units.decimals}f}"


def convert(value: float, old: Units, new: Units) -> float:
    if old is new:
        return value
    return value * MM_PER_INCH if new is Units.MM else value / MM_PER_INCH
