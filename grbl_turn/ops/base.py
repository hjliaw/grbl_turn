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
#   ratio  - dimensionless float (never unit-converted)
#   int    - integer spinbox
#   choice - combo box (choices list)
#   bool   - checkbox
#   rpm    - integer spindle speed
#   pitch  - thread pitch value; never unit-converted (TPI in inch mode,
#            mm/rev in mm mode)

# kinds whose values are lengths and get converted when the units change
DIMENSIONAL_KINDS = ("dia", "len", "zpos", "feed")


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
    default_mm: float | None = None   # mm-mode default for kind "pitch"
    unit: str = ""   # fixed unit text shown after the input (e.g. "deg")
    # optional auto-calculation for the value, from the other parameters;
    # the form shows an "auto" button next to fields that define one
    auto: Callable[[dict, Units], float] | None = None
    # optional named preset values; the form adds a dropdown above the
    # field that fills the value in (editing the field reverts to custom)
    presets: dict[str, float] | None = None
    # bool fields only: names of fields grayed out while this is checked
    disables: list[str] = field(default_factory=list)
    # (choice field name, value): show this field only while that choice
    # field holds that value
    visible_when: tuple[str, str] | None = None
    # where the form places the field: "form" (default) or "left" — above
    # the diagram; a "left" choice renders as a row of exclusive buttons
    placement: str = "form"


@dataclass
class Operation:
    key: str
    title: str
    icon: str      # SVG filename in resources/images
    diagram: str   # SVG shown in the parameter dialog
    fields: list[Field]
    generate: Callable[[dict, MachineProfile, Units], list[str]]
    is_threading: bool = False
    # how the preview derives the part silhouette from the cutting moves:
    #   turn - cuts lower the surface where they pass (OD work, parting)
    #   face - cuts also remove everything to their +Z side (facing)
    #   bore - cuts raise the bore surface; material sits outside it
    silhouette: str = "turn"


# The app never touches the spindle: the user's machine is adjusted
# manually, so programs contain no M3/M5/S words — start the spindle
# before Run, stop it after.
