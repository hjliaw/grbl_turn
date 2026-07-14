"""Parting / grooving: plunge the parting blade at a Z position, with
optional pecking to break chips."""

from grbl_turn.gcode import footer, header
from grbl_turn.machine import MachineProfile
from grbl_turn.ops.base import Field, Operation, spindle_fields, spindle_preamble
from grbl_turn.units import Units, fmt

FIELDS = [
    Field("work_dia", "Stock diameter", "dia", 0.750, group="X (cross-slide)"),
    Field("end_dia", "End diameter", "dia", 0.0, group="X (cross-slide)",
          minimum=0.0, tooltip="0 = part off at center"),
    Field("z_pos", "Z position (from face)", "zpos", 0.500,
          group="Z (bed/leadscrew)",
          tooltip="Distance from the face to the LEFT side of the blade;\n"
                  "the cut happens at Z-value"),
    Field("feed", "Feed", "feed", 1.0, group="Cutting"),
    Field("peck", "Peck depth (radial, 0=off)", "len", 0.050, group="Cutting",
          minimum=0.0, tooltip="Retract briefly after each peck to break chips"),
    Field("retract", "Peck retract", "len", 0.010, group="Cutting", minimum=0.0),
    Field("clearance", "Clearance", "len", 0.040, group="Cutting"),
] + spindle_fields(default_rpm=300)


def generate(p: dict, machine: MachineProfile, units: Units) -> list[str]:
    work_r = p["work_dia"] / 2.0
    end_r = p["end_dia"] / 2.0
    if end_r >= work_r:
        raise ValueError("end diameter must be smaller than the stock diameter")
    clear = p["clearance"]
    safe_x = machine.x_word(work_r + clear)
    z = -p["z_pos"]

    lines = header(
        "Parting",
        [f"stock dia {p['work_dia']} -> {p['end_dia']} at Z{z:g}",
         f"feed {p['feed']}, peck {p['peck']}"],
        units)
    lines += spindle_preamble(p)
    lines.append(f"G0 X{fmt(safe_x, units)} Z{fmt(clear, units)}")
    lines.append(f"G0 Z{fmt(z, units)}")

    if p["peck"] > 0:
        r = work_r
        while r > end_r + 1e-9:
            r = max(r - p["peck"], end_r)
            lines.append(f"G1 X{fmt(machine.x_word(r), units)} F{p['feed']:g}")
            if r > end_r + 1e-9:
                lines.append(f"G0 X{fmt(machine.x_word(r + p['retract']), units)}")
    else:
        lines.append(f"G1 X{fmt(machine.x_word(end_r), units)} F{p['feed']:g}")

    lines.append(f"G0 X{fmt(safe_x, units)}")
    lines += footer(p.get("app_spindle", False), safe_x, clear, units)
    return lines


OP = Operation("int_parting", "Parting", "int_parting.svg", "int_parting.svg",
               FIELDS, generate)
