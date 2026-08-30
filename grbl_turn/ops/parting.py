"""Parting / grooving: plunge the parting blade at a Z position, with
optional pecking to break chips."""

from grbl_turn.gcode import Program
from grbl_turn.machine import MachineProfile
from grbl_turn.ops.base import Field, Operation
from grbl_turn.units import Units

FIELDS = [
    Field("z_pos", "Z position", "zpos", 0.500,
          group="Z (bed/leadscrew)",
          tooltip="Distance from the face to the LEFT side of the blade;\n"
                  "the cut happens at Z-value"),
    Field("work_dia", "Stock diameter", "dia", 0.750, group="X (cross-slide)"),
    Field("end_dia", "End diameter", "dia", 0.0, group="X (cross-slide)",
          minimum=0.0, tooltip="0 = part off at center"),
    Field("feed", "Feed", "feed", 1.0, group="Cutting"),
    Field("peck", "Peck depth (radial, 0=off)", "len", 0.050, group="Cutting",
          minimum=0.0, tooltip="Retract briefly after each peck to break chips"),
    Field("retract", "Peck retract", "len", 0.010, group="Cutting", minimum=0.0),
    Field("clearance", "Clearance", "len", 0.040, group="Cutting"),
]


def generate(p: dict, machine: MachineProfile, units: Units) -> list[str]:
    work_r = p["work_dia"] / 2.0
    end_r = p["end_dia"] / 2.0
    if end_r >= work_r:
        raise ValueError("end diameter must be smaller than the stock diameter")
    clear = p["clearance"]
    z = -p["z_pos"]

    prog = Program(machine, units, origin_r=work_r,
                   start_note="touch off on the stock OD at the face")
    prog.header(
        "Parting",
        [f"stock dia {p['work_dia']} -> {p['end_dia']} at Z{z:g}",
         f"feed {p['feed']}, peck {p['peck']}"])
    prog.rapid(x=work_r + clear, z=clear)
    prog.rapid(z=z)

    if p["peck"] > 0:
        r = work_r
        while r > end_r + 1e-9:
            r = max(r - p["peck"], end_r)
            prog.feed(x=r, f=p["feed"])
            if r > end_r + 1e-9:
                prog.rapid(x=r + p["retract"])
    else:
        prog.feed(x=end_r, f=p["feed"])

    prog.rapid(x=work_r + clear)
    return prog.end()


OP = Operation("int_parting", "Parting", "int_parting.svg", "int_parting.svg",
               FIELDS, generate)
