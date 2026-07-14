"""Facing: remove material from the end of the stock, feeding X toward center."""

from grbl_turn.gcode import footer, header
from grbl_turn.machine import MachineProfile
from grbl_turn.ops.base import Field, Operation
from grbl_turn.units import Units, fmt

FIELDS = [
    Field("work_dia", "Stock diameter", "dia", 0.750, group="X (cross-slide)"),
    Field("end_dia", "End diameter", "dia", 0.0, group="X (cross-slide)",
          minimum=0.0, tooltip="0 = face to center"),
    Field("total_depth", "Total depth (Z)", "len", 0.020,
          group="Z (bed/leadscrew)", tooltip="Total material removed off the face"),
    Field("doc", "Depth per pass (Z)", "len", 0.010, group="Z (bed/leadscrew)"),
    Field("feed", "Feed", "feed", 3.0, group="Cutting"),
    Field("clearance", "Clearance", "len", 0.040, group="Cutting"),
]


def generate(p: dict, machine: MachineProfile, units: Units) -> list[str]:
    work_r = p["work_dia"] / 2.0
    end_r = p["end_dia"] / 2.0
    clear = p["clearance"]
    start_x = machine.x_word(work_r + clear)

    lines = header(
        "Facing",
        [f"stock dia {p['work_dia']}, total depth {p['total_depth']}",
         f"doc {p['doc']}, feed {p['feed']}"],
        units)
    lines.append(f"G0 X{fmt(start_x, units)} Z{fmt(clear, units)}")

    # Z0 is the CURRENT face; each pass goes deeper until total_depth removed.
    z = 0.0
    remaining = p["total_depth"]
    while remaining > 1e-9:
        step = min(p["doc"], remaining)
        z -= step
        remaining -= step
        lines.append(f"G0 X{fmt(start_x, units)}")
        lines.append(f"G0 Z{fmt(z, units)}")
        lines.append(f"G1 X{fmt(machine.x_word(end_r), units)} F{p['feed']:g}")
        lines.append(f"G0 Z{fmt(z + clear, units)}")
    lines += footer(start_x, clear, units)
    return lines


OP = Operation("ext_facing", "Facing", "ext_facing.svg", "ext_facing.svg",
               FIELDS, generate)
