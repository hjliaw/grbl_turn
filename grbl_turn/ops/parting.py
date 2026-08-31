"""Parting / grooving: plunge the parting blade radially, with optional
pecking to break chips.

No absolute stock diameter or Z position is asked for: the operator jogs
the carriage to wherever the cut belongs and touches off there, on the
stock OD -- both axes read zero at that point, not at the face. Parting
all the way through just means entering at least the stock's real
diameter -- sweeping a little past center is harmless once the part has
already separated."""

from grbl_turn.gcode import Program
from grbl_turn.machine import MachineProfile
from grbl_turn.ops.base import Field, Operation
from grbl_turn.units import Units

FIELDS = [
    Field("dia_reduction", "Diameter to part through", "dia", 0.750,
          group="X (cross-slide)",
          tooltip="Swept from the touched OD; enter at least the stock "
                  "diameter to part all the way through"),
    Field("feed", "Feed", "feed", 1.0, group="Cutting"),
    Field("peck", "Peck depth (radial, 0=off)", "len", 0.050, group="Cutting",
          minimum=0.0, tooltip="Retract briefly after each peck to break chips"),
    Field("retract", "Peck retract", "len", 0.010, group="Cutting", minimum=0.0),
    Field("clearance", "Clearance", "len", 0.040, group="Cutting"),
]


def generate(p: dict, machine: MachineProfile, units: Units) -> list[str]:
    end_r = -p["dia_reduction"] / 2.0
    if end_r >= 0:
        raise ValueError("diameter to part through must be > 0")
    clear = p["clearance"]

    prog = Program(machine, units, origin_r=None,
                   start_note="touch off on the stock OD at the parting "
                              "location")
    prog.header(
        "Parting",
        [f"part across {p['dia_reduction']} dia",
         f"feed {p['feed']}, peck {p['peck']}"])
    prog.rapid(x=clear)

    if p["peck"] > 0:
        r = 0.0
        while r > end_r + 1e-9:
            r = max(r - p["peck"], end_r)
            prog.feed(x=r, f=p["feed"])
            if r > end_r + 1e-9:
                prog.rapid(x=r + p["retract"])
    else:
        prog.feed(x=end_r, f=p["feed"])

    prog.rapid(x=clear)
    return prog.end()


OP = Operation("int_parting", "Parting", "int_parting.svg", "int_parting.svg",
               FIELDS, generate)
