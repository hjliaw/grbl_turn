"""Facing: remove material from the end of the stock, feeding X toward
center.

No absolute stock diameter is asked for: the operator touches off on the
stock OD at the face, and the sweep is specified as a diameter to face
across from there. Facing all the way to center just means entering at
least the stock's real diameter -- sweeping a little past center is
harmless, it only cuts air on the far side."""

from grbl_turn.gcode import Program
from grbl_turn.machine import MachineProfile
from grbl_turn.ops.base import Field, Operation
from grbl_turn.units import Units

FIELDS = [
    Field("total_depth", "Total depth (Z)", "len", 0.020,
          group="Z (bed/leadscrew)", tooltip="Total material removed off the face"),
    Field("doc", "Depth per pass (Z)", "len", 0.010, group="Z (bed/leadscrew)"),
    Field("dia_reduction", "Diameter to face across", "dia", 0.750,
          group="X (cross-slide)",
          tooltip="Swept from the touched OD; enter at least the stock "
                  "diameter to face all the way to center"),
    Field("feed", "Feed", "feed", 3.0, group="Cutting"),
    Field("clearance", "Clearance", "len", 0.040, group="Cutting"),
]


def generate(p: dict, machine: MachineProfile, units: Units) -> list[str]:
    end_r = -p["dia_reduction"] / 2.0
    if end_r >= 0:
        raise ValueError("diameter to face across must be > 0")
    clear = p["clearance"]

    prog = Program(machine, units, origin_r=None,
                   start_note="touch off on the stock OD at the face")
    prog.header(
        "Facing",
        [f"face across {p['dia_reduction']} dia, total depth "
         f"{p['total_depth']}",
         f"doc {p['doc']}, feed {p['feed']}"])
    prog.rapid(x=clear, z=clear)

    # Z0 is the CURRENT face; each pass goes deeper until total_depth removed.
    z = 0.0
    remaining = p["total_depth"]
    while remaining > 1e-9:
        step = min(p["doc"], remaining)
        z -= step
        remaining -= step
        prog.rapid(x=clear)
        prog.rapid(z=z)
        prog.feed(x=end_r, f=p["feed"])
        prog.rapid(z=z + clear)
    return prog.end()


OP = Operation("ext_facing", "Facing", "ext_facing.svg", "ext_facing.svg",
               FIELDS, generate, silhouette="face")
