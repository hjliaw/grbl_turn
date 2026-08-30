"""Boring: enlarge an existing hole. Same pass loop as turning but X grows
and the retract goes inward (toward center) to clear the bore wall."""

from grbl_turn.gcode import Program
from grbl_turn.machine import MachineProfile
from grbl_turn.ops.base import Field, Operation
from grbl_turn.ops.passes import turning_passes
from grbl_turn.units import Units

FIELDS = [
    Field("length", "Bore depth", "len", 0.500,
          group="Z (bed/leadscrew)"),
    Field("start_dia", "Existing bore diameter", "dia", 0.250,
          group="X (cross-slide)"),
    Field("end_dia", "Target bore diameter", "dia", 0.375,
          group="X (cross-slide)"),
    Field("doc", "Depth per pass, radial", "len", 0.010,
          group="X (cross-slide)"),
    Field("finish_allow", "Finish allowance, radial", "len", 0.003,
          group="X (cross-slide)", minimum=0.0),
    Field("feed", "Feed", "feed", 2.0, group="Cutting"),
    Field("clearance", "Clearance", "len", 0.020, group="Cutting",
          tooltip="Radial pull-back off the wall before retracting in Z"),
]


def generate(p: dict, machine: MachineProfile, units: Units) -> list[str]:
    start_r = p["start_dia"] / 2.0
    end_r = p["end_dia"] / 2.0
    if end_r <= start_r:
        raise ValueError("target bore must be larger than the existing bore")
    clear = p["clearance"]
    if start_r - clear <= 0:
        raise ValueError("clearance too large for the existing bore")

    prog = Program(machine, units, origin_r=start_r,
                   start_note="touch off on the bore wall at the face")
    prog.header(
        "Boring",
        [f"bore dia {p['start_dia']} -> {p['end_dia']}, depth {p['length']}",
         f"doc {p['doc']} radial, finish {p['finish_allow']}, feed {p['feed']}"])
    prog.rapid(x=start_r - clear, z=clear)
    for r in turning_passes(start_r, end_r, p["doc"], p["finish_allow"]):
        prog.rapid(x=r)
        prog.feed(z=-p["length"], f=p["feed"])
        prog.rapid(x=r - clear)
        prog.rapid(z=clear)
    return prog.end()


OP = Operation("int_boring", "Boring", "int_boring.svg", "int_boring.svg",
               FIELDS, generate, silhouette="bore")
