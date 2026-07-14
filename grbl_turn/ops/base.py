"""Operation framework: each lathe operation is a Field list plus a
generate() function; the generic OpDialog renders the fields."""

from dataclasses import dataclass, field
from typing import Callable

from grbl_turn.machine import MachineProfile
from grbl_turn.units import Units

# Field kinds drive the widget/validator used by the dialog:
#   dia    - a diameter, positive float
#   len    - a length/depth, positive float
#   zpos   - a Z distance from the face, positive float (cut happens at -value)
#   feed   - feed rate, units/min
#   angle  - degrees
#   int    - integer spinbox
#   choice - combo box (choices list)
#   bool   - checkbox
#   rpm    - integer spindle speed


@dataclass
class Field:
    name: str
    label: str
    kind: str
    default: float | int | str | bool
    group: str = ""
    minimum: float = 0.0
    maximum: float = 10000.0
    tooltip: str = ""
    choices: list[str] = field(default_factory=list)


@dataclass
class Operation:
    key: str
    title: str
    icon: str      # SVG filename in resources/images
    diagram: str   # SVG shown in the parameter dialog
    fields: list[Field]
    generate: Callable[[dict, MachineProfile, Units], list[str]]
    is_threading: bool = False


def spindle_fields(default_rpm: int = 600) -> list[Field]:
    return [
        Field("rpm", "Spindle RPM", "rpm", default_rpm, group="Spindle",
              minimum=1, maximum=10000,
              tooltip="Only used when 'App starts spindle' is checked"),
        Field("app_spindle", "App starts spindle (M3)", "bool", False,
              group="Spindle",
              tooltip="Unchecked: start the spindle yourself before Run"),
    ]


def spindle_preamble(params: dict) -> list[str]:
    if params.get("app_spindle"):
        return [f"M3 S{int(params['rpm'])}"]
    return []
