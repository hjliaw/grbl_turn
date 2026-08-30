"""Facing: remove material from the end of the stock, feeding X toward center."""

from grbl_turn.gcode import Program
from grbl_turn.machine import MachineProfile
from grbl_turn.ops.base import Field, Operation
from grbl_turn.units import Units

FIELDS = [
    Field("total_depth", "Total depth (Z)", "len", 0.020,
          group="Z (bed/leadscrew)", tooltip="Total material removed off the face"),
    Field("doc", "Depth per pass (Z)", "len", 0.010, group="Z (bed/leadscrew)"),
    Field("work_dia", "Stock diameter", "dia", 0.750, group="X (cross-slide)"),
    Field("end_dia", "End diameter", "dia", 0.0, group="X (cross-slide)",
          minimum=0.0, tooltip="0 = face to center"),
    Field("feed", "Feed", "feed", 3.0, group="Cutting"),
    Field("clearance", "Clearance", "len", 0.040, group="Cutting"),
]


def generate(p: dict, machine: MachineProfile, units: Units) -> list[str]:
    work_r = p["work_dia"] / 2.0
    end_r = p["end_dia"] / 2.0
    clear = p["clearance"]

    prog = Program(machine, units, origin_r=work_r,
                   start_note="touch off on the stock OD at the face")
    prog.header(
        "Facing",
        [f"stock dia {p['work_dia']}, total depth {p['total_depth']}",
         f"doc {p['doc']}, feed {p['feed']}"])
    prog.rapid(x=work_r + clear, z=clear)

    # Z0 is the CURRENT face; each pass goes deeper until total_depth removed.
    z = 0.0
    remaining = p["total_depth"]
    while remaining > 1e-9:
        step = min(p["doc"], remaining)
        z -= step
        remaining -= step
        prog.rapid(x=work_r + clear)
        prog.rapid(z=z)
        prog.feed(x=end_r, f=p["feed"])
        prog.rapid(z=z + clear)
    return prog.end()


OP = Operation("ext_facing", "Facing", "ext_facing.svg", "ext_facing.svg",
               FIELDS, generate, silhouette="face")
