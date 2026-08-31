"""Boring: enlarge an existing hole. Same pass loop as turning but X grows
and the retract goes inward (toward center) to clear the bore wall.

No absolute bore diameter is asked for: the operator touches off on the
bore wall at the face (whatever it actually measures), and the cut is
specified as how much diameter to remove from there — the existing bore's
real diameter never has to be known or typed in."""

from grbl_turn.gcode import Program
from grbl_turn.machine import MachineProfile
from grbl_turn.ops.base import Field, Operation
from grbl_turn.ops.passes import turning_passes
from grbl_turn.units import Units

FIELDS = [
    Field("length", "Bore depth", "len", 0.500,
          group="Z (bed/leadscrew)"),
    Field("dia_increase", "Diameter increase", "dia", 0.125,
          group="X (cross-slide)",
          tooltip="How much to enlarge the bore by, measured from the "
                  "touched wall"),
    Field("doc", "Depth per pass, radial", "len", 0.010,
          group="X (cross-slide)"),
    Field("finish_allow", "Finish allowance, radial", "len", 0.003,
          group="X (cross-slide)", minimum=0.0),
    Field("feed", "Feed", "feed", 2.0, group="Cutting"),
    Field("clearance", "Clearance", "len", 0.020, group="Cutting",
          tooltip="Radial pull-back off the wall before retracting in Z"),
]


def generate(p: dict, machine: MachineProfile, units: Units) -> list[str]:
    end_r = p["dia_increase"] / 2.0
    if end_r <= 0:
        raise ValueError("diameter increase must be > 0")
    clear = p["clearance"]

    prog = Program(machine, units, origin_r=None,
                   start_note="touch off on the bore wall at the face")
    prog.header(
        "Boring",
        [f"enlarge bore by {p['dia_increase']}, depth {p['length']}",
         f"doc {p['doc']} radial, finish {p['finish_allow']}, feed {p['feed']}"])
    prog.rapid(x=-clear, z=clear)
    for r in turning_passes(0.0, end_r, p["doc"], p["finish_allow"]):
        prog.rapid(x=r)
        prog.feed(z=-p["length"], f=p["feed"])
        prog.rapid(x=r - clear)
        prog.rapid(z=clear)
    return prog.end()


OP = Operation("int_boring", "Boring", "int_boring.svg", "int_boring.svg",
               FIELDS, generate, silhouette="bore")
