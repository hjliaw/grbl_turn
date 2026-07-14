"""External OD turning: reduce start diameter to end diameter over a length."""

from grbl_turn.gcode import footer, header
from grbl_turn.machine import MachineProfile
from grbl_turn.ops.base import Field, Operation, spindle_fields, spindle_preamble
from grbl_turn.ops.passes import turning_passes
from grbl_turn.units import Units, fmt

FIELDS = [
    Field("start_dia", "Start diameter", "dia", 0.500, group="X (cross-slide)"),
    Field("end_dia", "End diameter", "dia", 0.400, group="X (cross-slide)"),
    Field("doc", "Depth per pass (radial)", "len", 0.020, group="X (cross-slide)",
          tooltip="Radial depth of cut for each roughing pass"),
    Field("finish_allow", "Finish allowance (radial)", "len", 0.005,
          group="X (cross-slide)", minimum=0.0,
          tooltip="Left for the final pass; 0 = no separate finish pass"),
    Field("length", "Length (from face)", "len", 0.750, group="Z (bed/leadscrew)",
          tooltip="Cut runs from Z0 to Z-length"),
    Field("feed", "Feed", "feed", 3.0, group="Cutting"),
    Field("clearance", "Clearance", "len", 0.040, group="Cutting",
          tooltip="Radial retract above the work and Z gap in front of the face"),
] + spindle_fields()


def generate(p: dict, machine: MachineProfile, units: Units) -> list[str]:
    start_r = p["start_dia"] / 2.0
    end_r = p["end_dia"] / 2.0
    if end_r >= start_r:
        raise ValueError("end diameter must be smaller than start diameter")
    clear = p["clearance"]
    safe_x = machine.x_word(start_r + clear)
    z_clear = clear

    lines = header(
        "External turning",
        [f"dia {p['start_dia']} -> {p['end_dia']}, length {p['length']}",
         f"doc {p['doc']} radial, finish {p['finish_allow']}, feed {p['feed']}"],
        units)
    lines += spindle_preamble(p)
    lines.append(f"G0 X{fmt(safe_x, units)} Z{fmt(z_clear, units)}")
    for r in turning_passes(start_r, end_r, p["doc"], p["finish_allow"]):
        lines.append(f"G0 X{fmt(machine.x_word(r), units)}")
        lines.append(f"G1 Z{fmt(-p['length'], units)} F{p['feed']:g}")
        lines.append(f"G0 X{fmt(machine.x_word(r + clear), units)}")
        lines.append(f"G0 Z{fmt(z_clear, units)}")
    lines += footer(p.get("app_spindle", False), safe_x, z_clear, units)
    return lines


OP = Operation("ext_turning", "External turning (OD)", "ext_od.svg",
               "ext_od.svg", FIELDS, generate)
