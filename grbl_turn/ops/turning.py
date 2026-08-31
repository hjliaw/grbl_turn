"""External OD turning: reduce the diameter by a fixed amount over a length.

No absolute diameter is asked for: the operator touches off on the stock OD
at the face (whatever it actually measures), and the cut is specified as how
much diameter to remove from there — the stock's real diameter never has to
be known or typed in."""

from grbl_turn.gcode import Program
from grbl_turn.machine import MachineProfile
from grbl_turn.ops.base import Field, Operation
from grbl_turn.ops.passes import turning_passes
from grbl_turn.units import Units

FIELDS = [
    Field("length", "Length", "len", 0.750, group="Z (bed/leadscrew)",
          tooltip="Cut runs from Z0 to Z-length"),
    Field("dia_reduction", "Diameter reduction", "dia", 0.100,
          group="X (cross-slide)",
          tooltip="How much diameter to remove, measured from the touched "
                  "OD"),
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
    end_r = -p["dia_reduction"] / 2.0
    if end_r >= 0:
        raise ValueError("diameter reduction must be > 0")
    clear = p["clearance"]

    prog = Program(machine, units, origin_r=None,
                   start_note="touch off on the stock OD at the face")
    prog.header(
        "External turning",
        [f"reduce diameter by {p['dia_reduction']}, length {p['length']}",
         f"doc {p['doc']} radial, finish {p['finish_allow']}, feed {p['feed']}"])
    prog.rapid(x=clear, z=clear)
    for r in turning_passes(0.0, end_r, p["doc"], p["finish_allow"]):
        prog.rapid(x=r)
        prog.feed(z=-p["length"], f=p["feed"])
        prog.rapid(x=r + clear)
        prog.rapid(z=clear)
    return prog.end()


OP = Operation("ext_turning", "External turning (OD)", "ext_od.svg",
               "ext_od.svg", FIELDS, generate)
