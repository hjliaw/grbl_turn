"""Single-point threading, external and internal.

Requires spindle-synchronized motion in the firmware (spindle encoder).
Two emitters, selected by the machine profile:
  - G76 canned cycle (grblHAL / LinuxCNC-style words)
  - explicit G33 passes computed by the app (fallback; also useful to read
    to see exactly what G76 will do)

Both use the same degressive infeed math from passes.thread_infeeds().
"""

from grbl_turn.gcode import footer, header
from grbl_turn.machine import MachineProfile
from grbl_turn.ops.base import Field, Operation
from grbl_turn.ops.passes import flank_offset, thread_infeeds
from grbl_turn.units import Units, fmt

# thread depth as a fraction of pitch for 60 deg threads (UN/ISO shop values)
EXT_DEPTH_FACTOR = 0.6134
INT_DEPTH_FACTOR = 0.5413


def _fields(internal: bool) -> list[Field]:
    dia_field = (
        Field("dia", "Bore diameter (thread minor)", "dia", 0.4056,
              group="X (cross-slide)",
              tooltip="Bore to the thread minor diameter before threading")
        if internal else
        Field("dia", "Major diameter (thread OD)", "dia", 0.500,
              group="X (cross-slide)")
    )
    return [
        dia_field,
        Field("total_depth", "Total depth", "len", 0.0,
              group="X (cross-slide)", minimum=0.0,
              tooltip="Radial thread depth; auto = 0.6134x pitch (ext) or "
                      "0.5413x pitch (int) for 60 deg threads",
              auto=lambda p, u: _pitch(p, u) * (INT_DEPTH_FACTOR if internal
                                                else EXT_DEPTH_FACTOR)),
        Field("first_depth", "First pass depth", "len", 0.003,
              group="X (cross-slide)"),
        Field("degression", "Depth degression (R)", "ratio", 1.5,
              group="X (cross-slide)", minimum=1.0, maximum=2.0,
              tooltip="G76 R word: 1.0 = same depth every pass, "
                      "2.0 = constant chip area (passes taper off)"),
        Field("spring", "Spring passes", "int", 1, group="X (cross-slide)",
              minimum=0, maximum=9),
        Field("pitch_val", "Pitch", "pitch", 20.0, group="Z (bed/leadscrew)",
              default_mm=1.5,
              tooltip="Inch mode: TPI; mm mode: mm/rev"),
        Field("length", "Thread length (from face)", "len", 0.500,
              group="Z (bed/leadscrew)"),
        Field("lead_in", "Lead-in", "len", 0.0,
              group="Z (bed/leadscrew)", minimum=0.0,
              tooltip="Sync-up distance in front of the face; auto = 2x pitch",
              auto=lambda p, u: 2.0 * _pitch(p, u)),
        Field("compound", "Compound angle", "choice", "29.5", group="Cutting",
              choices=["0", "29.5", "30"], unit="deg"),
        Field("clearance", "Clearance (radial)", "len", 0.020, group="Cutting"),
    ]


def _pitch(p: dict, units: Units) -> float:
    if p["pitch_val"] <= 0:
        raise ValueError("pitch must be positive")
    if units is Units.MM:
        return p["pitch_val"]           # mm/rev
    return 1.0 / p["pitch_val"]         # inch mode: TPI


def _generate(p: dict, machine: MachineProfile, units: Units,
              internal: bool) -> list[str]:
    pitch = _pitch(p, units)
    depth = p["total_depth"]
    if depth <= 0:
        raise ValueError("total depth must be > 0 — tap its A button "
                         "to auto-calculate from the pitch")
    lead_in = p["lead_in"]   # 0 is honored: sync-up starts at the face
    clear = p["clearance"]
    angle = float(p["compound"])
    r = p["dia"] / 2.0                       # major radius (ext) / minor (int)
    inward = -1.0 if internal else 1.0       # retract direction off the thread
    drive_r = r + inward * clear             # cycle start / retract radius
    if internal and drive_r <= 0:
        raise ValueError("clearance too large for the bore")
    z_end = -p["length"]

    title = "Internal threading" if internal else "External threading"
    kind = "mm/rev" if units is Units.MM else "TPI"
    lines = header(
        title,
        [f"dia {p['dia']}, pitch {p['pitch_val']:g} {kind}, length {p['length']}",
         f"depth {depth:.4f} radial, first {p['first_depth']}, "
         f"compound {angle:g} deg",
         "REQUIRES spindle sync (encoder); feed hold is DEFERRED during passes"],
        units)
    lines.append(f"G0 X{fmt(machine.x_word(drive_r), units)} "
                 f"Z{fmt(lead_in, units)}")

    if machine.has_g76:
        # I: thread peak offset from the drive line (negative = external)
        i_word = -inward * clear
        lines.append(
            f"G76 P{fmt(pitch, units)} Z{fmt(z_end, units)} "
            f"I{fmt(i_word, units)} J{fmt(p['first_depth'], units)} "
            f"R{p['degression']:g} K{fmt(depth, units)} "
            f"Q{angle:g} H{int(p['spring'])}")
    else:
        for d in thread_infeeds(depth, p["first_depth"], p["degression"],
                                int(p["spring"])):
            z_start = lead_in - flank_offset(d, angle)
            lines.append(f"G0 Z{fmt(z_start, units)}")
            lines.append(f"G0 X{fmt(machine.x_word(r - inward * d), units)}")
            lines.append(f"G33 Z{fmt(z_end, units)} K{fmt(pitch, units)}")
            lines.append(f"G0 X{fmt(machine.x_word(drive_r), units)}")
    lines += footer(machine.x_word(drive_r),
                    lead_in, units)
    return lines


def generate_ext(p, machine, units):
    return _generate(p, machine, units, internal=False)


def generate_int(p, machine, units):
    return _generate(p, machine, units, internal=True)


OP_EXT = Operation("ext_thread", "External thread", "ext_thread2.svg",
                   "ext_thread2_dim.svg", _fields(False), generate_ext,
                   is_threading=True)
OP_INT = Operation("int_thread", "Internal thread", "int_thread2.svg",
                   "int_thread2.svg", _fields(True), generate_int,
                   is_threading=True, silhouette="bore")
