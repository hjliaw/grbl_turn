"""Tapers, external and internal. The taper runs from the face (Z0) to
Z-length; you give the diameter at each end. Roughing is done with straight
passes stepped to the cone, then a finish pass follows the taper itself."""

from grbl_turn.gcode import footer, header
from grbl_turn.machine import MachineProfile
from grbl_turn.ops.base import Field, Operation, spindle_fields, spindle_preamble
from grbl_turn.ops.passes import turning_passes
from grbl_turn.units import Units, fmt


def _fields(internal: bool) -> list[Field]:
    if internal:
        x_fields = [
            Field("start_dia", "Existing bore diameter", "dia", 0.375,
                  group="X (cross-slide)",
                  tooltip="Pilot bore; must be at least the small-end diameter"),
            Field("face_dia", "Diameter at face (large end)", "dia", 0.625,
                  group="X (cross-slide)"),
            Field("end_dia", "Diameter at depth (small end)", "dia", 0.375,
                  group="X (cross-slide)"),
        ]
    else:
        x_fields = [
            Field("start_dia", "Stock diameter", "dia", 0.750,
                  group="X (cross-slide)"),
            Field("face_dia", "Diameter at face (small end)", "dia", 0.500,
                  group="X (cross-slide)"),
            Field("end_dia", "Diameter at length (large end)", "dia", 0.750,
                  group="X (cross-slide)"),
        ]
    return x_fields + [
        Field("length", "Taper length (from face)", "len", 1.000,
              group="Z (bed/leadscrew)"),
        Field("doc", "Depth per pass (radial)", "len", 0.020,
              group="X (cross-slide)"),
        Field("feed", "Feed", "feed", 3.0, group="Cutting"),
        Field("clearance", "Clearance", "len", 0.040, group="Cutting"),
    ] + spindle_fields()


def _generate(p: dict, machine: MachineProfile, units: Units,
              internal: bool) -> list[str]:
    face_r = p["face_dia"] / 2.0
    end_r = p["end_dia"] / 2.0
    start_r = p["start_dia"] / 2.0
    length = p["length"]
    clear = p["clearance"]

    if internal:
        if not (face_r > end_r >= start_r - 1e-9):
            raise ValueError("internal taper needs face dia > end dia >= bore dia")
        safe_x = machine.x_word(max(start_r - clear, 0.0))
        retract_sign = -1.0
        # cone radius as a function of z (z <= 0): wide at face, narrow at depth
        passes = turning_passes(start_r, face_r, p["doc"])
    else:
        if not (start_r >= end_r > face_r):
            raise ValueError("external taper needs stock >= large end > small end")
        safe_x = machine.x_word(start_r + clear)
        retract_sign = 1.0
        passes = turning_passes(start_r, face_r, p["doc"])

    # z on the cone where radius == r
    def cone_z(r: float) -> float:
        return -length * (r - face_r) / (end_r - face_r)

    title = "Internal taper" if internal else "External taper"
    lines = header(
        title,
        [f"dia {p['face_dia']} at face -> {p['end_dia']} at Z-{length:g}",
         f"doc {p['doc']} radial, feed {p['feed']}"],
        units)
    lines += spindle_preamble(p)
    lines.append(f"G0 X{fmt(safe_x, units)} Z{fmt(clear, units)}")

    # roughing: straight passes, each stopping where it meets the cone
    for r in passes:
        z_stop = max(cone_z(r), -length)
        lines.append(f"G0 X{fmt(machine.x_word(r), units)}")
        lines.append(f"G1 Z{fmt(z_stop, units)} F{p['feed']:g}")
        lines.append(f"G0 X{fmt(machine.x_word(r + retract_sign * clear), units)}")
        lines.append(f"G0 Z{fmt(clear, units)}")

    # finish pass along the taper, face to depth
    lines.append(f"G0 X{fmt(machine.x_word(face_r), units)}")
    lines.append(f"G1 Z{fmt(0.0, units)} F{p['feed']:g}")
    lines.append(f"G1 X{fmt(machine.x_word(end_r), units)} "
                 f"Z{fmt(-length, units)} F{p['feed']:g}")
    lines.append(f"G0 X{fmt(machine.x_word(end_r + retract_sign * clear), units)}")
    lines += footer(p.get("app_spindle", False), safe_x, clear, units)
    return lines


def generate_ext(p, machine, units):
    return _generate(p, machine, units, internal=False)


def generate_int(p, machine, units):
    return _generate(p, machine, units, internal=True)


OP_EXT = Operation("ext_taper", "External taper", "ext_taper.svg",
                   "ext_taper.svg", _fields(False), generate_ext)
OP_INT = Operation("int_taper", "Internal taper", "int_taper.svg",
                   "int_taper.svg", _fields(True), generate_int)
