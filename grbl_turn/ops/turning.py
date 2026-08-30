"""External OD turning: reduce start diameter to end diameter over a length."""

from grbl_turn.gcode import Program
from grbl_turn.machine import MachineProfile
from grbl_turn.ops.base import Field, Operation
from grbl_turn.ops.passes import turning_passes
from grbl_turn.units import Units

FIELDS = [
    Field("length", "Length", "len", 0.750, group="Z (bed/leadscrew)",
          tooltip="Cut runs from Z0 to Z-length"),
    Field("start_dia", "Start diameter", "dia", 0.500, group="X (cross-slide)"),
    Field("end_dia", "End diameter", "dia", 0.400, group="X (cross-slide)"),
    Field("doc", "Depth per pass, radial", "len", 0.020, group="X (cross-slide)",
          tooltip="Radial depth of cut for each roughing pass"),
    Field("finish_allow", "Finish allowance, radial", "len", 0.005,
          group="X (cross-slide)", minimum=0.0,
          tooltip="Left for the final pass; 0 = no separate finish pass"),
    Field("feed", "Feed", "feed", 3.0, group="Cutting"),
    Field("clearance", "Clearance", "len", 0.040, group="Cutting",
          tooltip="Radial retract above the work and Z gap in front of the face"),
]


def generate(p: dict, machine: MachineProfile, units: Units) -> list[str]:
    start_r = p["start_dia"] / 2.0
    end_r = p["end_dia"] / 2.0
    if end_r >= start_r:
        raise ValueError("end diameter must be smaller than start diameter")
    clear = p["clearance"]

    prog = Program(machine, units, origin_r=start_r,
                   start_note="touch off on the stock OD at the face")
    prog.header(
        "External turning",
        [f"dia {p['start_dia']} -> {p['end_dia']}, length {p['length']}",
         f"doc {p['doc']} radial, finish {p['finish_allow']}, feed {p['feed']}"])
    prog.rapid(x=start_r + clear, z=clear)
    for r in turning_passes(start_r, end_r, p["doc"], p["finish_allow"]):
        prog.rapid(x=r)
        prog.feed(z=-p["length"], f=p["feed"])
        prog.rapid(x=r + clear)
        prog.rapid(z=clear)
    return prog.end()


OP = Operation("ext_turning", "External turning (OD)", "ext_od.svg",
               "ext_od.svg", FIELDS, generate)
