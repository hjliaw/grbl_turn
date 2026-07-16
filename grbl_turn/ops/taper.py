"""Tapers, external and internal. The taper runs from the face (Z0) to
Z-length; you give the diameter at the face and the taper angle per side
(the compound-slide angle). Roughing is done with straight passes stepped
to the cone, then a finish pass follows the taper itself."""

import math

from grbl_turn.gcode import footer, header
from grbl_turn.machine import MachineProfile
from grbl_turn.ops.base import Field, Operation
from grbl_turn.ops.passes import turning_passes
from grbl_turn.units import Units, fmt

# half angles (deg per side) from the standard taper-per-foot values
MORSE_ANGLES = {"MT0": 1.4908, "MT1": 1.4287, "MT2": 1.4307, "MT3": 1.4377}


def _fields(internal: bool) -> list[Field]:
    if internal:
        x_fields = [
            Field("start_dia", "Existing bore diameter", "dia", 0.375,
                  group="X (cross-slide)",
                  tooltip="Pilot bore the taper is cut into"),
            Field("face_dia", "Diameter at face (large end)", "dia", 0.625,
                  group="X (cross-slide)"),
        ]
    else:
        x_fields = [
            Field("start_dia", "Stock diameter", "dia", 0.750,
                  group="X (cross-slide)"),
            Field("face_dia", "Diameter at face (small end)", "dia", 0.500,
                  group="X (cross-slide)"),
        ]
    return [
        Field("angle", "Taper angle (per side)", "angle", 7.0,
              group="Taper", minimum=0.01, maximum=80.0,
              tooltip="Half angle, as set on a compound slide; the "
                      "diameter changes by 2 x tan(angle) per unit length",
              presets=MORSE_ANGLES),
        Field("trim", "Trim existing taper", "bool", False, group="Taper",
              tooltip="Every pass runs the full taper length instead of "
                      "straight roughing — for skimming an already tapered "
                      "surface (start/stock dia = current dia at the face)"),
    ] + x_fields + [
        Field("length", "Taper length (from face)", "len", 1.000,
              group="Z (bed/leadscrew)"),
        Field("doc", "Depth per pass (radial)", "len", 0.020,
              group="X (cross-slide)"),
        Field("feed", "Feed", "feed", 3.0, group="Cutting"),
        Field("clearance", "Clearance", "len", 0.040, group="Cutting"),
    ]


def _generate(p: dict, machine: MachineProfile, units: Units,
              internal: bool) -> list[str]:
    face_r = p["face_dia"] / 2.0
    start_r = p["start_dia"] / 2.0
    length = p["length"]
    clear = p["clearance"]
    angle = p["angle"]
    if not (0.0 < angle < 90.0):
        raise ValueError("taper angle must be between 0 and 90 deg per side")
    # radius change over the taper length; wide end derived from the angle
    delta = length * math.tan(math.radians(angle))

    warns = []
    if internal:
        end_r = face_r - delta      # narrows toward depth
        if end_r < 0:
            raise ValueError("taper reaches the centerline — reduce the "
                             "angle or the length")
        if end_r < start_r - 1e-9:
            warns.append("WARNING: taper undercuts the existing bore "
                         f"(dia {end_r * 2:.4f} < {p['start_dia']:g}) at depth")
        safe_x = machine.x_word(max(start_r - clear, 0.0))
        retract_sign = -1.0
        # cone radius as a function of z (z <= 0): wide at face, narrow at depth
        passes = turning_passes(start_r, face_r, p["doc"])
    else:
        end_r = face_r + delta      # widens toward depth
        if end_r > start_r + 1e-9:
            warns.append("WARNING: taper exceeds the stock diameter "
                         f"(dia {end_r * 2:.4f} > {p['start_dia']:g}) at depth")
        safe_x = machine.x_word(max(start_r, end_r) + clear)
        retract_sign = 1.0
        passes = turning_passes(start_r, face_r, p["doc"])

    # z on the cone where radius == r
    def cone_z(r: float) -> float:
        return -length * (r - face_r) / (end_r - face_r)

    trim = bool(p["trim"])
    if trim and internal and end_r + (start_r - face_r) < 0:
        raise ValueError("trim passes cross the centerline — reduce the "
                         "angle or the length")

    title = "Internal taper" if internal else "External taper"
    mode = "full-length trim passes" if trim else "straight roughing + finish"
    lines = header(
        title,
        [f"dia {p['face_dia']} at face, {angle:g} deg/side -> "
         f"dia {end_r * 2:.4f} at Z-{length:g}",
         f"{mode}, doc {p['doc']} radial, feed {p['feed']}"] + warns,
        units)
    lines.append(f"G0 X{fmt(safe_x, units)} Z{fmt(clear, units)}")

    if trim:
        # every pass follows the cone over the full length, stepping the
        # whole profile inward until it lands on the target taper
        for r in passes:
            offset = r - face_r
            lines.append(f"G0 X{fmt(machine.x_word(r), units)}")
            lines.append(f"G1 Z{fmt(0.0, units)} F{p['feed']:g}")
            lines.append(f"G1 X{fmt(machine.x_word(end_r + offset), units)} "
                         f"Z{fmt(-length, units)} F{p['feed']:g}")
            retract = end_r + offset + retract_sign * clear
            lines.append(f"G0 X{fmt(machine.x_word(retract), units)}")
            lines.append(f"G0 Z{fmt(clear, units)}")
    else:
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
    lines += footer(safe_x, clear, units)
    return lines


def generate_ext(p, machine, units):
    return _generate(p, machine, units, internal=False)


def generate_int(p, machine, units):
    return _generate(p, machine, units, internal=True)


OP_EXT = Operation("ext_taper", "External taper", "ext_taper.svg",
                   "ext_taper.svg", _fields(False), generate_ext)
OP_INT = Operation("int_taper", "Internal taper", "int_taper.svg",
                   "int_taper.svg", _fields(True), generate_int)
