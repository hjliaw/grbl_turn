"""Tapers, external and internal. The taper runs from the face (Z0) to
Z-length; you give the taper angle per side (the compound-slide angle) and
how much diameter to remove (external) or add (internal) at the face.
Roughing is done with straight passes stepped to the cone, then a finish
pass follows the taper itself.

No absolute diameter is asked for: the operator touches off on the surface
that exists before the cut -- the stock/pilot bore when cutting fresh, the
taper itself when trimming -- and the face change is measured from there."""

import math

from grbl_turn.gcode import Program
from grbl_turn.machine import MachineProfile
from grbl_turn.ops.base import Field, Operation
from grbl_turn.ops.passes import turning_passes
from grbl_turn.units import Units

# half angles (deg per side) from the standard taper-per-foot values
MORSE_ANGLES = {"MT0": 1.4908, "MT1": 1.4287, "MT2": 1.4307, "MT3": 1.4377}

MODE_CUT = "Cut from stock"
MODE_CUT_INT = "Cut from bored"
MODE_TRIM = "Trim existing taper"


def _fields(internal: bool) -> list[Field]:
    mode_cut = MODE_CUT_INT if internal else MODE_CUT
    if internal:
        change_field = Field(
            "dia_increase", "Diameter increase at face", "dia", 0.250,
            group="X (cross-slide)",
            tooltip="How much to enlarge the diameter at the face, "
                    "measured from the touched surface: bored up before "
                    "the cone when cutting fresh, or trimmed off the "
                    "existing taper when trimming")
    else:
        change_field = Field(
            "dia_reduction", "Diameter reduction at face", "dia", 0.250,
            group="X (cross-slide)",
            tooltip="How much to reduce the diameter at the face, "
                    "measured from the touched surface: turned down "
                    "before the cone when cutting fresh, or trimmed off "
                    "the existing taper when trimming")
    return [
        Field("angle", "Taper angle (a)", "angle", 7.0,
              group="Taper", minimum=0.01, maximum=80.0,
              tooltip="Half angle, as set on a compound slide; the "
                      "diameter changes by 2 x tan(angle) per unit length",
              presets=MORSE_ANGLES),
        Field("mode", "Mode", "choice", mode_cut, placement="left",
              choices=[mode_cut, MODE_TRIM],
              tooltip="Trim: progressive full-length passes along an "
                      "existing tapered surface, stepping from the "
                      "touched surface to the target"),
        Field("length", "Taper length (L)", "len", 1.000,
              group="Z (bed/leadscrew)"),
        change_field,
        Field("doc", "Depth per pass, radial", "len", 0.020,
              group="X (cross-slide)"),
        Field("feed", "Feed", "feed", 3.0, group="Cutting"),
        Field("clearance", "Clearance", "len", 0.040, group="Cutting"),
    ]


def _generate(p: dict, machine: MachineProfile, units: Units,
              internal: bool) -> list[str]:
    length = p["length"]
    clear = p["clearance"]
    angle = p["angle"]
    if not (0.0 < angle < 90.0):
        raise ValueError("taper angle must be between 0 and 90 deg per side")
    change_key = "dia_increase" if internal else "dia_reduction"
    change_r = p[change_key] / 2.0
    if change_r < 0:
        raise ValueError(f"'{change_key}' must be >= 0")
    # radius change over the taper length; deep end derived from the angle
    delta = length * math.tan(math.radians(angle))

    # face_r is the finished radius at the face (Z0), relative to the
    # touched surface (X0): cutting fresh turns/bores down to it before the
    # cone starts, trimming steps straight onto it. Same quantity either
    # way -- it's just where the finish cone's face sits.
    face_r = change_r if internal else -change_r

    trim = p["mode"] == MODE_TRIM
    offsets = turning_passes(change_r, 0.0, p["doc"]) if trim else [0.0]

    warns = []
    if internal:
        end_r = face_r - delta     # narrows toward depth
        if not trim and end_r < -1e-9:
            warns.append("WARNING: taper undercuts the existing bore "
                         f"(short by {-end_r * 2:.4f} dia) at depth")
        retract_sign = -1.0
        safe_r = (end_r - change_r if trim else 0.0) - clear
    else:
        end_r = face_r + delta     # widens toward depth
        if not trim and end_r > 1e-9:
            warns.append("WARNING: taper exceeds the stock diameter "
                         f"(over by {end_r * 2:.4f} dia) at depth")
        retract_sign = 1.0
        safe_r = (end_r + change_r if trim else max(0.0, end_r)) + clear

    # z on the cone where radius == r
    def cone_z(r: float) -> float:
        return -length * (r - face_r) / (end_r - face_r)

    title = "Internal taper" if internal else "External taper"
    verb = "enlarge" if internal else "reduce"
    mode_desc = (f"trim in {len(offsets)} passes, doc {p['doc']:g} radial"
                if trim else
                f"straight roughing at doc {p['doc']} radial + finish")
    # the operator touches off on the surface that exists before the cut:
    # the stock/pilot bore when cutting fresh, the taper itself when trimming
    surface = ("the existing taper at the face" if trim else
               "the pilot bore wall at the face" if internal else
               "the stock OD at the face")
    prog = Program(machine, units, origin_r=None,
                   start_note=f"touch off on {surface}")
    prog.header(
        title,
        [f"{verb} face by {p[change_key]:g} dia, {angle:g} deg/side, "
         f"depth-end {end_r * 2:+.4f} dia relative to touch, "
         f"length {length:g}",
         f"{mode_desc}, feed {p['feed']}"] + warns)
    prog.rapid(x=safe_r, z=clear)

    if not trim:
        # roughing: straight passes, each stopping where it meets the cone
        for r in turning_passes(0.0, face_r, p["doc"]):
            z_stop = max(cone_z(r), -length)
            prog.rapid(x=r)
            prog.feed(z=z_stop, f=p["feed"])
            prog.rapid(x=r + retract_sign * clear)
            prog.rapid(z=clear)

    # passes along the taper, face to depth; cut-from-stock has one finish
    # pass on the cone, trim steps parallel passes down onto the target
    for off in offsets:
        prog.rapid(x=face_r + retract_sign * off)
        prog.feed(z=0.0, f=p["feed"])
        prog.feed(x=end_r + retract_sign * off, z=-length, f=p["feed"])
        prog.rapid(x=end_r + retract_sign * (off + clear))
        prog.rapid(z=clear)
    return prog.end()


def generate_ext(p, machine, units):
    return _generate(p, machine, units, internal=False)


def generate_int(p, machine, units):
    return _generate(p, machine, units, internal=True)


OP_EXT = Operation("ext_taper", "External taper", "ext_taper.svg",
                   "ext_taper_dim.svg", _fields(False), generate_ext)
OP_INT = Operation("int_taper", "Internal taper", "int_taper.svg",
                   "int_taper_dim.svg", _fields(True), generate_int,
                   silhouette="bore")
