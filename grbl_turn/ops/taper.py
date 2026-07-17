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

MODE_CUT = "Cut from stock"
MODE_TRIM = "Trim existing taper"


def _fields(internal: bool) -> list[Field]:
    target_tip = ("The finished diameter at the face; trim passes step "
                  "from the existing surface (Diameter at face) toward "
                  "it by the depth per pass")
    if internal:
        x_fields = [
            Field("start_dia", "Existing bore diameter", "dia", 0.375,
                  group="X (cross-slide)",
                  tooltip="Pilot bore the taper is cut into",
                  visible_when=("mode", MODE_CUT)),
            Field("target_dia", "Target diameter at face", "dia", 0.645,
                  group="X (cross-slide)", tooltip=target_tip,
                  visible_when=("mode", MODE_TRIM)),
            Field("face_dia", "Diameter at face", "dia", 0.625,
                  group="X (cross-slide)",
                  tooltip="Finished size when cutting from stock; the "
                          "existing surface when trimming"),
        ]
    else:
        x_fields = [
            Field("start_dia", "Stock diameter", "dia", 0.750,
                  group="X (cross-slide)",
                  visible_when=("mode", MODE_CUT)),
            Field("target_dia", "Target diameter at face", "dia", 0.480,
                  group="X (cross-slide)", tooltip=target_tip,
                  visible_when=("mode", MODE_TRIM)),
            Field("face_dia", "Diameter at face", "dia", 0.500,
                  group="X (cross-slide)",
                  tooltip="Finished size when cutting from stock; the "
                          "existing surface when trimming"),
        ]
    return [
        Field("angle", "Taper angle (per side)", "angle", 7.0,
              group="Taper", minimum=0.01, maximum=80.0,
              tooltip="Half angle, as set on a compound slide; the "
                      "diameter changes by 2 x tan(angle) per unit length",
              presets=MORSE_ANGLES),
        Field("mode", "Mode", "choice", MODE_CUT, placement="left",
              choices=[MODE_CUT, MODE_TRIM],
              tooltip="Trim: progressive full-length passes along an "
                      "existing tapered surface, stepping from its "
                      "measured diameter at the face to the target"),
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

    trim = p["mode"] == MODE_TRIM
    if trim:
        # the finished cone sits at the target; the existing surface
        # (face_dia) is a parallel cone, skin further out (in, if internal)
        final_r = p["target_dia"] / 2.0
        skin = (final_r - face_r) if internal else (face_r - final_r)
        if skin < -1e-9:
            raise ValueError(
                "target diameter would not remove material (existing "
                f"dia at face {p['face_dia']:g})")
        # radial offsets off the finished cone, one full-length pass each,
        # stepping by doc and ending exactly on the target
        offsets = turning_passes(max(skin, 0.0), 0.0, p["doc"])
    else:
        final_r = face_r
        skin = 0.0
        offsets = [0.0]

    warns = []
    if internal:
        end_r = final_r - delta     # narrows toward depth
        if end_r - skin < 0:
            raise ValueError("taper reaches the centerline — reduce the "
                             "angle or the length")
        if not trim and end_r < start_r - 1e-9:
            warns.append("WARNING: taper undercuts the existing bore "
                         f"(dia {end_r * 2:.4f} < {p['start_dia']:g}) at depth")
        retract_sign = -1.0
        safe_x = machine.x_word(
            max((end_r - skin if trim else start_r) - clear, 0.0))
    else:
        end_r = final_r + delta     # widens toward depth
        if not trim and end_r > start_r + 1e-9:
            warns.append("WARNING: taper exceeds the stock diameter "
                         f"(dia {end_r * 2:.4f} > {p['start_dia']:g}) at depth")
        retract_sign = 1.0
        safe_x = machine.x_word(
            (end_r + skin if trim else max(start_r, end_r)) + clear)

    # z on the cone where radius == r
    def cone_z(r: float) -> float:
        return -length * (r - final_r) / (end_r - final_r)

    title = "Internal taper" if internal else "External taper"
    mode = (f"trim in {len(offsets)} passes, doc {p['doc']:g} radial"
            if trim else
            f"straight roughing at doc {p['doc']} radial + finish")
    lines = header(
        title,
        [f"dia {final_r * 2:g} at face, {angle:g} deg/side -> "
         f"dia {end_r * 2:.4f} at Z-{length:g}",
         f"{mode}, feed {p['feed']}"] + warns,
        units)
    lines.append(f"G0 X{fmt(safe_x, units)} Z{fmt(clear, units)}")

    if not trim:
        # roughing: straight passes, each stopping where it meets the cone
        for r in turning_passes(p["start_dia"] / 2.0, face_r, p["doc"]):
            z_stop = max(cone_z(r), -length)
            lines.append(f"G0 X{fmt(machine.x_word(r), units)}")
            lines.append(f"G1 Z{fmt(z_stop, units)} F{p['feed']:g}")
            lines.append(f"G0 X{fmt(machine.x_word(r + retract_sign * clear), units)}")
            lines.append(f"G0 Z{fmt(clear, units)}")

    # passes along the taper, face to depth; cut-from-stock has one finish
    # pass on the cone, trim steps parallel passes down onto the target
    for off in offsets:
        lines.append(
            f"G0 X{fmt(machine.x_word(final_r + retract_sign * off), units)}")
        lines.append(f"G1 Z{fmt(0.0, units)} F{p['feed']:g}")
        lines.append(
            f"G1 X{fmt(machine.x_word(end_r + retract_sign * off), units)} "
            f"Z{fmt(-length, units)} F{p['feed']:g}")
        lines.append(
            f"G0 X{fmt(machine.x_word(end_r + retract_sign * (off + clear)), units)}")
        lines.append(f"G0 Z{fmt(clear, units)}")
    lines += footer(safe_x, clear, units)
    return lines


def generate_ext(p, machine, units):
    return _generate(p, machine, units, internal=False)


def generate_int(p, machine, units):
    return _generate(p, machine, units, internal=True)


OP_EXT = Operation("ext_taper", "External taper", "ext_taper.svg",
                   "ext_taper.svg", _fields(False), generate_ext)
OP_INT = Operation("int_taper", "Internal taper", "int_taper.svg",
                   "int_taper.svg", _fields(True), generate_int,
                   silhouette="bore")
